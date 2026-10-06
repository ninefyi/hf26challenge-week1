import json

from walkjournal.notes import BadWebhook, load_notes, save_note
import pytest

B = "testboundary"
CT = f"multipart/form-data; boundary={B}"


def multipart(fields: dict, audio: bytes | None = None) -> bytes:
    out = b""
    if audio is not None:
        out += (f'--{B}\r\nContent-Disposition: form-data; name="audio"; filename="a.m4a"\r\n'
                "Content-Type: audio/mp4\r\n\r\n").encode() + audio + b"\r\n"
    for k, v in fields.items():
        out += f'--{B}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    return out + f"--{B}--\r\n".encode()


def test_saves_transcript_audio_and_time(tmp_path):
    body = multipart({"transcription": "Heron by the bridge. ", "recordedAt": "1791251811058", "client": "ring"},
                     audio=b"\x00\x01audio")
    note = save_note(tmp_path, CT, {"X-Index-Trigger": "single-click-hold"}, body)
    assert note.transcript == "Heron by the bridge."
    assert note.recorded_at == "2026-10-06T01:56:51.058000+00:00"
    assert (tmp_path / note.audio_file).read_bytes() == b"\x00\x01audio"
    assert load_notes(tmp_path) == [note]


def test_test_event_is_not_stored(tmp_path):
    body = multipart({"transcription": "Index webhook test event", "test": "true", "recordedAt": "1"})
    assert save_note(tmp_path, CT, {}, body) is None
    assert load_notes(tmp_path) == []


def test_retry_does_not_duplicate(tmp_path):
    body = multipart({"transcription": "x", "recordedAt": "5"}, audio=b"a")
    assert save_note(tmp_path, CT, {}, body) is not None
    assert save_note(tmp_path, CT, {}, body) is None
    assert len(load_notes(tmp_path)) == 1


def test_note_without_audio_still_saved(tmp_path):
    note = save_note(tmp_path, CT, {}, multipart({"transcription": "idea", "recordedAt": "7"}))
    assert note.audio_file is None


def test_notes_come_back_in_time_order(tmp_path):
    save_note(tmp_path, CT, {}, multipart({"transcription": "second", "recordedAt": "2000"}))
    save_note(tmp_path, CT, {}, multipart({"transcription": "first", "recordedAt": "1000"}))
    assert [n.transcript for n in load_notes(tmp_path)] == ["first", "second"]


def test_rejects_non_multipart_and_missing_time(tmp_path):
    with pytest.raises(BadWebhook):
        save_note(tmp_path, "application/json", {}, b"{}")
    with pytest.raises(BadWebhook):
        save_note(tmp_path, CT, {}, multipart({"transcription": "x"}))
