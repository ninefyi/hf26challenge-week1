"""Render one Walk as a Markdown Journal. The Walker's own Notes stay visible."""
from datetime import datetime, timedelta, timezone

from .extract import Observation, write_paragraph, extract_observations
from .walks import Walk

SGT = timezone(timedelta(hours=8))  # author-local; change if you walk elsewhere


def _clock(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, SGT).strftime("%H:%M")


def build_journal(walk: Walk, llm) -> str:
    observations = [o for n in walk.notes for o in extract_observations(n, llm)]
    paragraph = write_paragraph(list(walk.notes), llm)
    day = datetime.fromtimestamp(walk.start_ms / 1000, SGT).strftime("%A %-d %B %Y")
    lines = [
        f"# Walk, {day}",
        f"*{_clock(walk.start_ms)} to {_clock(walk.end_ms)}, {len(walk.notes)} notes. "
        "Paragraph and observations written by a local model; the notes below are my own words.*",
        "",
        paragraph,
        "",
        "## Observations",
    ]
    by_note: dict[str, list[Observation]] = {}
    for o in observations:
        by_note.setdefault(o.note_id, []).append(o)
    if not observations:
        lines.append("_None extracted._")
    for o in observations:
        where = f" ({o.where})" if o.where else ""
        lines.append(f"- **{o.kind}**: {o.what}{where} — “{o.quote}”")
    lines += ["", "## My notes"]
    for n in walk.notes:
        lines.append(f"- {_clock(n.recorded_at_ms)} {n.transcript}")
    return "\n".join(lines) + "\n"
