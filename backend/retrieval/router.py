import re


def route(question: str):
    q = question.casefold()
    if re.search(
        r"\b(indirect|indirectly|multi.hop|acquisition|acquired.*partner|across documents|chain|through|cross.document)\b",
        q,
    ):
        return "hybrid", "Multi-hop or cross-document language detected"
    if re.search(r"\b(founded|founder|acquired|partnered|relationship|connected|owns|works at)\b", q):
        return "graph", "Explicit entity relationship question"
    return "vector", "Semantic or simple factual question"
