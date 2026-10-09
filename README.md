# VANI Context — memory across channels

Voice AI Hackathon 2.0 · Problem 2 "Global Context: Memory Across Channels" · built on Sarvam AI.

VANI (IndiaMART's voice bot) today starts every call cold. This project gives VANI a **memory file per user**
(`buyer.md` / `seller.md`, keyed by GLID) that is rebuilt within ~2 seconds whenever the user does something on
any channel, and is loaded by the Sarvam Voice Agent **before its first word**. The same file is read on voice,
WhatsApp, web and app, so a conversation started on one channel continues on the next.

## How it works

```
IndiaMART data (Dataset/ CSVs + buyer getContext JSON; starter APIs on Day 1)
        │  app/sources/      fetch one user's history by GLID, apply the lookback window
        ▼
Context builder   facts by code + 5 insight fields by sarvam-105b (story, greeting, opener, next action, avoid)
        │  app/builder/      writes context_files/<glid>/{buyer|seller}.md  (~35 lines, timestamped)
        ▼
FastAPI  GET /context?glid=…   →  call card, greeting, opener, role, language   (Sarvam on_start tool)
         GET /history          →  answer about older history, mid-call         (Sarvam run tool)
         POST /events          →  new activity from any channel → rebuild       (Sarvam on_end tool, WhatsApp, web)
        ▼
Sarvam Voice Agent "VANI IndiaMART"  (Samvaad, agent id VANI-IndiaM-b67b20da-8a1b)
   telephony · web widget · SDK  — same agent, same memory file on every channel
```

| Piece | File | Notes |
|---|---|---|
| Seller history | `app/sources/seller.py` | 11 organiser CSVs (profile, enquiries, replies, buyer calls, buy-leads, WhatsApp, VANI calls + transcripts, executive calls, PNS quotes). Only file that knows CSV columns: swap for the real APIs here. |
| Buyer history | `app/sources/buyer.py` | Parses IndiaMART's existing `getContext` API responses (Kibana export). |
| Builders | `app/builder/seller_md.py`, `buyer_md.py`, `insight.py`, `call_card.py`, `prefs.py` | Facts rendered by code (never hallucinated); insight by `sarvam-105b` with `reasoning_effort=None`; rule-based fallback if the LLM fails. Call card = ~10-line version sent to the agent. Prefs = language the user spoke last. |
| API | `app/api.py` | Routes above plus `/webhook/sarvam`, `/whatsapp/{glid}`, `/site/{glid}`, `/active`, `/call`. |
| Demo pages | `web/demo.html` (`/demo`), `web/index.html` (`/`) | Phone (WhatsApp + VANI call via the Sarvam web widget) · desktop (IndiaMART site) · live memory file. |

## Lookback window and refresh logic

- **Activity:** last 30 days (enquiries, calls, buy-leads, WhatsApp counts, website actions).
- **Conversations:** last 180 days (VANI calls, executive calls, WhatsApp texts, phone quotes). Older than that is
  noise for a greeting but is still reachable mid-call through `GET /history`.
- **Refresh:** every `POST /events` (call summary, WhatsApp message, website action) appends to
  `context_files/<glid>/events.jsonl` and regenerates the file immediately. Typical freshness: **1.3–2 s**
  (source read 0.2–0.6 s + LLM 1–1.5 s). Calls where nobody really spoke (`no_conversation`, `wrong_person`)
  are skipped so they never become the "latest" memory.
- **Language memory:** the language the user spoke at the end of the last call is saved and the next greeting is
  written in it.

## What is real and what is simulated (please read before judging the demo)

| Channel | In the demo |
|---|---|
| Voice | **Real** Sarvam Voice Agent (STT Saaras, LLM sarvam-105b-conversations, TTS Bulbul). Memory loaded by the on_start tool, call summary written back by the on_end tool. |
| WhatsApp | **Simulated** on the demo page: the message becomes a live event, the reply is written by sarvam-105b from the fresh memory. Real WhatsApp needs Sarvam's enterprise channel. |
| Website / Lead Manager | **Simulated** on the demo page with the user's real dataset items; clicks and scroll-views post web events. |
| Data | Organiser dataset (5,000 sellers, 302 buyers) standing in for the Day-1 APIs. No invented users. |

## Live indiamart.com in the demo (Chrome extension)

The middle screen of `/demo` has two modes. **Emulated** shows the user's real dataset items in a look-alike page.
**Live indiamart.com** shows the real website inside the frame and captures what the user does there:

- searches (query), product page opens (title, supplier, price shown on the page),
- clicks on Get Latest Price / Contact Supplier / Call Supplier / Send Enquiry / Shortlist / Reply / Call buyer,
- product cards that stay in view for a second ("browsed: A, B, C", batched).

Each action is posted to `POST /events/{glid}` as one plain line, the memory file is rebuilt, and VANI's next
greeting changes. The GLID is the user selected on the demo page (`GET /active`).

IndiaMART sends `x-frame-options: sameorigin`, so a small Chrome extension (folder `extension/`) removes that
header for the frame and injects the capture script on every `*.indiamart.com` page, in tabs and in the frame.
Install once: `chrome://extensions` → Developer mode → **Load unpacked** → pick the `extension/` folder.
In production this script is simply part of IndiaMART's own frontend; the extension is the hackathon stand-in.

## Known limitations

- The Sarvam web widget sends `user_identifier`, but the agent's on_start tool receives it empty. The demo page
  therefore posts the selected GLID to `POST /active` and the API uses it when the agent calls with no usable
  identifier. One on-screen user at a time. To be confirmed with Sarvam staff: the correct system variable name.
- The API is exposed with a cloudflared quick tunnel whose URL changes on restart; both agent tools must then be
  re-pointed and the agent committed. A static ngrok domain removes this.
- The dashboard "Test agent" runs the **draft**; the widget runs the latest **committed** version. Commit after
  every change.
- Inbound calls need a Sarvam phone number (none in the workspace yet). `data/phone_to_glid.json` maps caller
  numbers to GLIDs for the demo.

## Run

```bash
source .venv/bin/activate
uvicorn app.api:app --reload --port 8000          # API + demo pages at http://localhost:8000/demo
cloudflared tunnel --url http://localhost:8000     # public URL for the Sarvam tools
python -m app.builder.seller_md 95568576           # build one seller file (add --no-llm for rules only)
python -m app.builder.buyer_md 274238067           # build one buyer file
```

`.env` needs `SARVAM_API_KEY`. `web/config.js` needs the embed-scoped Sarvam key (see `web/config.js.example`).
Dataset and generated files are git-ignored.
