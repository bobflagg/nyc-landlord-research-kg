"""The retrieval cache (design note 0028, W3): SQLite under data/cache/ (gitignored), keyed by the normalized request, storing the response, the original
retrieval time and a content hash. A hit reports the original time and cached true, so 'retrieved just now' and 'as of the snapshot' never blur.
Time to live: a day for searches, a week for documents and registry records. Replay fixtures load into the same store."""
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from etl.config import ROOT

DEFAULT_PATH = ROOT / "data" / "cache" / "web.sqlite"
TTL = {"search": 24 * 3600, "extract": 7 * 24 * 3600, "registry": 7 * 24 * 3600}


def request_key(kind: str, params: dict) -> str:
    return hashlib.sha256(json.dumps({"kind": kind, **params}, sort_keys=True, default=str).encode()).hexdigest()


class Cache:
    def __init__(self, path: Path | str | None = None):
        """path None: WEB_CACHE_PATH if set, else data/cache/web.sqlite; ':memory:' for a throwaway store."""
        self.path = str(path or os.environ.get("WEB_CACHE_PATH") or DEFAULT_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, kind TEXT, request TEXT, response TEXT, retrieved_at TEXT, stored REAL, content_hash TEXT)")

    def get(self, kind: str, params: dict, ignore_ttl: bool = False) -> dict | None:
        r = self.db.execute("SELECT response, retrieved_at, stored FROM responses WHERE key = ?", (request_key(kind, params),)).fetchone()
        if r is None or (not ignore_ttl and time.time() - r[2] > TTL[kind]):
            return None
        return {"response": json.loads(r[0]), "retrieved_at": r[1]}

    def put(self, kind: str, params: dict, response: dict, retrieved_at: str) -> None:
        body = json.dumps(response, sort_keys=True, default=str)
        self.db.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?,?,?)", (request_key(kind, params), kind, json.dumps(params, sort_keys=True, default=str), body, retrieved_at,
                                                                                  time.time(), hashlib.sha256(body.encode()).hexdigest()))
        self.db.commit()

    def load_fixtures(self, path: Path | str) -> int:
        """Fixtures: a JSON list of {kind, params, response, retrieved_at}. They are stored as fresh, for replay."""
        items = json.loads(Path(path).read_text())
        for i in items:
            self.put(i["kind"], i["params"], i["response"], i["retrieved_at"])
        return len(items)

    def dump(self, path: Path | str) -> int:
        """Write every stored response as a fixture list (the form load_fixtures reads)."""
        rows = self.db.execute("SELECT kind, request, response, retrieved_at FROM responses ORDER BY key").fetchall()
        Path(path).write_text(json.dumps([{"kind": k, "params": json.loads(q), "response": json.loads(r), "retrieved_at": a} for k, q, r, a in rows], indent=1, sort_keys=True) + "\n")
        return len(rows)
