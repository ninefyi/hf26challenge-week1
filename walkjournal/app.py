"""Review screen: check what the model drafted against your own words, then confirm.

Run: uv run python -m walkjournal.app [--data data] [--out journals] [--model gemma3:12b]
"""
import argparse
from pathlib import Path

import gradio as gr

from .extract import KINDS, Ollama
from .journal import clock, draft_walk, render_journal, select_walks, walk_label, walk_stamp
from .notes import load_notes
from .review import HEADERS, from_rows, to_rows


def build_app(data: Path, out: Path, model: str, since=None, until=None, gap_min=None) -> gr.Blocks:
    llm = Ollama(model)

    def walks():
        return select_walks(load_notes(data), since, until, gap_min)

    def choices():
        return [(walk_label(w), i) for i, w in enumerate(walks())]

    def my_notes(walk):
        return "\n".join(f"{i}. **{clock(n.recorded_at_ms)}** {n.transcript}" for i, n in enumerate(walk.notes, 1))

    def read(idx):
        ws = walks()
        if idx is None or idx >= len(ws):
            raise gr.Error("Pick a walk first.")
        walk = ws[idx]
        paragraph, observations = draft_walk(walk, llm)
        return my_notes(walk), paragraph, to_rows(walk, observations), ""

    def confirm(idx, paragraph, rows):
        ws = walks()
        if idx is None or idx >= len(ws):
            raise gr.Error("Pick a walk first.")
        walk = ws[idx]
        text = render_journal(walk, paragraph.strip(), from_rows(walk, rows.values.tolist()), confirmed=True)
        out.mkdir(exist_ok=True)
        path = out / f"{walk_stamp(walk)}.md"
        path.write_text(text)
        return f"Saved to `{path}`", text

    with gr.Blocks(title="Walk journal review") as app:
        gr.Markdown("# Walk journal\nCheck the model's draft against **your own words**, fix anything wrong, then confirm.")
        with gr.Row():
            pick = gr.Dropdown(choices(), label="Walk", value=None)
            refresh = gr.Button("Refresh walks")
            read_btn = gr.Button("Read with Gemma", variant="primary")
        gr.Markdown("### 1. My notes (what I actually said)")
        notes_md = gr.Markdown()
        gr.Markdown("### 2. Draft paragraph (edit freely)")
        paragraph = gr.Textbox(lines=5, show_label=False)
        gr.Markdown("### 3. Observations (untick Keep to drop a row; **Note** is the number above)")
        table = gr.Dataframe(
            headers=HEADERS, datatype=["bool", "number", "str", "str", "str", "str"],
            col_count=(6, "fixed"), interactive=True, show_label=False, static_columns=[1, 5],
        )
        gr.Markdown(f"Kinds: {', '.join(KINDS)}")
        confirm_btn = gr.Button("Confirm and save journal", variant="primary")
        status = gr.Markdown()
        preview = gr.Markdown()

        refresh.click(lambda: gr.update(choices=choices()), None, pick)
        read_btn.click(read, pick, [notes_md, paragraph, table, status])
        confirm_btn.click(confirm, [pick, paragraph, table], [status, preview])
    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("journals"))
    ap.add_argument("--model", default="gemma3:12b")
    ap.add_argument("--port", type=int, default=7861)
    ap.add_argument("--since", help="only notes at or after this local time, e.g. 2026-10-10T08:00")
    ap.add_argument("--until", help="only notes before this local time")
    ap.add_argument("--gap-min", type=int, help="minutes of quiet that start a new walk (default 30)")
    args = ap.parse_args()
    build_app(args.data, args.out, args.model, args.since, args.until, args.gap_min).launch(server_name="127.0.0.1", server_port=args.port)


if __name__ == "__main__":
    main()
