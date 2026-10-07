import struct

from walkjournal.notes import Note
from walkjournal.stats import audio_seconds, grade, match_script, report, script_lines, similarity


def note(i, ms, text, audio=None, stored=None):
    return Note(f"n{i}", ms, "", text, audio, None, stored)


def m4a(seconds, timescale=16000):
    mvhd = b"mvhd" + struct.pack(">B3xIIII", 0, 0, 0, timescale, int(seconds * timescale))
    return b"\x00\x00\x00\x1cftypM4A " + mvhd


def test_audio_seconds_reads_movie_header(tmp_path):
    (tmp_path / "a.m4a").write_bytes(m4a(4.5))
    assert abs(audio_seconds(tmp_path / "a.m4a") - 4.5) < 0.001
    (tmp_path / "bad.m4a").write_bytes(b"nothing here")
    assert audio_seconds(tmp_path / "bad.m4a") is None
    assert audio_seconds(tmp_path / "missing.m4a") is None


def test_script_lines_take_only_quoted_cells(tmp_path):
    f = tmp_path / "s.md"
    f.write_text('| # | Say this | x |\n|---|---|---|\n| 1 | "Hello there." | a |\n| 2 | A long ramble | b |\n| 3 | "Heron." | c |\n')
    assert script_lines(f) == ["Hello there.", "Heron."]


def test_grades():
    assert grade(similarity("A grey heron.", "a grey heron")) == "exact"
    assert grade(similarity("Offline test one", "Off-line tail one")) == "close"
    assert grade(similarity("Something moved in the bush", "Something moved in the bus")) == "close"  # one wrong word is not exact
    assert grade(similarity("Offline test one", "banana")) == "missing"


def test_script_matched_by_similarity_not_order():
    notes = [note(1, 1, "off line taste too"), note(2, 2, "heron by the bridge")]
    got = match_script(["Heron by the bridge", "Offline test two"], notes)
    assert got[0][1].id == "n2" and grade(got[0][2]) == "exact"
    assert got[1][1].id == "n1"


def test_report_numbers(tmp_path):
    (tmp_path / "a.m4a").write_bytes(m4a(4))
    notes = [note(1, 0, "A grey heron by the pond", "a.m4a", stored=60_000),
             note(2, 30_000, "Hello hello hello"),
             note(3, 90_000, "Remember to buy a bottle")]
    out = report(notes, tmp_path, ["A grey heron by the pond", "Remember to buy a bottle", "Zzzz qqqq xxxx"])
    assert "Notes received: **3**" in out
    assert "Filler or too short" in out and "**1**" in out
    assert "exact **2**" in out and "missing 1" in out
    assert "median 60 s" in out  # recorded to saved
    assert "Hello hello hello" in out.split("matched no script line")[1]


def test_report_with_no_notes():
    assert report([], None) == "No notes.\n"
