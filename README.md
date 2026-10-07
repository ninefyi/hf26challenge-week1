# ring-walk-journal

Walk with a [Pebble Index 01](https://repebble.com) ring on your finger, say what you see with a button press instead of looking at a phone, and get a journal of the walk when you are home. A local open model (Gemma 3) drafts it, you check it against your own words, and nothing is sent to a hosted AI service.

Built for the [Hacktoberfest Open-Source AI Challenge: Week 1, "Touch Grass"](https://dev.to/challenges/hacktoberfest-week1-2026-10-05). Started on 6 October 2026, inside the challenge window.

## How it works

```
ring (hold button, speak) ─► Pebble app on iPhone (transcribes on the phone)
   ─► webhook over home Wi-Fi ─► receiver on your laptop (audio + transcript + time)
   ─► Gemma 3 12B via Ollama (observations + a short paragraph)
   ─► review screen: your words beside the draft; fix, untick, confirm
   ─► journals/2026-10-09_0800.md
```

- **The ring and the phone do the listening.** The Pebble app transcribes on the phone and the app forwards each note to a webhook you set. This project only receives it.
- **Your words are never replaced.** Every observation carries a quote that must appear word for word in the note it came from. If it does not, it is dropped. The finished journal lists your own notes under "My notes".
- **You are the editor.** The journal is marked "Draft, not yet reviewed" until you confirm it in the review screen.
- **Walks are found by time.** A gap of more than 30 minutes between notes starts a new walk.

## Run it

You need an iPhone or Android with the Pebble app, the ring, and a laptop on the same Wi-Fi.

```bash
brew install ollama && ollama serve &     # or install from ollama.com
ollama pull gemma3:12b                    # ~8 GB; I run it on a 16 GB M1 Pro
uv sync
```

1. Start the receiver and note your laptop's LAN address:

   ```bash
   uv run python -m walkjournal.receiver
   ipconfig getifaddr en0
   ```

2. In the Pebble app, set the ring's webhook to `http://<that address>:8787/hook` (plain `http` works) and use its test button.
3. Go for a walk. Notes reach the receiver when the phone is back on your Wi-Fi.
4. Review and confirm:

   ```bash
   uv run python -m walkjournal.app      # opens http://127.0.0.1:7861
   ```

   Or draft every walk without the screen: `uv run python -m walkjournal.cli`.

Notes and audio are stored in `data/` and journals in `journals/`. Both are in `.gitignore`.

## What the ring sends

Measured from a real note: a `multipart/form-data` POST with `audio` (m4a, 16 kHz mono), `transcription` (text), `recordedAt` (epoch milliseconds) and `client`, plus headers such as `X-Index-Trigger` and `X-Index-Webhook-Version: 1`. The format is not documented anywhere I could find, so a newer Pebble app may change it.

## Tests

```bash
uv run pytest
```

The tests cover the webhook parsing, walk grouping, the quote check and the review table. They use a fake model, so they do not need Ollama.

## Honest limits

- **Drafting is slow.** Gemma 3 12B takes about a minute for a five-note walk on my laptop. It is meant to run at home after the walk, not in the field.
- **The model is imperfect.** On a fabricated walk it filed "cool air" and "smells like rain" as thoughts, and sometimes attached a place the note did not tie to that item. The quote check blocks invented facts, not misfiled ones. That is what the review screen is for.
- **Short or repeated notes are skipped** (fewer than three words, or one word repeated), so a real one-word note such as "heron" is not extracted.
- **Notes are only received while the receiver is running** and the phone can reach the laptop.
- **Tested so far on a fabricated walk.** Results from a real walk are in the write-up, not here.

## Privacy

The model runs on your machine. Voice notes, transcripts and journals stay in `data/` and `journals/`, which are not committed. `spike_log.ndjson`, the raw log from the first webhook test, is not committed either.

## License

MIT, see [LICENSE](LICENSE).
