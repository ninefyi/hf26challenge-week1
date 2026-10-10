# ring-walk-journal

Walk with a [Pebble Index 01](https://repebble.com) ring on your finger, say what you see with a button press instead of looking at a phone, and get a journal of the walk when you are home. A local open model (Gemma 3) drafts it, you check it against your own words, and nothing is sent to a hosted AI service.

Built for the [Hacktoberfest Open-Source AI Challenge: Week 1, "Touch Grass"](https://dev.to/challenges/hacktoberfest-week1-2026-10-05). Started on 6 October 2026, inside the challenge window.

**Write-up:** [Voice2Note: I spoke to a ring for four hours, and the phone misheard me](https://dev.to/ninefyi/voice2note-i-spoke-to-a-ring-for-four-hours-and-the-phone-misheard-me-24lb), with what worked, what went wrong and what the model got wrong.

## How it works

```
ring (hold button, speak) ─► Pebble app on iPhone (transcribes on the phone)
   ─► webhook ─► Mailbox on Render (web service + Postgres) holds the note
   ·····  later, at home, you run:  uv run python -m walkjournal.pull  ·····
   ─► notes saved on your laptop, then deleted from the Mailbox
   ─► Gemma 3 12B via Ollama (observations + a short paragraph)
   ─► review screen: your words beside the draft; fix, untick, confirm
   ─► journals/2026-10-09_0800.md
```

- **The ring and the phone do the listening.** The Pebble app transcribes on the phone and forwards each note to a webhook you set. This project only receives it.
- **The Mailbox only holds notes.** It runs no model and keeps nothing once you have pulled. A note is deleted from it only after it is saved on your laptop.
- **The model stays on your laptop.** Gemma reads your notes at home. No hosted model ever sees them. They do pass through the Mailbox, which is a trade-off you should know about.
- **Your words are never replaced.** Every observation carries a quote that must appear word for word in the note it came from. If it does not, it is dropped. The finished journal lists your own notes under "My notes".
- **You are the editor.** The journal is marked "Draft, not yet reviewed" until you confirm it in the review screen.
- **Walks are found by time.** A gap of more than 30 minutes between notes starts a new walk.

There is also a home-only mode with no cloud at all: `uv run python -m walkjournal.receiver` accepts the webhook straight onto your laptop over your own Wi-Fi.

## Run it

You need an iPhone or Android with the Pebble app, the ring, and a laptop.

```bash
brew install ollama && ollama serve &     # or install from ollama.com
ollama pull gemma3:12b                    # ~8 GB; I run it on a 16 GB M1 Pro
uv sync
```

### 1. Deploy the Mailbox on Render (free plan)

1. Make two tokens, one for the ring and one for your laptop:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

2. In Render, create a new Blueprint from this repo. It reads [render.yaml](render.yaml), makes the web service and a free Postgres database, and asks for `INGEST_TOKEN` and `PULL_TOKEN`.
3. In the Pebble app, set the ring's webhook to `https://<your-service>.onrender.com/hook/<INGEST_TOKEN>` and use its test button.

A free Render service sleeps after 15 minutes without traffic and takes about a minute to wake, so the first note after a quiet spell can fail. The Pebble app keeps its own list of notes; resend any that are missing. A free Render Postgres database expires 30 days after it is created.

### 2. After the walk

```bash
export MAILBOX_URL=https://<your-service>.onrender.com
export PULL_TOKEN=<PULL_TOKEN>
uv run python -m walkjournal.pull         # waits for the Mailbox to wake, saves notes to data/
uv run python -m walkjournal.app          # review screen at http://127.0.0.1:7861
```

Or draft every walk without the screen: `uv run python -m walkjournal.cli`. Notes and audio are stored in `data/` and journals in `journals/`. Both are in `.gitignore`.

## What the ring sends

Measured from a real note: a `multipart/form-data` POST with `audio` (m4a, 16 kHz mono), `transcription` (text), `recordedAt` (epoch milliseconds) and `client`, plus headers such as `X-Index-Trigger` and `X-Index-Webhook-Version: 1`. The format is not documented anywhere I could find, so a newer Pebble app may change it.

## Tests

```bash
uv run pytest
```

The tests cover the webhook parsing, the Mailbox and the pull (against a real local HTTP server), walk grouping, the quote check and the review table. They use a fake model and an in-memory store, so they need neither Ollama nor Postgres.

## Honest limits

- **Drafting is slow.** Gemma 3 12B takes about a minute for a five-note walk on my laptop. It is meant to run at home after the walk, not in the field.
- **The model is imperfect.** On a fabricated walk it filed "cool air" and "smells like rain" as thoughts, and sometimes attached a place the note did not tie to that item. The quote check blocks invented facts, not misfiled ones. That is what the review screen is for.
- **Short or repeated notes are skipped** (fewer than three words, or one word repeated), so a real one-word note such as "heron" is not extracted.
- **The free Mailbox sleeps when idle.** On one real day, two of the three notes I used arrived while the service was asleep and were stored 10 to 14 seconds after it started waking. That is two cases, not a guarantee, and I did not test a long stretch away from home.
- **The phone mishears, and the model repeats it.** On that day every note had one wrong word (3 of 29). The quote check only compares against the transcript, so it cannot catch a wrong word the phone wrote. The draft journal also put the notes out of time order and added a few words I did not say. See the write-up.
- **Tested on one real day with three notes.** Not a study; the numbers are in the write-up.

## Privacy

The model runs on your machine. Voice notes and transcripts pass through the Mailbox you deploy, are deleted from it once pulled, and are then kept only in `data/` and `journals/` on your laptop, which are not committed. `spike_log.ndjson`, the raw log from the first webhook test, is not committed either.

## License

MIT, see [LICENSE](LICENSE).
