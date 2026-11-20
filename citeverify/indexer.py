import re
import sqlite3
from pathlib import Path
import fitz

DB_PATH = Path(__file__).resolve().parent.parent / "citeverify.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS page_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_name TEXT NOT NULL,
                page_num INTEGER NOT NULL,
                content TEXT NOT NULL,
                UNIQUE(doc_name, page_num)
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(doc_name, page_num UNINDEXED, content, tokenize='porter unicode61');
            """
        )


def ingest_pdf(pdf_path: str | Path) -> tuple[str, int]:
    path = Path(pdf_path).resolve()
    doc_name = path.name
    init_db()

    doc = fitz.open(path)
    page_count = len(doc)

    with get_connection() as conn:
        conn.execute("DELETE FROM page_chunks WHERE doc_name = ?", (doc_name,))
        conn.execute("DELETE FROM chunks_fts WHERE doc_name = ?", (doc_name,))

        for idx, page in enumerate(doc, start=1):
            cleaned = re.sub(r"\s+", " ", page.get_text("text")).strip()
            if not cleaned:
                continue
            conn.execute(
                "INSERT INTO page_chunks (doc_name, page_num, content) VALUES (?, ?, ?)",
                (doc_name, idx, cleaned),
            )
            conn.execute(
                "INSERT INTO chunks_fts (doc_name, page_num, content) VALUES (?, ?, ?)",
                (doc_name, idx, cleaned),
            )

    doc.close()
    return doc_name, page_count


def search_bm25(query: str, doc_name: str | None = None, limit: int = 3) -> list[dict]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", query)
    if not tokens:
        return []
    fts_query = " OR ".join(dict.fromkeys(tokens))

    with get_connection() as conn:
        if doc_name:
            rows = conn.execute(
                """
                SELECT doc_name, page_num, content, bm25(chunks_fts) AS rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ? AND doc_name = ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (fts_query, doc_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT doc_name, page_num, content, bm25(chunks_fts) AS rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def get_all_pages(doc_name: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT doc_name, page_num, content FROM page_chunks WHERE doc_name = ? ORDER BY page_num ASC",
            (doc_name,),
        ).fetchall()
    return [dict(r) for r in rows]
