"""Mailbox: a small public web service that holds Notes until the Walker pulls them.

Runs on Render (web service + Postgres). It never runs a model.

  POST /hook/<INGEST_TOKEN>         the Pebble app's webhook
  GET  /notes?limit=N               pending Notes with audio (Authorization: Bearer <PULL_TOKEN>)
  POST /notes/ack  {"ids": [...]}   delete Notes the Walker has saved (same bearer token)
  GET  /health

Env: DATABASE_URL, INGEST_TOKEN, PULL_TOKEN, PORT.
"""
import base64
import hmac
import json
import os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .notes import BadWebhook, Note, read_webhook

MAX_BODY = 8 * 1024 * 1024
MAX_PULL = 50


class PostgresStore:
    def __init__(self, url: str):
        import psycopg  # only the deployed service needs it

        self.psycopg, self.url = psycopg, url
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS notes (
                     id text PRIMARY KEY, recorded_at_ms bigint NOT NULL, recorded_at text NOT NULL,
                     transcript text NOT NULL, trigger text, audio bytea,
                     received_at timestamptz NOT NULL DEFAULT now())"""
            )

    def _connect(self):
        return self.psycopg.connect(self.url)

    def add(self, note: Note, audio: bytes | None) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO notes (id, recorded_at_ms, recorded_at, transcript, trigger, audio) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                (note.id, note.recorded_at_ms, note.recorded_at, note.transcript, note.trigger, audio),
            )
            return cur.rowcount == 1

    def pending(self, limit: int) -> list[tuple[Note, bytes | None]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, recorded_at_ms, recorded_at, transcript, trigger, audio FROM notes "
                "ORDER BY recorded_at_ms LIMIT %s",
                (limit,),
            ).fetchall()
        return [(Note(r[0], r[1], r[2], r[3], None, r[4]), bytes(r[5]) if r[5] else None) for r in rows]

    def delete(self, ids: list[str]) -> int:
        with self._connect() as conn:
            return conn.execute("DELETE FROM notes WHERE id = ANY(%s)", (ids,)).rowcount


class MemoryStore:
    """For tests and local trials."""

    def __init__(self):
        self.rows: dict[str, tuple[Note, bytes | None]] = {}

    def add(self, note, audio):
        if note.id in self.rows:
            return False
        self.rows[note.id] = (note, audio)
        return True

    def pending(self, limit):
        return sorted(self.rows.values(), key=lambda r: r[0].recorded_at_ms)[:limit]

    def delete(self, ids):
        return sum(self.rows.pop(i, None) is not None for i in ids)


def _same(a: str, b: str) -> bool:
    return bool(a) and hmac.compare_digest(a.encode(), b.encode())


def make_handler(store, ingest_token: str, pull_token: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> bytes | None:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                self._send(413, {"ok": False})
                return None
            return self.rfile.read(n)

        def _authorised(self) -> bool:
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if _same(token, pull_token):
                return True
            self._send(401, {"ok": False})
            return False

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/health":
                self._send(200, {"ok": True})
            elif path == "/notes":
                if not self._authorised():
                    return
                limit = MAX_PULL
                for kv in query.split("&"):
                    if kv.startswith("limit=") and kv[6:].isdigit():
                        limit = max(1, min(int(kv[6:]), MAX_PULL))
                notes = []
                pending = store.pending(limit)
                print(f"pull: {len(pending)} pending", flush=True)
                for note, audio in pending:
                    d = asdict(note)
                    d["audio_b64"] = base64.b64encode(audio).decode() if audio else None
                    notes.append(d)
                self._send(200, {"notes": notes})
            else:
                self._send(404, {"ok": False})

        def do_POST(self):
            path = self.path.split("?")[0]
            if path.startswith("/hook/"):
                if not _same(path[len("/hook/"):], ingest_token):
                    print("hook: wrong token (check the URL in the Pebble app)", flush=True)
                    self._send(404, {"ok": False})
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    parsed = read_webhook(self.headers.get("Content-Type", ""), dict(self.headers), body)
                except BadWebhook as e:
                    print(f"rejected: {e}", flush=True)
                    self._send(400, {"ok": False})
                    return
                if parsed is None:
                    print("hook: test event, not stored", flush=True)
                elif store.add(*parsed):
                    print(f"hook: stored {parsed[0].id}", flush=True)
                else:
                    print(f"hook: duplicate {parsed[0].id}, ignored", flush=True)
                self._send(200, {"ok": True})
            elif path == "/notes/ack":
                if not self._authorised():
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    ids = [str(i) for i in json.loads(body)["ids"]]
                except (ValueError, KeyError, TypeError):
                    self._send(400, {"ok": False})
                    return
                deleted = store.delete(ids)
                print(f"ack: deleted {deleted} of {len(ids)}", flush=True)
                self._send(200, {"deleted": deleted})
            else:
                self._send(404, {"ok": False})

        def log_message(self, *args):
            pass

    return Handler


def main():
    ingest, pull = os.environ["INGEST_TOKEN"], os.environ["PULL_TOKEN"]
    if len(ingest) < 16 or len(pull) < 16:
        raise SystemExit("INGEST_TOKEN and PULL_TOKEN must each be at least 16 characters")
    store = PostgresStore(os.environ["DATABASE_URL"])
    port = int(os.environ.get("PORT", "10000"))
    print(f"mailbox listening on {port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(store, ingest, pull)).serve_forever()


if __name__ == "__main__":
    main()
