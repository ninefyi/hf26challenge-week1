"""Parse a Pebble Index webhook request and store it as a Note.

A Note is one ring recording: the phone's transcript, the audio, and when it was recorded.
The audio file is kept as ground truth; notes.ndjson is the index.
"""
import hashlib
import json
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path


@dataclass(frozen=True)
class Note:
    id: str
    recorded_at_ms: int
    recorded_at: str  # ISO 8601, UTC
    transcript: str
    audio_file: str | None
    trigger: str | None
    stored_at_ms: int | None = None  # when this computer saved it; older notes have none


class BadWebhook(ValueError):
    pass


def parse_webhook(content_type: str, headers: dict, body: bytes):
    """Return (fields, audio_bytes) from the multipart body, or raise BadWebhook."""
    if not content_type.startswith("multipart/form-data"):
        raise BadWebhook(f"unexpected content type: {content_type}")
    raw = b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    fields, audio = {}, None
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        if name == "audio":
            audio = payload
        elif name:
            fields[name] = payload.decode("utf-8", "replace")
    return fields, audio


def read_webhook(content_type: str, headers: dict, body: bytes) -> tuple[Note, bytes | None] | None:
    """Turn a webhook request into a Note and its audio. None for the app's test events."""
    fields, audio = parse_webhook(content_type, headers, body)
    if fields.get("test") == "true" or headers.get("X-Index-Test") == "true":
        return None
    try:
        recorded_at_ms = int(fields["recordedAt"])
    except (KeyError, ValueError):
        raise BadWebhook("missing or invalid recordedAt")

    # Same recording retried by the phone gets the same id.
    digest = hashlib.sha256(str(recorded_at_ms).encode() + (audio or b"")).hexdigest()[:12]
    note = Note(
        id=f"{recorded_at_ms}-{digest}",
        recorded_at_ms=recorded_at_ms,
        recorded_at=datetime.fromtimestamp(recorded_at_ms / 1000, timezone.utc).isoformat(),
        transcript=fields.get("transcription", "").strip(),
        audio_file=None,
        trigger=headers.get("X-Index-Trigger"),
    )
    return note, audio


def store_note(root: Path, note: Note, audio: bytes | None) -> Note | None:
    """Write the Note to disk. Returns None if it is already stored."""
    index = root / "notes.ndjson"
    if index.exists() and any(
        json.loads(line)["id"] == note.id for line in index.read_text().splitlines() if line
    ):
        return None

    audio_file = None
    if audio:
        (root / "audio").mkdir(parents=True, exist_ok=True)
        audio_file = f"audio/{note.id}.m4a"
        (root / audio_file).write_bytes(audio)  # audio first, so an index line never points at nothing

    stored = replace(note, audio_file=audio_file, stored_at_ms=int(time.time() * 1000))
    root.mkdir(parents=True, exist_ok=True)
    with index.open("a") as f:
        f.write(json.dumps(asdict(stored), ensure_ascii=False) + "\n")
    return stored


def save_note(root: Path, content_type: str, headers: dict, body: bytes) -> Note | None:
    """Store a webhook request as a Note. None for test events and duplicates."""
    parsed = read_webhook(content_type, headers, body)
    return store_note(root, *parsed) if parsed else None


def load_notes(root: Path) -> list[Note]:
    index = root / "notes.ndjson"
    if not index.exists():
        return []
    notes = [Note(**json.loads(line)) for line in index.read_text().splitlines() if line]
    return sorted(notes, key=lambda n: n.recorded_at_ms)
