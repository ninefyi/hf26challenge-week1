"""Spike: accept any webhook POST from the Pebble app and log it raw.

Run: python walkjournal/spike_receiver.py   (listens on 0.0.0.0:8787)
Every request is appended to spike_log.ndjson with headers and body (base64 if not text).
"""
import base64, json, time
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = "spike_log.ndjson"


class Handler(BaseHTTPRequestHandler):
    def _handle(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        try:
            text = body.decode("utf-8")
            rec_body = {"text": text}
        except UnicodeDecodeError:
            rec_body = {"base64": base64.b64encode(body).decode()}
        rec = {
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "method": self.command,
            "path": self.path,
            "headers": dict(self.headers),
            "bytes": n,
            **rec_body,
        }
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{rec['received_at']} {self.command} {self.path} {n} bytes "
              f"{self.headers.get('Content-Type')}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    do_POST = do_PUT = do_GET = _handle

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("listening on 0.0.0.0:8787")
    HTTPServer(("0.0.0.0", 8787), Handler).serve_forever()
