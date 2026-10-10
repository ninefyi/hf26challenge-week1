"""Build Markdown Journals from stored Notes.

Run: uv run python -m walkjournal.cli [--data data] [--out journals] [--model gemma3:12b]
"""
import argparse
from datetime import datetime
from pathlib import Path

from .extract import Ollama
from .journal import SGT, build_journal, select_walks
from .notes import load_notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("journals"))
    ap.add_argument("--model", default="gemma3:12b")
    ap.add_argument("--since", help="only notes at or after this local time, e.g. 2026-10-10T08:00")
    ap.add_argument("--until", help="only notes before this local time")
    ap.add_argument("--gap-min", type=int, help="minutes of quiet that start a new walk (default 30)")
    args = ap.parse_args()

    walks = select_walks(load_notes(args.data), args.since, args.until, args.gap_min)
    if not walks:
        print("no notes yet")
        return
    args.out.mkdir(exist_ok=True)
    llm = Ollama(args.model)
    for walk in walks:
        stamp = datetime.fromtimestamp(walk.start_ms / 1000, SGT).strftime("%Y-%m-%d_%H%M")
        path = args.out / f"{stamp}.md"
        path.write_text(build_journal(walk, llm))
        print(f"wrote {path} ({len(walk.notes)} notes)")


if __name__ == "__main__":
    main()
