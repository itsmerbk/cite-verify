# CiteVerify

**Local-First PDF Research Engine with Deterministic Claim Verification**

CiteVerify eliminates silent LLM hallucinations in technical document Q&A. It parses multi-page PDFs locally with PyMuPDF, indexes pages in an embedded SQLite FTS5 (BM25) store, and runs a deterministic post-generation verification pass that validates every sentence—and every numerical metric—against exact page citations and verbatim source text.

## Architecture

~~~mermaid
flowchart LR
    A[Local PDF Documents] -->|PyMuPDF Page Extractor| B[(SQLite FTS5 BM25 Index)]
    C[User Query] -->|BM25 Lexical Retrieval| B
    B -->|Top-K Grounded Pages| D[LLM / Answer Draft]
    D -->|Sentence Splitter| E[Deterministic Claim Verifier]
    B -->|Full Page Corpus| E
    E -->|Match >= 55% & Exact Numbers| F[VERIFIED + Page Citation]
    E -->|Metric Mismatch / Unsourced| G[FLAGGED Hallucination Alert]
~~~

## Quickstart

~~~bash
git clone https://github.com/itsmerbk/cite-verify.git
cd cite-verify
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Generate sample technical spec PDF, index in SQLite FTS5, and run claim verification audit
python -m citeverify.demo_audit
~~~
