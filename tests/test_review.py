from walkjournal.extract import Observation
from walkjournal.journal import render_journal
from walkjournal.notes import Note
from walkjournal.review import from_rows, to_rows
from walkjournal.walks import group_walks

NOTES = [Note("a", 1_791_288_000_000, "", "Heron by the bridge", None, None),
         Note("b", 1_791_288_060_000, "", "Remember to buy a bottle", None, None)]
WALK = group_walks(NOTES)[0]
OBS = [Observation("a", "sighting", "heron", "bridge", "Heron"),
       Observation("b", "todo", "buy a bottle", None, "buy a bottle")]


def test_rows_round_trip():
    rows = to_rows(WALK, OBS)
    assert rows[1][:2] == [True, 2]
    assert from_rows(WALK, rows) == OBS


def test_unticked_and_blank_rows_are_dropped():
    rows = to_rows(WALK, OBS)
    rows[0][0] = False
    rows[1][3] = "  "
    assert from_rows(WALK, rows) == []


def test_edits_flow_through_and_nan_where_is_none():
    rows = to_rows(WALK, OBS)
    rows[0][3] = "grey heron"
    rows[1][4] = float("nan")
    got = from_rows(WALK, rows)
    assert got[0].what == "grey heron" and got[1].where is None


def test_bad_note_number_or_kind_skipped():
    rows = to_rows(WALK, OBS)
    rows[0][1] = 9
    rows[1][2] = "nonsense"
    assert from_rows(WALK, rows) == []


def test_render_marks_confirmed():
    md = render_journal(WALK, "A walk.", OBS, confirmed=True)
    assert "Reviewed and confirmed by me." in md
    assert "Draft, not yet reviewed." in render_journal(WALK, "A walk.", OBS)
