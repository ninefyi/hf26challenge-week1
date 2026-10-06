"""Build Markdown Journals from stored Notes.

Run: uv run python -m walkjournal.cli [--data data] [--out journals] [--model gemma3:12b]
"""
import argparse
from datetime import datetime
from pathlib import Path

from .extract import Ollama
from .journal import SGT, build_journal
from .notes import load_notes
from .walks import group_walks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("journals"))
    ap.add_argument("--model", default="gemma3:12b")
    args = ap.parse_args()

    walks = group_walks(load_notes(args.data))
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
