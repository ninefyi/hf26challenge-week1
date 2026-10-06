"""Draft and render the Journal for one Walk. The Walker's own Notes stay visible."""
from datetime import datetime, timedelta, timezone

from .extract import Observation, extract_observations, write_paragraph
from .walks import Walk

SGT = timezone(timedelta(hours=8))  # author-local; change if you walk elsewhere


def clock(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, SGT).strftime("%H:%M")


def walk_label(walk: Walk) -> str:
    day = datetime.fromtimestamp(walk.start_ms / 1000, SGT).strftime("%Y-%m-%d %H:%M")
    return f"{day}, {len(walk.notes)} notes"


def walk_stamp(walk: Walk) -> str:
    return datetime.fromtimestamp(walk.start_ms / 1000, SGT).strftime("%Y-%m-%d_%H%M")


def draft_walk(walk: Walk, llm) -> tuple[str, list[Observation]]:
    observations = [o for n in walk.notes for o in extract_observations(n, llm)]
    return write_paragraph(list(walk.notes), llm), observations


def render_journal(walk: Walk, paragraph: str, observations: list[Observation], confirmed: bool = False) -> str:
    day = datetime.fromtimestamp(walk.start_ms / 1000, SGT).strftime("%A %-d %B %Y")
    status = "Reviewed and confirmed by me." if confirmed else "Draft, not yet reviewed."
    lines = [
        f"# Walk, {day}",
        f"*{clock(walk.start_ms)} to {clock(walk.end_ms)}, {len(walk.notes)} notes. "
        f"Paragraph and observations drafted by a local model; the notes below are my own words. {status}*",
        "",
        paragraph,
        "",
        "## Observations",
    ]
    if not observations:
        lines.append("_None._")
    for o in observations:
        where = f" ({o.where})" if o.where else ""
        lines.append(f"- **{o.kind}**: {o.what}{where} — “{o.quote}”")
    lines += ["", "## My notes"]
    for n in walk.notes:
        lines.append(f"- {clock(n.recorded_at_ms)} {n.transcript}")
    return "\n".join(lines) + "\n"


def build_journal(walk: Walk, llm) -> str:
    paragraph, observations = draft_walk(walk, llm)
    return render_journal(walk, paragraph, observations)
