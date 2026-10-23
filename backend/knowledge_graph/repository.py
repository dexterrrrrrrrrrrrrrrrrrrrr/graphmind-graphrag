import hashlib

from neo4j import GraphDatabase

from backend.core.logging import logging
from backend.knowledge_graph.extraction import canonical, entity_id
from backend.models.schemas import Evidence, GraphEdge, GraphNode, GraphPath

log = logging.getLogger(__name__)


def node(value):
    return GraphNode(id=value["id"], name=value["name"], type=value["type"], aliases=value.get("aliases", []))


def edge(value, source, target):
    return GraphEdge(
        id=value["id"],
        source=source,
        target=target,
        type=value["type"],
        evidence=value["evidence"],
        chunk_id=value["chunk_id"],
        document_id=value["document_id"],
        confidence=value["confidence"],
    )


class GraphRepository:
    def __init__(self, settings):
        self.settings = settings
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
            connection_timeout=10,
            connection_acquisition_timeout=15,
            max_transaction_retry_time=15,
        )

    def read(self, query, **params):
        records, _, _ = self.driver.execute_query(query, parameters_=params, routing_="r", database_="neo4j")
        return [r.data() for r in records]

    def write(self, query, **params):
        records, _, _ = self.driver.execute_query(query, parameters_=params, database_="neo4j")
        return [r.data() for r in records]

    def initialize(self):
        self.driver.verify_connectivity()
        for label in ("Document", "Chunk", "Entity"):
            # Labels are constants, never request parameters.
            self.write(
                f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
            )
        self.write("CREATE CONSTRAINT fact_id IF NOT EXISTS FOR ()-[r:FACT]-() REQUIRE r.id IS UNIQUE")
        self.write("CREATE INDEX entity_canonical IF NOT EXISTS FOR (e:Entity) ON (e.canonical)")
        self.write("CREATE INDEX fact_document IF NOT EXISTS FOR ()-[r:FACT]-() ON (r.document_id)")
        self.write("CREATE INDEX chunk_document IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)")
        self.write(
            "CREATE CONSTRAINT embedding_config IF NOT EXISTS FOR (m:EmbeddingConfig) REQUIRE m.id IS UNIQUE"
        )
        rows = self.write(
            """MERGE (m:EmbeddingConfig {id:'active'})
            ON CREATE SET m.model=$model, m.dimension=$dimension
            RETURN m.model AS model, m.dimension AS dimension""",
            model=self.settings.embedding_model,
            dimension=self.settings.embedding_dimension,
        )
        if rows[0] != {
            "model": self.settings.embedding_model,
            "dimension": self.settings.embedding_dimension,
        }:
            raise ValueError("Database embedding model differs from configuration; use a new database")
        from neo4j_graphrag.indexes import create_vector_index

        create_vector_index(
            self.driver,
            name="chunk_embeddings",
            label="Chunk",
            embedding_property="embedding",
            dimensions=self.settings.embedding_dimension,
            similarity_fn="cosine",
            fail_if_exists=False,
            neo4j_database="neo4j",
        )
        self.write("CALL db.awaitIndexes(60)")

    def index_ready(self):
        rows = self.read("SHOW VECTOR INDEXES YIELD name,state WHERE name='chunk_embeddings' RETURN state")
        return bool(rows and rows[0]["state"] == "ONLINE")

    def persist(self, document, chunks, extractions):
        if not chunks or len(chunks) != len(extractions):
            raise ValueError("Every chunk must have a validated extraction")
        if any(len(c["embedding"]) != self.settings.embedding_dimension for c in chunks):
            raise ValueError("Invalid chunk embedding dimension")

        def transaction(tx):
            self._delete(tx, document["id"])
            tx.run(
                "CREATE (d:Document {id:$id,name:$name,sha256:$sha256,created_at:$created_at,status:'indexing'})",
                **{k: document[k] for k in ("id", "name", "sha256", "created_at")},
            ).consume()
            for chunk, extraction in zip(chunks, extractions):
                tx.run(
                    """MATCH (d:Document {id:$document_id})
                    CREATE (c:Chunk) SET c=$chunk CREATE (d)-[:HAS_CHUNK]->(c)""",
                    document_id=document["id"],
                    chunk=chunk,
                ).consume()
                mapping = {}
                for e in extraction.entities:
                    id = entity_id(e.name, e.type)
                    mapping[e.id] = id
                    tx.run(
                        """MATCH (c:Chunk {id:$chunk_id}) MERGE (e:Entity {id:$id})
                        ON CREATE SET e.name=$name,e.canonical=$canonical,e.type=$type,e.aliases=[]
                        SET e.aliases=reduce(acc=e.aliases,a IN $aliases |
                            CASE WHEN a IN acc THEN acc ELSE acc+a END)
                        MERGE (c)-[m:MENTIONS]->(e) SET m.aliases=$aliases""",
                        chunk_id=chunk["id"],
                        id=id,
                        name=e.name,
                        canonical=canonical(e.name),
                        type=e.type,
                        aliases=[canonical(a) for a in e.aliases],
                    ).consume()
                for r in extraction.relationships:
                    rid = hashlib.sha256(
                        f"{mapping[r.source]}:{r.type}:{mapping[r.target]}:{chunk['id']}".encode()
                    ).hexdigest()
                    tx.run(
                        """MATCH (a:Entity {id:$source}),(b:Entity {id:$target})
                        MERGE (a)-[r:FACT {id:$id}]->(b)
                        SET r.type=$type,r.evidence=$evidence,r.chunk_id=$chunk_id,
                            r.document_id=$document_id,r.confidence=$confidence,r.ingested_at=$ingested_at""",
                        source=mapping[r.source],
                        target=mapping[r.target],
                        id=rid,
                        type=r.type,
                        evidence=r.evidence,
                        chunk_id=chunk["id"],
                        document_id=document["id"],
                        confidence=r.confidence,
                        ingested_at=chunk["ingested_at"],
                    ).consume()

        with self.driver.session(database="neo4j") as session:
            session.execute_write(transaction)
        self.write("CALL db.awaitIndexes(60)")
        if not self.index_ready():
            raise RuntimeError("Vector index is not online")
        self.write("MATCH (d:Document {id:$id}) SET d.status='ready'", id=document["id"])

    @staticmethod
    def _delete(tx, id):
        tx.run("MATCH ()-[r:FACT]->() WHERE r.document_id=$id DELETE r", id=id).consume()
        tx.run("MATCH (d:Document {id:$id})-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE c", id=id).consume()
        tx.run("MATCH (d:Document {id:$id}) DETACH DELETE d", id=id).consume()
        tx.run("MATCH (e:Entity) WHERE NOT (e)<-[:MENTIONS]-() DETACH DELETE e").consume()
        tx.run("""MATCH (e:Entity)<-[m:MENTIONS]-(:Chunk)
            WITH e,collect(m.aliases) AS groups
            SET e.aliases=reduce(acc=[],g IN groups | reduce(a=acc,x IN g |
                CASE WHEN x IN a THEN a ELSE a+x END))""").consume()

    def delete(self, id):
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._delete, id)

    def stats(self):
        return self.read("""CALL () { MATCH (d:Document) RETURN count(d) AS documents }
            CALL () { MATCH (c:Chunk) RETURN count(c) AS chunks }
            CALL () { MATCH (e:Entity) RETURN count(e) AS entities }
            CALL () { MATCH ()-[r:FACT]->() RETURN count(r) AS relationships }
            RETURN documents,chunks,entities,relationships""")[0]

    def entities(self, search="", kind=None, document_id=None, limit=100, offset=0):
        return self.read(
            """MATCH (e:Entity) WHERE ($search='' OR e.canonical CONTAINS $search)
            AND ($kind IS NULL OR e.type=$kind)
            AND ($doc IS NULL OR EXISTS { MATCH (:Chunk {document_id:$doc})-[:MENTIONS]->(e) })
            RETURN e{.*} AS entity ORDER BY e.name SKIP $offset LIMIT $limit""",
            search=canonical(search),
            kind=kind,
            doc=document_id,
            limit=limit,
            offset=offset,
        )

    def entity(self, id):
        rows = self.read("MATCH (e:Entity {id:$id}) RETURN e{.*} AS entity", id=id)
        return rows[0]["entity"] if rows else None

    def link(self, question: str):
        # Word-boundary containment, longest exact names/explicit aliases first.
        import re

        q = canonical(question)
        names = self.read(
            """MATCH (e:Entity)
            WHERE ($q CONTAINS e.canonical OR any(a IN e.aliases WHERE $q CONTAINS a))
            AND EXISTS { MATCH (:Document {status:'ready'})-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->(e) }
            RETURN e.id AS id,e.canonical AS name,e.aliases AS aliases
            ORDER BY size(e.canonical) DESC LIMIT 200""",
            q=q,
        )
        found = []
        for e in names:
            matches = [
                n
                for n in [e["name"], *(e["aliases"] or [])]
                if n and re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", q)
            ]
            if matches:
                found.append((max(len(m) for m in matches), e["id"]))
        return [id for _, id in sorted(found, reverse=True)[:10]]

    def traverse(self, ids, depth, limit, allowed=None, document_id=None):
        # Bounded iterative expansion rather than enumerating all database paths before LIMIT.
        depth, limit = min(max(int(depth), 1), 5), min(max(int(limit), 1), 100)
        frontier = []
        for id in ids[:10]:
            e = self.entity(id)
            if e:
                frontier.append(GraphPath(nodes=[node(e)], edges=[]))
        result, seen = [], set()
        for _ in range(depth):
            next_frontier = []
            for path in frontier[:limit]:
                rows = self.read(
                    """MATCH (a:Entity {id:$id})-[r:FACT]-(b:Entity)
                    WHERE r.type IN $allowed AND NOT b.id IN $visited
                    AND EXISTS { MATCH (d:Document {status:'ready'}) WHERE d.id=r.document_id }
                    AND ($doc IS NULL OR r.document_id=$doc)
                    RETURN a{.*} AS a,b{.*} AS b,r{.*} AS r,
                           startNode(r).id AS source,endNode(r).id AS target
                    ORDER BY r.confidence DESC,r.id LIMIT $limit""",
                    id=path.nodes[-1].id,
                    allowed=allowed or self.settings.relationship_types,
                    visited=[n.id for n in path.nodes],
                    doc=document_id,
                    limit=limit,
                )
                for row in rows:
                    key = tuple([e.id for e in path.edges] + [row["r"]["id"]])
                    if key in seen:
                        continue
                    seen.add(key)
                    p = GraphPath(
                        nodes=[*path.nodes, node(row["b"])],
                        edges=[*path.edges, edge(row["r"], row["source"], row["target"])],
                    )
                    result.append(p)
                    next_frontier.append(p)
                    if len(next_frontier) >= limit:
                        break
                if len(next_frontier) >= limit:
                    break
            frontier = next_frontier
            if not frontier:
                break
        return result[: depth * limit]

    def evidence(self, ids):
        rows = self.read(
            """MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document) WHERE c.id IN $ids AND d.status='ready'
            RETURN c.id AS chunk_id,c.document_id AS document_id,d.name AS document_name,
                   c.text AS text,c.page AS page""",
            ids=ids,
        )
        return [Evidence(**r, sources=["graph"]) for r in rows]

    def vector(self, embedding, top_k, threshold):
        rows = self.read(
            """CALL db.index.vector.queryNodes('chunk_embeddings',$k,$embedding)
            YIELD node AS c,score MATCH (d:Document)-[:HAS_CHUNK]->(c)
            WHERE score >= $threshold AND d.status='ready'
            RETURN c.id AS chunk_id,c.document_id AS document_id,d.name AS document_name,
                   c.text AS text,c.page AS page,score ORDER BY score DESC""",
            embedding=embedding,
            k=top_k,
            threshold=threshold,
        )
        return [Evidence(**r, sources=["vector"]) for r in rows]
