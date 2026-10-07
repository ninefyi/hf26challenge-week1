"""Pull new Notes from the Mailbox onto this computer, then tell the Mailbox to delete them.

Run: MAILBOX_URL=https://<service>.onrender.com PULL_TOKEN=... uv run python -m walkjournal.pull

A Note is deleted from the Mailbox only after it is saved here. A free Render service sleeps
when idle and can take about a minute to wake, so the first request retries patiently.
"""
import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .notes import Note, store_note


def _request(url: str, token: str, data: bytes | None = None, timeout: int = 30):
    req = urllib.request.Request(
        url, data, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _with_retries(fn, wait_s: int, sleep=time.sleep):
    deadline = time.monotonic() + wait_s
    while True:
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise SystemExit(f"Mailbox said {e.code}: check MAILBOX_URL and PULL_TOKEN")
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        if time.monotonic() >= deadline:
            raise SystemExit(f"Mailbox not reachable: {err}")
        print("waiting for the Mailbox to wake up...", flush=True)
        sleep(5)


def pull(base_url: str, token: str, root: Path, wait_s: int = 120, sleep=time.sleep) -> int:
    base = base_url.rstrip("/")
    saved = 0
    while True:
        batch = _with_retries(lambda: _request(f"{base}/notes", token, timeout=60), wait_s, sleep)["notes"]
        if not batch:
            return saved
        for d in batch:
            audio = base64.b64decode(d.pop("audio_b64")) if d.get("audio_b64") else None
            if store_note(root, Note(**d), audio):
                saved += 1
        ids = [d["id"] for d in batch]  # every one is now on this computer, new or already there
        _with_retries(lambda: _request(f"{base}/notes/ack", token, json.dumps({"ids": ids}).encode()), wait_s, sleep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--url", default=os.environ.get("MAILBOX_URL"))
    ap.add_argument("--wait", type=int, default=120, help="seconds to wait for the Mailbox to wake")
    args = ap.parse_args()
    token = os.environ.get("PULL_TOKEN")
    if not args.url or not token:
        raise SystemExit("set MAILBOX_URL (or --url) and PULL_TOKEN")
    print(f"pulled {pull(args.url, token, args.data, args.wait)} new notes into {args.data}/")


if __name__ == "__main__":
    main()
