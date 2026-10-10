<p align="center">
  <img src="web/im-logo.png" alt="IndiaMART" width="80" />
</p>

<h1 align="center">VANI Context — Memory Across Channels</h1>

<p align="center">
  <strong>Give IndiaMART's voice bot a memory that works across voice, WhatsApp, web, and app — so every conversation picks up where the last one left off.</strong>
</p>

<p align="center">
  <em>Voice AI Hackathon 2.0 · Problem Statement 2: "Global Context — Memory Across Channels" · Built on Sarvam AI</em>
</p>

---

## 🎯 The Problem

VANI — IndiaMART's voice bot — starts every call **cold**. It doesn't know that the seller just replied to an enquiry on WhatsApp, or that the buyer browsed three products on the website five minutes ago. Conversations feel disconnected, repetitive, and robotic.

## 💡 The Solution

VANI Context builds a **persistent memory file per user** (`seller.md` / `buyer.md`, keyed by GLID) that is:

- **Rebuilt in ~2 seconds** whenever the user does _anything_ on _any_ channel
- **Loaded by the Sarvam Voice Agent before its first word** — so the greeting, the opener, and the conversation are personalised from second zero
- **Shared across voice, WhatsApp, web, and app** — a conversation started on one channel continues seamlessly on the next

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
│                                                                     │
│   Organiser CSVs              IndiaMART APIs         Live Events    │
│   (seller profile,            (getContext for         (call summary,│
│    enquiries, calls,           buyer history)          WhatsApp msg,│
│    buy-leads, WhatsApp,                                web action)  │
│    VANI transcripts,                                                │
│    executive calls)                                                 │
└──────────┬─────────────────────────┬────────────────────┬───────────┘
           │                         │                    │
           ▼                         ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     app/sources/                                    │
│                                                                     │
│   seller.py ─── 11 CSV tables, applies lookback window              │
│   buyer.py  ─── parses getContext JSON responses                    │
│   im_home.py / im_search.py ─── IndiaMART page context              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     app/builder/                                    │
│                                                                     │
│   seller_md.py ─── renders seller memory file (facts by code)       │
│   buyer_md.py  ─── renders buyer memory file                        │
│   insight.py   ─── 5 LLM-generated fields via sarvam-m1            │
│                     (story, greeting, opener, next action, avoid)    │
│   call_card.py ─── ~10-line summary for the agent prompt            │
│   prefs.py     ─── language memory + feminine form enforcement      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     app/api.py (FastAPI)                             │
│                                                                     │
│   GET  /context/{glid}       → call card + greeting + opener        │
│   GET  /history/{glid}       → older history for mid-call questions  │
│   POST /events/{glid}        → new event → rebuild memory file      │
│   POST /webhook/sarvam       → Sarvam on_end callback               │
│   POST /whatsapp/{glid}      → WhatsApp message handling            │
│   POST /site/{glid}          → website action event                 │
│   GET  /config.js            → embed widget config (from .env)      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Sarvam Voice Agent — "Tanya"                          │
│                                                                     │
│   Buyer Agent:  VANI-IndiaM-b67b20da-8a1b                           │
│   Seller Agent: VANI-IndiaM-61f2af95-c5b7                           │
│                                                                     │
│   STT: Saaras · LLM: sarvam-m1 · TTS: Bulbul (Sarika voice)        │
│   Same persona, same 4 tools, same API — on telephony, web & SDK    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📄 What a Memory File Looks Like

Here's a real example for a seller (`context_files/95568576/seller.md`):

```markdown
# Seller memory — Alfa Enterprises (GLID 95568576)

## Who
- Alfa Enterprises, New Delhi · Free seller · 148 products · catalog score 86

## Story so far
The seller recently browsed memory cards and pen drives on Lead Manager.
They have multiple unread enquiries for memory cards and HP pen drives.

## Latest across channels (live)
- 🔄 2026-10-10 13:41 via web: Seller opened Lead Manager
- 🔄 2026-10-10 13:39 via web: Browsed SanDisk Ultra Memory Card, HP Pen Drive

## Last 30 days
- Enquiries: 57 received, **8 unread** · seller replied 6×
- Buyer calls: 32 (21 connected, 11 missed)
- Buyleads bought: 55 (11,000 credits)

## For the next conversation
- **Greeting:** नमस्ते Alfa Enterprises, SanDisk Memory Card की enquiry के बारे में बात करनी थी
- **Opener:** Aapko HP Pen Drive 16gb ki enquiry aayi thi, kya reply de diya?
- **Next best action:** Help reply to unread buyer enquiries
- **Avoid:** Don't bring up the past August meeting
```

The agent reads this **before saying a word** — so the very first line of the call is personalised.

---

## 🔄 Lookback Window & Refresh Logic

| What | Window | Why |
|------|--------|-----|
| **Activity** (enquiries, calls, buy-leads, WhatsApp, web) | Last **30 days** | Recent enough to be relevant for a greeting |
| **Conversations** (VANI calls, executive calls, WhatsApp texts) | Last **180 days** | Longer context to avoid repeating old mistakes |
| **Older history** | Available mid-call via `GET /history` | Reachable but not in the greeting |

**Refresh triggers:**
- Every `POST /events` (call summary, WhatsApp message, website action) appends to `events.jsonl` and **regenerates the memory file immediately**
- Typical freshness: **1.3–2 seconds** (source read 0.2–0.6s + LLM insight 1–1.5s)
- No-conversation calls (`no_conversation`, `wrong_person`) are skipped — they never become the "latest" memory
- **Language memory:** the language the user spoke at the end of the last call is saved, and the next greeting is written in it

---

## 🌐 API Reference

| Method | Endpoint | Description | Used By |
|--------|----------|-------------|---------|
| `GET` | `/context/{glid}` | Returns call card, greeting, opener, name, role, language | Sarvam `on_start` tool |
| `GET` | `/context/{glid}/seller.md` | Returns raw markdown memory file | Debugging / external tools |
| `GET` | `/history/{glid}` | Returns older history for mid-call questions | Sarvam `run` tool |
| `POST` | `/events/{glid}` | Append a new event, regenerate memory, return freshness | Sarvam `on_end` tool / WhatsApp / Web |
| `POST` | `/webhook/sarvam` | Sarvam on_end callback (call summary) | Sarvam platform |
| `POST` | `/whatsapp/{glid}` | Process incoming WhatsApp message | WhatsApp integration |
| `POST` | `/site/{glid}` | Record website action (browse, click, enquiry) | Chrome extension / demo |
| `GET` | `/active` | Get/set the currently active GLID for the demo | Demo page |
| `POST` | `/call` | Initiate an outbound VANI call | Demo page |
| `GET` | `/config.js` | Sarvam embed widget config (built from `.env`) | Web widget |
| `GET` | `/health` | Health check | Monitoring |
| `GET` | `/demo` | Demo page (three-screen experience) | Browser |

---

## 🗂️ Project Structure

```
vani-context/
├── app/
│   ├── api.py                    # FastAPI server — all routes
│   ├── sources/
│   │   ├── seller.py             # 11 organiser CSVs → seller history
│   │   ├── buyer.py              # getContext JSON → buyer history
│   │   ├── im_home.py            # IndiaMART homepage context
│   │   └── im_search.py          # IndiaMART search page context
│   └── builder/
│       ├── seller_md.py          # Renders seller.md memory file
│       ├── buyer_md.py           # Renders buyer.md memory file
│       ├── insight.py            # LLM-generated fields (story, greeting, etc.)
│       ├── call_card.py          # ~10-line summary for agent prompt
│       └── prefs.py              # Language memory + feminine Hindi forms
│
├── context_files/                # Generated memory files (per GLID)
│   ├── <glid>/
│   │   ├── seller.md or buyer.md # The memory file the agent reads
│   │   ├── events.json           # Structured event log
│   │   └── events.jsonl          # Append-only event stream
│   ├── _active.json              # Currently active GLID for demo
│   └── _backups/                 # Backup copies of event files
│
├── data/
│   └── phone_to_glid.json        # Caller number → GLID mapping (demo stand-in)
│
├── docs/
│   ├── agent_prompt_buyer.md     # Full buyer agent prompt (copy from Sarvam)
│   ├── agent_prompt_seller.md    # Full seller agent prompt (copy from Sarvam)
│   ├── indiamart_facts_and_guardrails.md  # Verified facts + guardrails
│   └── seller_call_insights.md   # Analysis of 9,657 past seller calls
│
├── extension/                    # Chrome extension for live indiamart.com capture
│   ├── manifest.json             # Manifest V3
│   ├── background.js             # Service worker (header removal)
│   ├── capture.js                # Content script (action capture)
│   └── rules.json                # Declarative net request rules
│
├── scripts/
│   ├── explore_seller.py         # Interactive seller data exploration
│   ├── test_sarvam.py            # Sarvam API test script
│   └── tunnel.sh                 # cloudflared / ngrok tunnel helper
│
├── web/                          # Demo UI
│   ├── demo.html                 # Three-screen demo (phone + site + memory)
│   ├── index.html                # Landing page
│   ├── start.html                # Quick start page
│   ├── config.js.example         # Template for embed widget config
│   └── widget.html.example       # Template for standalone widget
│
├── Dataset/                      # Organiser dataset (git-ignored)
├── .env                          # API keys (git-ignored)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Sarvam AI account** with API keys ([indus.sarvam.ai](https://indus.sarvam.ai))
- **cloudflared** or **ngrok** (to expose the local server to Sarvam)

### 1. Clone & Install

```bash
git clone https://github.com/Ankulraja/vani-context.git
cd vani-context

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Server key for LLM calls (from indus.sarvam.ai → API Keys)
SARVAM_API_KEY=sk_your_server_key_here

# Embed-scoped key for the web widget (indus.sarvam.ai → Deploy with code → API keys)
# IMPORTANT: Use the embed/widget scope key, NOT the server key
SARVAM_EMBED_KEY=sk_samvaad_your_embed_key_here

# Organisation and workspace IDs (from indus.sarvam.ai)
SARVAM_ORG_ID=your-org-id
SARVAM_WORKSPACE_ID=your-workspace-id

# Agent IDs (created on the Sarvam dashboard)
SARVAM_APP_ID=your-buyer-agent-id
SARVAM_APP_ID_SELLER=your-seller-agent-id

# Optional: for inbound calls
# SARVAM_AGENT_API_KEY=your-agent-api-key
# SARVAM_CONNECTION_ID=your-connection-id
# SARVAM_AGENT_NUMBER=your-agent-phone-number
```

### 3. Place the Dataset

Put the organiser dataset CSVs in `Dataset/Global Context - Seller Dataset/`. These files are **git-ignored** and must be added manually:

| File | Description |
|------|-------------|
| `gc_seller_profile.csv` | Seller business profiles |
| `gc_enquiries_received.csv` | Enquiries sellers received from buyers |
| `gc_enquiry_messages.csv` | Enquiry message threads |
| `gc_buyer_calls_received.csv` | Buyer → seller call records |
| `gc_buyer_call_extractions.csv` | Extracted data from buyer calls |
| `gc_buyleads_bought.csv` | Buy-leads purchased by sellers |
| `gc_whatsapp_messages.csv` | WhatsApp conversations |
| `gc_whatsapp_chatbot_conversations.csv` | WhatsApp chatbot interactions |
| `gc_bot_calls.csv` | VANI bot call records |
| `gc_bot_call_turns.csv` | Turn-by-turn VANI call transcripts |
| `gc_executive_calls.csv` | Executive (human) call records |

### 4. Run the Server

```bash
# Start the API + demo pages
uvicorn app.api:app --reload --port 8000

# In another terminal — expose to the internet for Sarvam
cloudflared tunnel --url http://localhost:8000
# or: ngrok http 8000
```

### 5. Try It Out

| What | URL |
|------|-----|
| **Demo page** (three-screen experience) | `http://localhost:8000/demo` |
| **Landing page** | `http://localhost:8000/` |
| **Build a single seller memory file** | `python -m app.builder.seller_md 95568576` |
| **Build a single buyer memory file** | `python -m app.builder.buyer_md 274238067` |
| **Rules-only mode (no LLM)** | `python -m app.builder.seller_md 95568576 --no-llm` |

---

## 🎭 The Agent — "Tanya"

Both the buyer and seller agents share the same persona: **Tanya**, IndiaMART's customer care voice assistant.

| Property | Detail |
|----------|--------|
| **Name** | Tanya (never says "VANI" to users) |
| **Voice** | Sarika — Conversational (pace 1.1) |
| **Identity** | When asked, says she's Tanya, IndiaMART's AI assistant |
| **Language** | Speaks in the user's last-used language; Hindi/Hinglish with feminine forms (बोल **रही** हूँ, kar **sakti** hoon) |
| **Style** | Under 25 words per turn · one question then waits · addresses user as "{name} ji" |
| **Seller goal** | Help sellers respond to waiting buyers (unread enquiries, missed calls) |
| **Buyer goal** | Help buyers follow up on their requirements and connect with sellers |
| **Guardrails** | No selling, no price promises, no personal data disclosure, IndiaMART scope only |

The prompts are documented in [`docs/agent_prompt_buyer.md`](docs/agent_prompt_buyer.md) and [`docs/agent_prompt_seller.md`](docs/agent_prompt_seller.md).

---

## 🧩 Chrome Extension (Live IndiaMART Capture)

The demo page can show **live indiamart.com** inside a frame and capture real user actions:

- **Searches** (query text)
- **Product page opens** (title, supplier, price)
- **Button clicks** (Get Latest Price, Contact Supplier, Call Supplier, Send Enquiry, Shortlist, Reply, Call Buyer)
- **Product cards browsed** (items visible for >1 second, batched)

Each action is posted to `POST /events/{glid}`, the memory file rebuilds, and the agent's next greeting changes.

**Install the extension:**
1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder

> **Note:** IndiaMART sends `X-Frame-Options: sameorigin`, so the extension removes that header for the demo frame. In production, this capture script would be part of IndiaMART's own frontend.

---

## ✅ What's Real vs. Simulated in the Demo

| Channel | Status | Details |
|---------|--------|---------|
| **Voice** | ✅ Real | Sarvam Voice Agent with STT (Saaras), LLM (sarvam-m1), TTS (Bulbul). Memory loaded via `on_start` tool, call summary written via `on_end` tool. |
| **WhatsApp** | 🔶 Simulated | Message becomes a live event, reply generated by sarvam-m1 from fresh memory. Real WhatsApp requires Sarvam's enterprise channel. |
| **Website / Lead Manager** | 🔶 Simulated | Demo page uses real dataset items; clicks and scroll-views post web events. Chrome extension captures live indiamart.com. |
| **Data** | 📊 Organiser Dataset | 5,000 sellers, 302 buyers from the hackathon dataset. No invented users. |

---

## ⚠️ Known Limitations

1. **Widget identifier bug:** The Sarvam web widget sends `user_identifier`, but the agent's `on_start` tool receives it empty. The demo works around this by posting the selected GLID to `POST /active` — one on-screen user at a time.

2. **Tunnel URL changes:** `cloudflared` quick tunnels generate a new URL on each restart. Both Sarvam agent tools must be re-pointed and the agent re-committed. A static ngrok domain solves this.

3. **Draft vs. committed:** The Sarvam dashboard "Test agent" runs the **draft** version; the web widget runs the latest **committed** version. Always commit after prompt changes.

4. **No inbound phone number:** Inbound calls require a Sarvam phone number (not provisioned in the hackathon workspace). `data/phone_to_glid.json` maps caller numbers to GLIDs for demo purposes.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [`docs/agent_prompt_buyer.md`](docs/agent_prompt_buyer.md) | Full buyer agent prompt (synced from Sarvam dashboard) |
| [`docs/agent_prompt_seller.md`](docs/agent_prompt_seller.md) | Full seller agent prompt (synced from Sarvam dashboard) |
| [`docs/indiamart_facts_and_guardrails.md`](docs/indiamart_facts_and_guardrails.md) | Verified IndiaMART facts + 10-rule guardrails |
| [`docs/seller_call_insights.md`](docs/seller_call_insights.md) | Analysis of 9,657 past IndiaMART seller calls |

---

## 🙏 Credits

- **Ringback tone** on the demo phone: "UK ringback tone" by Lcmortensen, Wikimedia Commons, CC BY-SA 3.0 (`web/ringback.ogg`; the UK 400/450 Hz cadence matches what Indian networks use).
- **IndiaMART logo and product images** belong to IndiaMART InterMESH Ltd and its sellers; used only inside this internal hackathon demo.
- Built with [Sarvam AI](https://www.sarvam.ai/) and [FastAPI](https://fastapi.tiangolo.com/).

---

<p align="center">
  <sub>Built for the Voice AI Hackathon 2.0 by <a href="https://github.com/Ankulraja">Ankul Raja Patel</a></sub>
</p>
