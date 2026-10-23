import re

from backend.reasoning.answers import INSUFFICIENT


def local_answer(question, evidence, max_depth=3):
    """Same evidence-only deterministic generator for every retrieval mode; no database access.

    Literal fact joins stand in for language reasoning only in this explicitly non-LLM mode.
    Structured graph paths remain exclusively database retrieval outputs.
    """
    from backend.knowledge_graph.extraction import canonical
    from backend.tests.literal_extraction import VERBS, extract_literal_facts

    q = canonical(question)
    required = {kind for verb, kind in VERBS.items() if verb in q}
    for word, kind in {
        "acquisition": "ACQUIRED",
        "partnership": "PARTNERED_WITH",
        "founder": "FOUNDED",
        "acquire": "ACQUIRED",
    }.items():
        if word in q:
            required.add(kind)
    multi = bool(re.search(r"\b(indirect|indirectly|through|chain|acquisition)\b", q))
    names, facts = {}, []
    for item in evidence:
        extraction = extract_literal_facts(item.text, list(VERBS.values()))
        names.update({e.id: e.name for e in extraction.entities})
        facts.extend((r, item) for r in extraction.relationships)
    anchors = [
        id for id, name in names.items() if re.search(r"(?<!\w)" + re.escape(canonical(name)) + r"(?!\w)", q)
    ]
    if not anchors or not required:
        return INSUFFICIENT, []
    candidates = []
    frontier = [(id, [id], []) for id in anchors]
    for depth in range(1, max_depth + 1):
        following = []
        for current, visited, chain in frontier[:100]:
            for relation, item in facts:
                # Forward joins for multi-hop; inverse single facts support "Who founded X?".
                nxt = (
                    relation.target
                    if relation.source == current
                    else (relation.source if not multi and relation.target == current else None)
                )
                if not multi:
                    name = re.escape(canonical(names[current]))
                    incoming = re.search(
                        r"(?:who|which\s+\w+|what\s+\w+)\s+"
                        r"(?:founded|acquired|owns|developed|created|partnered with|works at|is associated with)\s+"
                        + name
                        + r"(?!\w)",
                        q,
                    )
                    outgoing = re.search(
                        name
                        + r"\s+(?:acquire|acquired|own|owns|found|founded|develop|developed|create|created|partner|partnered)\b",
                        q,
                    )
                    nxt = (
                        relation.source
                        if incoming and relation.target == current
                        else relation.target
                        if outgoing and relation.source == current
                        else None
                    )
                if nxt is None or nxt in visited:
                    continue
                joined = [*chain, (relation, item)]
                if required <= {r.type for r, _ in joined} and (not multi or depth >= 2):
                    candidates.append((nxt, joined))
                if multi and len(following) < 100:
                    following.append((nxt, [*visited, nxt], joined))
        frontier = following
        if not multi or not frontier:
            break
    if not candidates:
        return INSUFFICIENT, []
    terminal, chain = max(candidates, key=lambda item: len(item[1]))
    ids = {item.chunk_id for _, item in chain}
    quotes = " ".join(dict.fromkeys(r.evidence for r, _ in chain))
    return f"{names[terminal]}. Supporting facts: {quotes}", [e for e in evidence if e.chunk_id in ids]
