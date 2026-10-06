"""Group Notes into Walks: a new Walk starts after a long gap between Notes."""
from dataclasses import dataclass

from .notes import Note

GAP_MS = 30 * 60 * 1000


@dataclass(frozen=True)
class Walk:
    notes: tuple[Note, ...]

    @property
    def start_ms(self) -> int:
        return self.notes[0].recorded_at_ms

    @property
    def end_ms(self) -> int:
        return self.notes[-1].recorded_at_ms


def group_walks(notes: list[Note], gap_ms: int = GAP_MS) -> list[Walk]:
    walks: list[list[Note]] = []
    for note in sorted(notes, key=lambda n: n.recorded_at_ms):
        if walks and note.recorded_at_ms - walks[-1][-1].recorded_at_ms <= gap_ms:
            walks[-1].append(note)
        else:
            walks.append([note])
    return [Walk(tuple(w)) for w in walks]
