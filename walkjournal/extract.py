"""Ask a local model (Ollama) to turn Notes into Observations and a Journal paragraph.

The model never replaces the Walker's words: every Observation carries a quote that must
appear verbatim in the Note it came from, otherwise it is dropped.
"""
import json
import urllib.request
from dataclasses import dataclass

from .notes import Note

KINDS = ["sighting", "place", "thought", "todo"]

OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": KINDS},
                    "what": {"type": "string"},
                    "where": {"type": ["string", "null"]},
                    "quote": {"type": "string"},
                },
                "required": ["kind", "what", "where", "quote"],
            },
        }
    },
    "required": ["observations"],
}

EXTRACT_PROMPT = """You turn one spoken note from a walk into structured observations.
Kinds: sighting (a plant, animal, bird, thing seen or heard), place (somewhere noticed or reached),
thought (an idea or feeling), todo (something to do later).
Rules:
- Only use what the note says. Never add species, places or facts that are not in it.
- "quote" must be copied exactly from the note, a few words long.
- "where" is only a place the note mentions, else null.
- "thought" is for an idea or opinion, not for the weather or how things look or smell.
- "what" is a short plain phrase naming the thing. Never start it with "quote:".
- "where" only if the note itself says where that thing was; do not copy a place from elsewhere in the note.
- Do not repeat the same place in "what" and "where".
- If the note holds nothing worth recording, or is only a test or filler, return an empty list.

Note: {transcript}"""

JOURNAL_PROMPT = """Write a short journal paragraph (3 to 5 sentences, first person, plain and warm)
about a walk, from the walker's notes below, in time order. Only use what the notes say.
Do not add feelings, opinions, reactions or descriptions (no "lovely", "I realized", "I noticed").
Do not invent species, places or weather. Leave out test or filler notes.
Write everything in the past tense, as a record of a walk already taken.
State plainly what the walker saw, where, and what they want to do later.

Notes:
{notes}"""


@dataclass(frozen=True)
class Observation:
    note_id: str
    kind: str
    what: str
    where: str | None
    quote: str


class Ollama:
    def __init__(self, model: str = "gemma3:12b", host: str = "http://localhost:11434"):
        self.model, self.host = model, host

    def chat(self, prompt: str, schema: dict | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }
        if schema:
            payload["format"] = schema
        req = urllib.request.Request(
            f"{self.host}/api/chat", json.dumps(payload).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())["message"]["content"]


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


MIN_WORDS = 3


def is_filler(transcript: str) -> bool:
    """Too short to hold an observation, or the same word repeated ("hello hello hello")."""
    words = [w.strip(".,!?").lower() for w in transcript.split()]
    return len(words) < MIN_WORDS or len(set(words)) == 1


def extract_observations(note: Note, llm) -> list[Observation]:
    if is_filler(note.transcript):
        return []
    try:
        raw = json.loads(llm.chat(EXTRACT_PROMPT.format(transcript=note.transcript), OBSERVATION_SCHEMA))
        items = raw["observations"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    out = []
    for it in items:
        quote = str(it.get("quote", "")).strip()
        if it.get("kind") not in KINDS or not quote or _norm(quote) not in _norm(note.transcript):
            continue  # not grounded in what the walker said
        what = str(it.get("what", "")).strip()
        where = it.get("where") or None
        if where and _norm(where) in _norm(what):
            where = None  # already says where
        out.append(Observation(note.id, it["kind"], what, where, quote))
    return out


def write_paragraph(notes: list[Note], llm) -> str:
    text = "\n".join(f"- {n.transcript}" for n in notes if not is_filler(n.transcript))
    return llm.chat(JOURNAL_PROMPT.format(notes=text)).strip()
