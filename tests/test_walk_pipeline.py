import json

from walkjournal.extract import extract_observations
from walkjournal.journal import build_journal
from walkjournal.notes import Note
from walkjournal.walks import group_walks


def note(i, ms, text):
    return Note(f"n{i}", ms, "", text, None, None)


MIN = 60_000


class FakeLLM:
    def __init__(self, observations):
        self.observations = observations

    def chat(self, prompt, schema=None):
        if schema:
            return json.dumps({"observations": self.observations})
        return "A quiet morning walk."


def test_gap_starts_a_new_walk():
    ns = [note(1, 0, "a"), note(2, 10 * MIN, "b"), note(3, 100 * MIN, "c")]
    walks = group_walks(ns)
    assert [len(w.notes) for w in walks] == [2, 1]


def test_unordered_notes_are_sorted_into_walks():
    walks = group_walks([note(2, 5 * MIN, "b"), note(1, 0, "a")])
    assert [n.id for n in walks[0].notes] == ["n1", "n2"]


def test_ungrounded_observation_is_dropped():
    n = note(1, 0, "A grey heron by the bridge")
    llm = FakeLLM([
        {"kind": "sighting", "what": "grey heron", "where": "bridge", "quote": "grey heron"},
        {"kind": "sighting", "what": "kingfisher", "where": None, "quote": "a kingfisher"},
    ])
    obs = extract_observations(n, llm)
    assert [o.what for o in obs] == ["grey heron"]


def test_quote_match_ignores_case_and_spacing():
    n = note(1, 0, "Big  old banyan tree")
    llm = FakeLLM([{"kind": "sighting", "what": "banyan", "where": None, "quote": "BIG old banyan"}])
    assert len(extract_observations(n, llm)) == 1


def test_bad_model_output_gives_no_observations():
    class Broken:
        def chat(self, prompt, schema=None):
            return "not json"

    assert extract_observations(note(1, 0, "hi"), Broken()) == []


def test_journal_keeps_walkers_own_words():
    n = note(1, 1_791_251_811_058, "Heron by the bridge")
    llm = FakeLLM([{"kind": "sighting", "what": "heron", "where": "bridge", "quote": "Heron"}])
    md = build_journal(group_walks([n])[0], llm)
    assert "## My notes" in md and "Heron by the bridge" in md
    assert "**sighting**: heron (bridge)" in md


def test_filler_notes_are_skipped():
    from walkjournal.extract import is_filler
    assert is_filler("Hello hello hello.")
    assert is_filler("test")
    assert not is_filler("Heron by the bridge")


def test_where_dropped_when_already_in_what():
    n = note(1, 0, "Rest at the park gate today")
    llm = FakeLLM([{"kind": "place", "what": "park gate", "where": "park gate", "quote": "park gate"}])
    assert extract_observations(n, llm)[0].where is None


def test_select_walks_window_and_gap():
    from walkjournal.journal import select_walks
    day = 1_791_590_400_000  # 2026-10-10 08:00 UTC+8
    ns = [note(1, day, "a"), note(2, day + 41 * MIN, "b"), note(3, day + 400 * MIN, "c")]
    assert [len(w.notes) for w in select_walks(ns)] == [1, 1, 1]
    assert [len(w.notes) for w in select_walks(ns, gap_min=60)] == [2, 1]
    assert [len(w.notes) for w in select_walks(ns, until="2026-10-10T13:00", gap_min=60)] == [2]
    assert [len(w.notes) for w in select_walks(ns, since="2026-10-10T08:30", gap_min=600)] == [2]
