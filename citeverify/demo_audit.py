from pathlib import Path
import fitz
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from citeverify.indexer import ingest_pdf, search_bm25
from citeverify.verifier import verify_response

console = Console()
SAMPLE_PDF = Path(__file__).resolve().parent.parent / "docs" / "architecture_spec_v2.pdf"


def create_sample_spec_pdf(output_path: Path) -> None:
    pages_content = [
        (
            "Page 1: Edge Gateway & Ingestion SLAs\n\n"
            "The Sentinel Edge Gateway enforces a strict p99 routing latency budget of 14.5 ms "
            "at a sustained throughput of 12,000 requests per second. Incoming payloads larger than "
            "256 KB are rejected with HTTP 413 prior to authentication. Token bucket rate limiters "
            "operate per tenant key with a burst capacity of 150 requests."
        ),
        (
            "Page 2: Storage Engine & Write-Ahead Logging\n\n"
            "Telemetry snapshots are persisted in embedded SQLite instances configured with WAL mode "
            "and synchronous=NORMAL. Batch commits of 500 records complete in 1.8 ms on NVMe storage. "
            "Automated background compaction runs every 6 hours whenever the WAL file exceeds 64 MB."
        ),
        (
            "Page 3: Multi-Region Failover & Recovery\n\n"
            "Active-passive cluster replication maintains a Recovery Point Objective (RPO) of 0 seconds "
            "for committed ledger transactions. Automated leader election completes within 900 ms "
            "following three consecutive missed heartbeat probes spaced 250 ms apart."
        ),
    ]

    doc = fitz.open()
    for text in pages_content:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(54, 54, 540, 780), text, fontsize=11, fontname="helv")
    doc.save(output_path)
    doc.close()


def main() -> None:
    create_sample_spec_pdf(SAMPLE_PDF)
    doc_name, total_pages = ingest_pdf(SAMPLE_PDF)

    console.print(
        Panel.fit(
            f"[bold cyan]CiteVerify Offline Engine[/bold cyan]\n"
            f"Indexed Document: [bold]{doc_name}[/bold] ({total_pages} pages in SQLite FTS5 BM25)",
            border_style="bright_blue",
        )
    )

    # 1. BM25 Retrieval Demo
    hits = search_bm25("WAL mode batch commits NVMe", doc_name=doc_name, limit=2)
    console.print(f"\n[bold]BM25 Top Retrieval Hit:[/bold] Page {hits[0]['page_num']} (score={hits[0]['rank']:.2f})\n")

    # 2. Simulated LLM Draft with 2 Grounded Claims & 2 Subtle Hallucinations
    llm_draft = (
        "The Edge Gateway enforces a p99 routing latency budget of 14.5 ms at 12,000 requests per second. "
        "Batch commits of 500 records complete in 0.4 ms on NVMe storage. "
        "Automated leader election completes within 900 ms after three missed heartbeat probes. "
        "Cold backups are streamed directly to Amazon S3 Glacier every 15 minutes."
    )

    audits = verify_response(doc_name, llm_draft)

    table = Table(title="Deterministic Sentence-Level Claim Verification Audit", expand=True, border_style="cyan")
    table.add_column("Status", width=11)
    table.add_column("Source", width=8)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Evaluated Claim", width=36)
    table.add_column("Verification Diagnostic / Verbatim Snippet", width=38)

    verified_count = 0
    for item in audits:
        is_ok = item.status == "VERIFIED"
        if is_ok:
            verified_count += 1
        badge = "[bold green]VERIFIED[/bold green]" if is_ok else "[bold red]FLAGGED[/bold red]"
        page_label = f"p.{item.page_num}" if item.page_num else "—"
        detail = (
            f"[green]{item.verbatim_evidence}[/green]"
            if is_ok
            else f"[yellow]{item.reason}[/yellow]\n[dim]Closest (p.{item.page_num}): {item.verbatim_evidence}[/dim]"
        )
        table.add_row(badge, page_label, f"{item.confidence}%", item.claim, detail)

    console.print(table)
    console.print(
        f"\n[bold]Audit Summary:[/bold] {verified_count}/{len(audits)} claims verified; "
        f"{len(audits) - verified_count} hallucinated/unsupported claims intercepted.\n"
    )


if __name__ == "__main__":
    main()
