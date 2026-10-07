import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from walkjournal.mailbox import MemoryStore, make_handler
from walkjournal.notes import load_notes
from walkjournal.pull import pull
from tests.test_notes import CT, multipart

INGEST, PULL = "i" * 20, "p" * 20


@pytest.fixture
def mailbox():
    store = MemoryStore()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store, INGEST, PULL))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield store, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def post(url, body, headers=None):
    req = urllib.request.Request(url, body, headers or {})
    return urllib.request.urlopen(req)


def send_note(base, text="Heron by the bridge", ms="1791251811058", audio=b"audio"):
    return post(f"{base}/hook/{INGEST}", multipart({"transcription": text, "recordedAt": ms}, audio),
                {"Content-Type": CT})


def test_webhook_stores_note_and_retry_is_not_duplicated(mailbox):
    store, base = mailbox
    send_note(base)
    send_note(base)
    assert len(store.rows) == 1


def test_wrong_token_is_rejected_and_nothing_stored(mailbox):
    store, base = mailbox
    with pytest.raises(urllib.error.HTTPError) as e:
        post(f"{base}/hook/wrong", multipart({"recordedAt": "1"}), {"Content-Type": CT})
    assert e.value.code == 404 and not store.rows


def test_test_event_is_acknowledged_but_not_stored(mailbox):
    store, base = mailbox
    post(f"{base}/hook/{INGEST}", multipart({"transcription": "t", "test": "true", "recordedAt": "1"}),
         {"Content-Type": CT})
    assert not store.rows


def test_bad_webhook_gets_400(mailbox):
    _, base = mailbox
    with pytest.raises(urllib.error.HTTPError) as e:
        post(f"{base}/hook/{INGEST}", b"{}", {"Content-Type": "application/json"})
    assert e.value.code == 400


def test_pull_endpoints_need_the_pull_token(mailbox):
    _, base = mailbox
    for token in ("", "Bearer nope", f"Bearer {INGEST}"):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(urllib.request.Request(f"{base}/notes", headers={"Authorization": token}))
        assert e.value.code == 401


def test_pull_saves_locally_then_deletes_from_mailbox(mailbox, tmp_path):
    store, base = mailbox
    send_note(base, "first", "1000")
    send_note(base, "second", "2000")
    assert pull(base, PULL, tmp_path, wait_s=5) == 2
    notes = load_notes(tmp_path)
    assert [n.transcript for n in notes] == ["first", "second"]
    assert (tmp_path / notes[0].audio_file).read_bytes() == b"audio"
    assert not store.rows
    assert pull(base, PULL, tmp_path, wait_s=5) == 0


def test_pull_keeps_notes_in_mailbox_when_not_saved(mailbox, tmp_path, monkeypatch):
    store, base = mailbox
    send_note(base)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("walkjournal.pull.store_note", boom)
    with pytest.raises(OSError):
        pull(base, PULL, tmp_path, wait_s=5)
    assert len(store.rows) == 1  # never acknowledged, so never deleted


def test_pull_retries_while_mailbox_wakes(tmp_path):
    calls = {"n": 0}
    sleeps = []
    import walkjournal.pull as p

    def flaky(url, token, data=None, timeout=30):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("asleep")
        return {"notes": []}

    orig = p._request
    p._request = flaky
    try:
        assert pull("http://x", "t", tmp_path, wait_s=60, sleep=sleeps.append) == 0
    finally:
        p._request = orig
    assert len(sleeps) == 2


def test_ack_with_bad_body_gets_400(mailbox):
    _, base = mailbox
    with pytest.raises(urllib.error.HTTPError) as e:
        post(f"{base}/notes/ack", b"nope", {"Authorization": f"Bearer {PULL}"})
    assert e.value.code == 400
