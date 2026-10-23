"""Small durable control-plane store. Evidence and vectors live exclusively in Neo4j."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.path = directory / "control.sqlite3"
        with self.connection() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL,
              size INTEGER, mime TEXT, status TEXT, progress INTEGER DEFAULT 0, chunks INTEGER DEFAULT 0,
              error TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS queries (id TEXT PRIMARY KEY, created_at TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, created_at TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS extraction_cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS extraction_cache_documents (
              key TEXT NOT NULL, document_id TEXT NOT NULL, PRIMARY KEY(key,document_id));
            CREATE INDEX IF NOT EXISTS extraction_cache_document ON extraction_cache_documents(document_id);
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT);
            """)
            columns = {r["name"] for r in db.execute("PRAGMA table_info(documents)")}
            if "processing_metadata" not in columns:
                db.execute("ALTER TABLE documents ADD COLUMN processing_metadata TEXT NOT NULL DEFAULT '{}'")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_document(self, id, name, digest, size, mime):
        with self.connection() as db:
            db.execute(
                "INSERT INTO documents (id,name,sha256,size,mime,status,progress,chunks,error,created_at,updated_at) VALUES (?,?,?,?,?,?,0,0,NULL,?,?)",
                (id, name, digest, size, mime, "queued", now(), now()),
            )
        return self.document(id)

    def document(self, id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (id,)).fetchone()
            return self.decode_document(row) if row else None

    def duplicate(self, digest):
        with self.connection() as db:
            row = db.execute("SELECT * FROM documents WHERE sha256=?", (digest,)).fetchone()
            return self.decode_document(row) if row else None

    def documents(self):
        with self.connection() as db:
            return [
                self.decode_document(r)
                for r in db.execute("SELECT * FROM documents ORDER BY created_at DESC")
            ]

    def update_document(self, id, status, progress, chunks=0, error=None):
        with self.connection() as db:
            db.execute(
                "UPDATE documents SET status=?,progress=?,chunks=?,error=?,updated_at=? WHERE id=?",
                (status, progress, chunks, error, now(), id),
            )

    def remove_document(self, id):
        with self.connection() as db:
            db.execute("DELETE FROM documents WHERE id=?", (id,))
            db.execute("DELETE FROM extraction_cache_documents WHERE document_id=?", (id,))
            db.execute(
                "DELETE FROM extraction_cache WHERE key NOT IN (SELECT key FROM extraction_cache_documents)"
            )

    def record(self, table, id, payload):
        assert table in ("queries", "evaluations")
        with self.connection() as db:
            db.execute(f"INSERT INTO {table} VALUES (?,?,?)", (id, now(), json.dumps(payload)))

    def records(self, table, limit=100):
        assert table in ("queries", "evaluations")
        with self.connection() as db:
            return [
                json.loads(r["payload"])
                for r in db.execute(f"SELECT payload FROM {table} ORDER BY created_at DESC LIMIT ?", (limit,))
            ]

    def query_aggregates(self):
        with self.connection() as db:
            return [
                dict(r)
                for r in db.execute("""
            SELECT json_extract(payload, '$.strategy') AS strategy, COUNT(*) AS count,
            AVG(json_extract(payload, '$.latency_ms')) AS average_latency_ms
            FROM queries GROUP BY strategy""")
            ]

    def saved_settings(self):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM settings WHERE id=1").fetchone()
            return json.loads(row[0]) if row else {}

    def save_settings(self, settings):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (1,?)", (json.dumps(settings),))

    def purge_evidence(self, document_id):
        """Delete saved responses/runs containing deleted or reprocessed source text."""
        with self.connection() as db:
            for table in ("queries", "evaluations"):
                records = db.execute(f"SELECT id,payload FROM {table}").fetchall()
                for row in records:
                    payload = json.loads(row["payload"])
                    responses = (
                        [payload] if table == "queries" else [r.get("response", {}) for r in payload["rows"]]
                    )
                    if any(
                        e.get("document_id") == document_id
                        for response in responses
                        for e in response.get("evidence", [])
                    ):
                        db.execute(f"DELETE FROM {table} WHERE id=?", (row["id"],))

    @staticmethod
    def decode_document(row):
        result = dict(row)
        result["processing_metadata"] = json.loads(result.get("processing_metadata", "{}"))
        return result

    def processing_metadata(self, id, settings):
        metadata = {
            k: getattr(settings, k)
            for k in (
                "llm_provider",
                "llm_model",
                "extraction_model",
                "ollama_context_length",
                "embedding_model",
                "chunk_size",
                "chunk_overlap",
                "relationship_types",
            )
        }
        metadata.update(started_at=now(), pipeline_version="graphmind-ollama-v2")
        with self.connection() as db:
            db.execute("UPDATE documents SET processing_metadata=? WHERE id=?", (json.dumps(metadata), id))

    def extraction_cache(self, key, value=None, document_id=None):
        with self.connection() as db:
            if document_id is not None:
                db.execute(
                    "INSERT OR IGNORE INTO extraction_cache_documents VALUES (?,?)", (key, document_id)
                )
            if value is not None:
                db.execute("INSERT OR REPLACE INTO extraction_cache VALUES (?,?)", (key, json.dumps(value)))
                return value
            row = db.execute("SELECT payload FROM extraction_cache WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def extraction_diagnostics(self, document_id, diagnostics):
        """Persist safe partial-extraction warnings alongside the document status."""
        with self.connection() as db:
            db.execute(
                "UPDATE documents SET processing_metadata=json_set(processing_metadata, "
                "'$.extraction_diagnostics', json(?)) WHERE id=?",
                (json.dumps(diagnostics), document_id),
            )
