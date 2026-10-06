"""HTTP receiver for the Pebble app webhook.

Run: uv run python -m walkjournal.receiver [--port 8787] [--data data]
Point the Pebble app's webhook at http://<this-machine-lan-ip>:8787/hook
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .notes import BadWebhook, save_note


def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                note = save_note(root, self.headers.get("Content-Type", ""), dict(self.headers), body)
            except BadWebhook as e:
                print(f"rejected: {e}", flush=True)
                self._reply(400, b'{"ok":false}')
                return
            if note:
                print(f"saved {note.id}: {note.transcript[:60]!r}", flush=True)
            else:
                print("ignored (test event or duplicate)", flush=True)
            self._reply(200, b'{"ok":true}')

        def _reply(self, code: int, payload: bytes):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--data", type=Path, default=Path("data"))
    args = ap.parse_args()
    print(f"listening on 0.0.0.0:{args.port}, storing in {args.data}/", flush=True)
    HTTPServer(("0.0.0.0", args.port), make_handler(args.data)).serve_forever()


if __name__ == "__main__":
    main()
