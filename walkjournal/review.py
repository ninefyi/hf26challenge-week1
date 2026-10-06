"""Review table logic: Observations <-> editable rows, kept free of any UI code."""
from .extract import KINDS, Observation
from .walks import Walk

HEADERS = ["Keep", "Note", "Kind", "What", "Where", "Quote"]


def to_rows(walk: Walk, observations: list[Observation]) -> list[list]:
    index = {n.id: i + 1 for i, n in enumerate(walk.notes)}
    return [[True, index[o.note_id], o.kind, o.what, o.where or "", o.quote] for o in observations]


def from_rows(walk: Walk, rows) -> list[Observation]:
    """Rows the Walker kept, in order. Rows with a bad note number or kind are skipped."""
    out = []
    for keep, num, kind, what, where, quote in rows:
        try:
            note = walk.notes[int(num) - 1]
        except (ValueError, TypeError, IndexError):
            continue
        if not keep or kind not in KINDS or not str(what).strip():
            continue
        where = str(where).strip()
        out.append(Observation(note.id, kind, str(what).strip(), where if where and where != "nan" else None, str(quote)))
    return out
