import re

from backend.knowledge_graph.extraction import entity_id, validate_extraction
from backend.models.schemas import EntityInput, Extraction, RelationshipInput

# Explicitly limited local extraction: it recognizes these literal declarative facts only.
VERBS = {
    "founded": "FOUNDED",
    "works at": "WORKS_AT",
    "acquired": "ACQUIRED",
    "partnered with": "PARTNERED_WITH",
    "developed": "DEVELOPED",
    "is located in": "LOCATED_IN",
    "created": "CREATED",
    "owns": "OWNS",
    "is associated with": "ASSOCIATED_WITH",
}


def extract_literal_facts(text: str, allowed: list[str]) -> Extraction:
    entities, relationships = {}, []
    pattern = r"^([\w][\w &\-]*?)\s+(" + "|".join(VERBS) + r")\s+([\w][\w &\-]*?)[.!]?$"
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text.strip()):
        match = re.match(pattern, sentence.strip())
        if not match:
            continue
        source, verb, target = match.groups()
        if VERBS[verb] not in allowed:
            continue
        # Organization is conservative, person heuristic applies only to literal founders.
        kinds = [
            "Person" if verb == "founded" and " " in source else "Organization",
            "Location" if verb == "is located in" else "Organization",
        ]
        ids = []
        for name, kind in zip((source, target), kinds):
            id = entity_id(name, kind)
            entities[id] = EntityInput(id=id, name=name, type=kind)
            ids.append(id)
        relationships.append(
            RelationshipInput(
                source=ids[0], target=ids[1], type=VERBS[verb], evidence=sentence.strip(), confidence=1
            )
        )
    return validate_extraction(
        Extraction(entities=list(entities.values()), relationships=relationships), text, allowed
    )
