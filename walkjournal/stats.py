"""Summarise stored Notes as Markdown numbers for the write-up.

Run: uv run python -m walkjournal.stats [--data data] [--since 2026-10-08] [--script drafts/rehearsal-notes.md]

With --script, each line you were meant to say is matched to the closest Note, so you can see how
many the phone heard exactly, nearly, badly or not at all. Matching is by similarity, not by order.
"""
import argparse
import re
import statistics
import struct
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from .extract import is_filler
from .journal import SGT, clock
from .notes import Note, load_notes
from .walks import group_walks

EXACT, CLOSE, POOR = 0.95, 0.7, 0.5


def audio_seconds(path: Path) -> float | None:
    """Duration from an m4a's movie header; None if it cannot be read."""
    try:
        data = path.read_bytes()
        i = data.index(b"mvhd") + 4
        version = data[i]
        if version == 1:
            timescale, duration = struct.unpack(">IQ", data[i + 20 : i + 32])
        else:
            timescale, duration = struct.unpack(">II", data[i + 12 : i + 20])
        return duration / timescale if timescale else None
    except (OSError, ValueError, struct.error):
        return None


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def similarity(a: str, b: str) -> float:
    """1.0 only when the words are identical (ignoring case and punctuation); otherwise below EXACT."""
    a, b = norm(a), norm(b)
    return 1.0 if a == b else min(SequenceMatcher(None, a, b).ratio(), EXACT - 0.01)


def script_lines(path: Path) -> list[str]:
    """Quoted 'Say this' cells from the rehearsal table, in order."""
    lines = []
    for row in path.read_text().splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0].isdigit() and cells[1].startswith('"') and cells[1].endswith('"'):
            lines.append(cells[1].strip('"'))
    return lines


def match_script(lines: list[str], notes: list[Note]):
    """For each script line, (line, best note or None, ratio)."""
    out = []
    for line in lines:
        best = max(notes, key=lambda n: similarity(line, n.transcript), default=None)
        out.append((line, best, similarity(line, best.transcript) if best else 0.0))
    return out


def grade(ratio: float) -> str:
    return "exact" if ratio >= EXACT else "close" if ratio >= CLOSE else "poor" if ratio >= POOR else "missing"


def report(notes: list[Note], data: Path, script: list[str] | None = None) -> str:
    if not notes:
        return "No notes.\n"
    walks = group_walks(notes)
    durations = [d for n in notes if n.audio_file and (d := audio_seconds(data / n.audio_file)) is not None]
    words = [len(n.transcript.split()) for n in notes]
    gaps = [(b.recorded_at_ms - a.recorded_at_ms) / 1000 for a, b in zip(notes, notes[1:])]
    day = datetime.fromtimestamp(notes[0].recorded_at_ms / 1000, SGT).strftime("%Y-%m-%d")
    out = [
        f"## Notes summary ({day}, UTC+8)",
        "",
        f"- Notes received: **{len(notes)}** in {len(walks)} walk(s), {clock(notes[0].recorded_at_ms)} to {clock(notes[-1].recorded_at_ms)}",
        f"- Words per note: mean {statistics.mean(words):.1f}, shortest {min(words)}, longest {max(words)}",
        f"- Filler or too short to use (< 3 words, or one word repeated): **{sum(is_filler(n.transcript) for n in notes)}**",
        f"- Without audio: {sum(1 for n in notes if not n.audio_file)}",
    ]
    if durations:
        out.append(
            f"- Audio length: total {sum(durations):.0f} s, mean {statistics.mean(durations):.1f} s, "
            f"shortest {min(durations):.1f} s, longest {max(durations):.1f} s"
        )
    if gaps:
        out.append(f"- Gap between notes: median {statistics.median(gaps):.0f} s, longest {max(gaps):.0f} s")
    waits = [(n.stored_at_ms - n.recorded_at_ms) / 1000 for n in notes if n.stored_at_ms]
    if waits:
        out.append(
            f"- Recorded to saved on this computer (includes waiting for me to run pull): "
            f"median {statistics.median(waits):.0f} s, longest {max(waits):.0f} s"
        )
    if script:
        matched = match_script(script, notes)
        counts = {g: sum(grade(r) == g for _, _, r in matched) for g in ("exact", "close", "poor", "missing")}
        out += [
            "",
            f"## Phone transcript vs what I said ({len(script)} script lines)",
            "",
            f"exact **{counts['exact']}**, close {counts['close']}, poor {counts['poor']}, missing {counts['missing']}",
            "",
            "| Said | Heard | Match |",
            "|---|---|---|",
        ]
        for line, note, ratio in matched:
            heard = note.transcript if note and ratio >= POOR else "(nothing close)"
            out.append(f"| {line} | {heard} | {grade(ratio)} ({ratio:.2f}) |")
        used = {id(n) for _, n, r in matched if n and r >= POOR}
        extra = [n for n in notes if id(n) not in used]
        if extra:
            out += ["", "Notes that matched no script line: " + "; ".join(f'"{n.transcript}"' for n in extra)]
    out += ["", "Not measured here (write these down by hand): resends from the app, cold-start result, rows edited in the review screen."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--since", help="only notes on or after this date, YYYY-MM-DD (UTC+8)")
    ap.add_argument("--script", type=Path, help="rehearsal-notes.md, to compare what the phone heard")
    args = ap.parse_args()
    notes = load_notes(args.data)
    if args.since:
        start = datetime.fromisoformat(args.since).replace(tzinfo=SGT).timestamp() * 1000
        notes = [n for n in notes if n.recorded_at_ms >= start]
    print(report(notes, args.data, script_lines(args.script) if args.script else None))


if __name__ == "__main__":
    main()
