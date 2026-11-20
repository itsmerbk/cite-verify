import re
from dataclasses import dataclass
from citeverify.indexer import get_all_pages

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
    "of", "with", "by", "and", "or", "that", "this", "it", "as", "be", "from",
    "has", "have", "had", "under", "within", "during", "using", "via", "into"
}


@dataclass
class ClaimAudit:
    claim: str
    status: str
    page_num: int | None
    confidence: float
    reason: str
    verbatim_evidence: str


def _content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_.-]+", text.lower())
    return {w.rstrip(".") for w in words if len(w) > 1 and w not in STOPWORDS}


def _numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text.lower()))


def _extract_best_snippet(page_text: str, claim_tokens: set[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", page_text)
    best_sent = sentences[0] if sentences else page_text[:140]
    best_hits = -1
    for sent in sentences:
        hits = len(_content_tokens(sent) & claim_tokens)
        if hits > best_hits:
            best_hits = hits
            best_sent = sent
    return best_sent[:115] + ("..." if len(best_sent) > 115 else "")


def verify_response(doc_name: str, candidate_response: str) -> list[ClaimAudit]:
    pages = get_all_pages(doc_name)
    claims = [s.strip() for s in re.split(r"(?<=[.!?])\s+", candidate_response.strip()) if s.strip()]
    audits: list[ClaimAudit] = []

    for claim in claims:
        c_tokens = _content_tokens(claim)
        c_nums = _numeric_tokens(claim)

        if not c_tokens:
            continue

        best_page = None
        best_score = 0.0
        missing_nums: set[str] = set()

        for page in pages:
            p_text = page["content"]
            p_tokens = _content_tokens(p_text)
            p_nums = _numeric_tokens(p_text)

            token_recall = len(c_tokens & p_tokens) / len(c_tokens)
            num_recall = 1.0 if not c_nums else (len(c_nums & p_nums) / len(c_nums))
            combined = (0.65 * token_recall) + (0.35 * num_recall)

            if combined > best_score:
                best_score = combined
                best_page = page
                missing_nums = c_nums - p_nums

        if best_page is None:
            audits.append(ClaimAudit(claim, "FLAGGED", None, 0.0, "Document empty", "—"))
            continue

        snippet = _extract_best_snippet(best_page["content"], c_tokens)
        confidence_pct = round(best_score * 100, 1)

        if missing_nums:
            audits.append(
                ClaimAudit(
                    claim=claim,
                    status="FLAGGED",
                    page_num=best_page["page_num"],
                    confidence=confidence_pct,
                    reason=f"Numeric mismatch: {', '.join(sorted(missing_nums))} absent on p.{best_page['page_num']}",
                    verbatim_evidence=snippet,
                )
            )
        elif best_score >= 0.55:
            audits.append(
                ClaimAudit(
                    claim=claim,
                    status="VERIFIED",
                    page_num=best_page["page_num"],
                    confidence=confidence_pct,
                    reason="Grounded in source text",
                    verbatim_evidence=snippet,
                )
            )
        else:
            audits.append(
                ClaimAudit(
                    claim=claim,
                    status="FLAGGED",
                    page_num=best_page["page_num"],
                    confidence=confidence_pct,
                    reason="Insufficient lexical support (<55%)",
                    verbatim_evidence=snippet,
                )
            )

    return audits
