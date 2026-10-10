# CLAUDE.md — VANI Context (Voice AI Hackathon 2.0)

This file is the handoff for any LLM session working in this repo. Read it first; it replaces
re-reading the hackathon PDF and the earlier chat. Keep it updated when the plan or state changes.

## How to work with the user

- The user is new to Python, AI/LLMs and voice bots. Explain in **simple, short English**. Avoid
  jargon; when a term is needed, define it in one line.
- **Since 2026-10-08 night: Claude does the work itself** (writes files, runs scripts, configures
  the agent via MCP). Tell the user in short simple English what was done and what was found. Do not hand
  them step lists any more unless something is only possible on their side (login, mic test, commit).
- **Always update CLAUDE.md** after each piece of work (state, findings, next step).
- Prefer tables and short bullet lists over long paragraphs.
- The user's day job is Next.js frontend (IndiaMART ads PDP). JS/Next.js is familiar; Python is not.
- Never print or commit the Sarvam API key. It lives in `.env` (git-ignored).
- The user is **Ankul Patel**, email `ankul.patel@indiamart.com`. The Claude Code login may show a
  different IndiaMART email; ignore it. Sarvam account / MCP login / Org ID = Ankul's email.
- Since 2026-10-09 ~16:00 IST the user wants replies in **simple English** again (was Hinglish before).
  Code, file names and commands stay in English.

## CURRENT STATE — read this first (2026-10-10 14:50 IST, hackathon Day 2; submission window 14:00–23:59 today)

Everything below this section is background and a dated build log (oldest first). This section is the whole picture now.

### What exists and works
- **Product:** a memory layer around Sarvam's hosted voice agent. `GET /context` builds `context_files/<glid>/{buyer,seller}.md`
  from the organiser dataset + live events, in ~2 s, and hands the agent a 10-line **call card**, a personalised **greeting**,
  an **opener**, next action and "avoid" line before its first word. New activity on any channel (`POST /events`, WhatsApp,
  website, call end) rebuilds the file (freshness ~1.5–2 s). Lookback: 30 d activity / 180 d conversations (README).
- **Two Sarvam agents, persona "Tanya"** (VANI = the service name; she introduces herself only as Tanya from IndiaMART):
  | Agent | id | live version | draft | default glid |
  |---|---|---|---|---|
  | VANI IndiaMART (**buyer**) | `VANI-IndiaM-b67b20da-8a1b` | v24 | v25 | 274238067 Aarti Singh |
  | VANI IndiaMART Seller | `VANI-IndiaM-61f2af95-c5b7` | v6 | v7 | 95568576 Alfa Enterprises |
  Same voice (Sarika - Conversational, `01a0cf16-97b2-…`, pace 1.1, single voice, no per-language mapping), same 4 tools,
  same API. Each prompt = Persona / Environment / Playbook A (IndiaMART called) / Playbook B (user called) / shared steps /
  Guardrails. The seller prompt has a section "What 9,657 past calls taught us" (from `docs/seller_call_insights.md`).
  **Since 13:36 IST (buyer v23 / seller v3) both prompts carry "## IndiaMART facts the agent may state" (verified from
  help.indiamart.com: matchmaking platform not party to the deal, helpline 096-9696-9696 7am-11pm, BuyLead vs direct enquiry,
  badges, Pay with IndiaMART closed 31 Mar 2024, Payment Protection Plan rules, safe-deal advice, Lead Manager, paid plans
  WITHOUT prices) and a 9/10-rule customer-care "## Guardrails" (identity, IndiaMART-only scope, truth, promises / no selling,
  money+OTP, privacy, disputes+complaints, respect, must-avoid). Sources + dataset evidence + chat test results:
  `docs/indiamart_facts_and_guardrails.md`; full prompt copies `docs/agent_prompt_{buyer,seller}.md` (the MCP `agents get`
  `include` param is ignored by this client, so the prompts were recovered from session transcripts; keep the docs copies
  in sync after every prompt edit). `configure_agent` takes `agent_id` + `prompt`.
  **13:55 IST seller helpline fix (user: DK Bean Bags heard "aapne thermocol ball ke liye enquiry ki thi"):** in `_call_lines()`
  a SELLER dialing the helpline now gets a plain welcome (name + "main Tanya, IndiaMART helpline" + "kya help chahiye"), no
  recall in the greeting; the latest RECEIVED enquiry is offered only in the opener in seller words ("aapko X ki enquiry aayi thi,
  buyer ko reply bhej doon?"). `CALL_LINES_PROMPT` has a vocabulary rule (buyer sends, seller receives); outbound fallback opener
  fixed for sellers; seller prompt Playbook B step 1 updated (committed v4). Buyers keep the recall in the greeting.
  **14:35 IST Tanya is female (user rule):** every prompt that writes her lines (agent Speaking style on both agents, buyer v24 /
  seller v5; API `CALL_LINES_PROMPT`, `WA_SEND_PROMPT`, `prefs.GREETING_RULE`, `insight.PROMPT`) says she uses feminine Hindi forms
  (बोल रही हूँ / kar sakti hoon), never masculine; `prefs.feminine()` is a code guard that rewrites राहा हूँ→रही हूँ, sakta→sakti,
  karunga→karungi etc. and is applied to greetings and call-intent openers. Users stay in neutral आप forms.
  **14:45 IST whole-memory answers (user: "not only the last activity"):** seller call card now has a `Health check (last 30 days)`
  line (enquiries received / unread / replies, buyer calls + missed, buyleads + credits, WhatsApp) and a rule-based `likely cause`
  line (no replies, unread >= 3, buyleads without replies, missed calls, < 5 products) in `call_card.py`; buyer card got an
  `Activity` line. Seller prompt has a new section "How a question or complaint is answered" (read the whole card, number first,
  then one question, offer to reply on their behalf; irrelevant leads -> categories; missing number -> get_more_history), committed
  v6. `HISTORY_PROMPT` reasons over the whole file from the user's side. Verified by send_chat on DK Bean Bags: "achhi enquiry nahi
  mil rahi" -> "aapke paas 24 enquiries unread hain aur 30 din mein ek bhi reply nahi, koi dikkat aa rahi hai?".
  **14:50 IST server check + 2 fixes:** API, tunnel and Sarvam egress all OK (public /health 200, Sarvam IP hitting /context and
  /events). Bug from the 14:45 card change fixed: buyer `sellers_contacted` is an int -> `len()` crashed `/context` for every buyer
  (TypeError in call_card.py); all 5 curated users rebuild fine now. Greeting topic: `prefs.latest_topic()` skips topic-less clicks
  (opened Lead Manager, helpline call, no-answer) so Alfa no longer hears "Lead Manager par baat karni thi"; both builders use it.
  Buyer chat on v24 through the tunnel recalled Aarti's WhatsApp message about the Duke e-rickshaw sent one minute earlier.
  Barge-in: hybrid VAD, no interruption dampening. Org `01a11128-bd2a-794c-a92a-5f518eacaba5`, workspace `01a11128-bd2f-7b40-9f2d-a2a3b2edf5d7`.
- **Tools on BOTH agents** (ids differ per agent and change on every commit → `agents get include=tools` before editing):
  `load_user_memory` (on_start, GET `<TUNNEL>/context?glid={{glid}}&uid={{user_identifier}}`, saves call_card→user_context,
  greeting, language→preferred_language, opener, next_action, avoid, name→user_name, role→user_role, glid),
  `get_more_history` (run, GET `/history?glid=&question=`, resp `{{answer}}`), `save_call_to_memory` (on_end, POST `/events`
  with glid, channel voice, summary=call_summary, language=user_language, outcome=call_outcome, callback_time),
  `send_whatsapp` (run, POST `/whatsapp/send` {glid, request}, resp `{{spoken}}`). Egress IP `4.213.167.70`.
- **Tunnel:** cloudflared quick tunnel, URL changes on every restart. Current `https://header-notebook-plastics-saying.trycloudflare.com`
  (also in `/tmp/vani_public_url.txt`). **Restart procedure:** `cd repo && nohup ./.venv/bin/uvicorn app.api:app --port 8000 --reload
  > /tmp/vani_api.log 2>&1 &` then `nohup cloudflared tunnel --url http://localhost:8000 > /tmp/cloudflared.log 2>&1 &`, read the URL
  from the log, then via MCP `configure_app_tool` ×4 per agent (8 calls, same connector_config with the new url) and `agents commit`
  ×2. If Tanya says "Hello ji" / "no recent activity" the on_start tool could not reach the API. MCP login expires daily (`/mcp`).
- **Call flows (demo page):** Flow A = IndiaMART calls the user: triggers are Get Latest Price on a product, Post Requirement,
  or a WhatsApp message that asks for help (`needs_help()` regex); phone rings, Tanya opens on that reason. Flow B = user calls:
  Call Now on a product (call dedicated to it) or 📞 Call Tanya (helpline, recalls latest activity). Mechanism: page `POST /active
  {glid, call:{direction, source, reason, label, product}}` → API `_call_lines()` writes greeting + opener + "THIS CALL:" card line
  with sarvam-105b; the agent's on_start fetch (uid path) gets them once, then the intent is consumed. Greetings always use the name
  (buyer first name, seller company). Memory records "VANI called X about …; picked up / no answer" and "X called VANI about …".
- **Mid-call WhatsApp:** when the user asks for details, Tanya says it is being sent and calls `send_whatsapp`; the API composes a
  Hinglish message (facts only, product/supplier links, photo) from the products in memory, with a live indiamart.com search when
  the requested product has no card (e.g. only talked about); it lands in `whatsapp_thread.json` + a whatsapp event; the demo's
  WhatsApp phone polls during the call and has a ↻ refresh button.
- **Demo pages (served by the API):** `/` = start page (`web/start.html`: GLID box + 10 curated users from `GET /users`; any dataset
  GLID works via `GET /lookup/{glid}`), `/demo#<glid>` = three screens (`web/demo.html`): WhatsApp phone (thread bot, photo
  messages, refresh), emulated IndiaMART website (real search results from `app/sources/im_search.py`, real home feed from
  `im_home.py`, PDP, ← → history, "Your recent activity" from memory, 3 CTAs per card: Get Latest Price / WhatsApp / Call Now;
  Live indiamart.com mode via the Chrome extension in `extension/`), call phone (helpline idle, ringback, keypad, Tanya labels),
  🧠 Memory drawer (file + "VANI will open with"). `web/config.js` (git-ignored) holds the embed key, `appId` (buyer) and
  `appIdSeller`; the page picks the agent by role. Old detailed page: `/index.html`.
  **Since 13:10 IST the embed key is NOT in a file any more:** `web/config.js` was deleted; the pages still load `/config.js`,
  but it is now an API route (`config_js()` in api.py) that builds `window.SARVAM_EMBED` from `.env`
  (`SARVAM_EMBED_KEY`, `SARVAM_ORG_ID`, `SARVAM_WORKSPACE_ID`, `SARVAM_APP_ID`, `SARVAM_APP_ID_SELLER`). api.py now calls
  `load_dotenv` itself. After rotating the key in the Sarvam dashboard: edit `SARVAM_EMBED_KEY` in `.env` and restart uvicorn.
- **Data:** organiser `Dataset/` (git-ignored, real names) stands in for the Day-1 APIs; `app/sources/seller.py` / `buyer.py` are
  the only files that know the raw layout. Curated demo users: buyers 274238067 Aarti Singh, 59681744 Ramesh, 274154429 Shinehomz,
  99718542 Akshay Chavan, 43279328 Prem Kumar; sellers 95568576 Alfa Enterprises, 253633098 Govind Enterprise, 35178044 DK Bean
  Bags, 87677035 Anuradha Oil Mill, 93557756 Visionary Style (hard case: 22 calls, said stop, met the executive).
- **Docs for the submission:** `README.md` (architecture, sources, lookback, refresh, real vs simulated, credits), `skills.md`
  (dated build journey, 15 % of the score; needs today's entries), `docs/seller_call_insights.md` (dataset analysis).

### Open items / risks (in priority order)
1. **DATA LEAK (needs the user):** commit ce91289 pushed `Dataset/` and `web/config.js` (Sarvam embed key) to the PUBLIC GitHub
   repo Ankulraja/vani-context. They are untracked now but still in history (commits ce91289, a55123c, 1707511). Needed: make
   the repo private, purge history (`git filter-repo --path Dataset --path web/config.js --invert-paths` + force-push), rotate the
   embed key in the Sarvam dashboard, put the new key in `.env` as `SARVAM_EMBED_KEY` (done 13:10: key moved out of the repo).
2. Uncommitted work in git right now: `app/api.py`, `web/demo.html`, `web/config.js.example`, `web/start.html`, `docs/`, `CLAUDE.md`.
   Branch `Ankul-main`; `main` is fast-forwarded to it after each push.
3. Tunnel URL is not static (ngrok static domain needs the user's ngrok account; `scripts/tunnel.sh` supports `NGROK_DOMAIN`).
4. Not yet done for the deck's success metrics: a measured "lift" of the personalised opening vs a cold greeting; the "app"
   channel is not shown; skills.md lacks the Day-2 entries; the 5–7 min demo video; the approach note.
5. Inbound telephony: no Sarvam phone number in the workspace; `data/phone_to_glid.json` maps caller numbers for the demo.
6. Seller-side triggers are thinner than buyer-side: Lead Manager "Reply" / "Call buyer" only save memory (no call); a new
   unread enquiry does not ring the seller yet.
7. Each call's memory is loaded once at call start (platform limit); mid-call changes are fetched on demand via get_more_history.

## The hackathon (facts from the deck, 31 pages)

- **Voice AI Hackathon 2.0**, IndiaMART, **9–10 Oct 2026**, in office (11th floor).
- Teams of **3**, at least **1 non-tech** member. One problem per team. Build on **Sarvam AI**.
- Team API keys/credits for Sarvam are given at the event; a "starter API list" of IndiaMART
  data sources for Problem 2 is given on **Day 1**. Until then we build on **mock data**.
- **Submission window:** Day 2, 2:00 PM–11:59 PM. Late = not evaluated. One submission per team.
- **Checklist:** demo video (5–7 min), problem + approach note, Sarvam Agent ID / live link,
  solution folder with code + README, `skills.md` (build journey and tools used), team details.
- **Rules:** no customer data leaves the premises; no pre-built/plagiarised solutions; all build
  work happens during the 2 days (setup/learning beforehand is fine).
- **Scoring (each juror 1–5 per criterion):** Business Impact 25%, Solution Completeness 20%,
  Technical Robustness 20%, Voice Experience 20% (natural, low-latency, Hinglish), Demo & skills.md 15%.
- Deck inconsistency: agenda says 7 problems, only 6 are described (Seller Enrichment is labelled
  "Problem 7 of 6"). Ask organisers if a 7th exists.
- The six problems: Quality Audit & Fix Loop; **Global Context: Memory Across Channels (ours)**;
  Best Time to Call; Persona Design; Agent A/B Testing & Auto-Rollout; Seller Enrichment.

## Our problem — #2 Global Context: Memory Across Channels

**Problem today (verbatim):** Each call or chat starts cold. The bot does not know what the buyer
searched, what the seller received, or what was said on WhatsApp yesterday, so users repeat
themselves and conversations restart.

**Challenge:** Make VANI already know the buyer or seller, and their past history, before it speaks.

**What to build (6 items from the deck):**
1. Context layer keyed to **GLID** (IndiaMART user id), pulling history from data sources we choose
   (starter API list provided on Day 1; other sources allowed).
2. `buyer.md`: enquiries filed, categories searched, sellers contacted, KYC status, past
   conversations, engagement signals.
3. `seller.md`: leads received, responses and call outcomes, categories and products, past
   conversations, engagement signals.
4. Bot loads the file before each call/chat, **opens with a personalised line**, and **resumes
   across voice, WhatsApp, chat and app**.
5. Files stay **short, structured, always up to date** — regenerated as new activity arrives.
6. We pick the right **lookback window** (how far back history goes).

**Expected outputs:** generated `buyer.md` + `seller.md` for sample GLIDs; a demo of a conversation
that **resumes across two channels**; a note on sources used, lookback window and refresh logic.

**Success metrics (what judges score):** freshness (delay from new activity → updated file);
compactness and structure of the files; conversations resumed without re-asking; lift from the
personalised opening; reusability beyond the bot prompt.

## The dataset (`Dataset/`, 69 MB, git-ignored, internal — real names inside, never commit/share)

The organisers gave data files that **stand in for the Day-1 APIs**. Explore with pandas; never
`cat` whole files. Data dictionary: `Dataset/Global Context - Seller Dataset/Global_Context_DATA_DICTIONARY.md`.

**Seller side** — 11 CSVs, 5,000 sellers, one row per event, 1 Apr–2 Oct 2026. Join key = seller
GLID, named `fk_glusr_usr_id` / `seller_glid` / `glid` depending on file.

| File | One row per | Rows |
|---|---|---|
| `gc_seller_profile.csv` | seller (69 cols: location, business, top categories, KYC flags, `eng_*` engagement, VANI bot history incl. `past_objections`, `showed_frustration`, `do_not_call_requested`) | 5,000 |
| `gc_enquiries_received.csv` | buyer enquiry to the seller (`message`, `product_name`, `read_status`, buyer city/company) | 33,006 |
| `gc_enquiry_messages.csv` | reply inside an enquiry thread (`message_from` buyer/seller, `reply_text`) | 17,633 |
| `gc_buyer_calls_received.csv` | buyer phone call to seller (Connected / Not connected, `talk_sec`) | 19,238 |
| `gc_buyleads_bought.csv` | buy-lead the seller bought (16 Aug–1 Oct only) | 14,852 |
| `gc_whatsapp_messages.csv` | WhatsApp delivery/read status, **no text** | 130,897 |
| `gc_whatsapp_chatbot_conversations.csv` | WhatsApp chatbot turn: `user_message` + `bot_reply` + `intent` | 83,280 |
| `gc_buyer_call_extractions.csv` | AI-extracted call details (`products_discussed`, `prices_quoted`); seller often acted as BUYER | 5,417 |
| `gc_bot_calls.csv` | answered VANI call: `lead_call_summary`, `disposition_label`, `meeting_fixed` | 9,657 |
| `gc_bot_call_turns.csv` | VANI call transcript turn (`speaker`, `text`) | 4,920 |
| `gc_executive_calls.csv` | IndiaMART executive call (Aug–Sep) | 2,580 |

**Buyer side** — one file, `Global_Context_Problem_Statement_Buyer Side.csv` (392 rows, 302 buyer
GLIDs). It is a Kibana export of API logs, with ~5,000 junk empty columns; only `GLUSR_ID`,
`REQUEST`, `RESPONSE`, `@timestamp` matter. Each `RESPONSE` is a JSON string from IndiaMART's
**existing internal API** `exchange.intermesh.net/go/api/globalcontext/v1/x/getContext`, holding a
raw buyer context: `ActualData` (glid, preferred_cities), `BLdetails` (active buy-leads),
`activitydetails` (`BUYER_ACTIVITY`, `LAST_ENQUIRY`, `LAST_LEAD`, `LAST_WA8181_CHAT`,
`LAST_WA9696_CHAT`, `enq_last_30_days`, `enq_last_90_days`, `last_4_week`/`last_3_month` stats).
Parse with `json.loads(row["RESPONSE"])["API_RESPONSE_JSON"]` then `json.loads` again. So the buyer
job is: raw getContext JSON → compact `buyer.md`.

## Sarvam AI — what it is and what we use

Sarvam sells building blocks, not a finished bot. A voice bot = ears + brain + mouth:

| Part | Sarvam product | Model id | Cost |
|---|---|---|---|
| Ears: speech → text | Saaras (STT) | `saaras:v4` | uses credits |
| Brain: text → text | Sarvam LLM | `sarvam-105b` (also `sarvam-30b`) | **free** |
| Mouth: text → speech | Bulbul (TTS) | `bulbul:v3`, speaker e.g. `shubh`, `language_code="hi-IN"` | uses credits |
| Voice Agents | hosted agent over telephony / WhatsApp / web widget | — | at event |

- SDK: `pip install sarvamai`; `client = SarvamAI(api_subscription_key=...)`; auth header is
  `api-subscription-key`. Docs: https://docs.sarvam.ai. Dashboard: https://dashboard.sarvam.ai.
- Personal key gives **₹100 free credits** (never expire). LLM is free → use it freely. Keep STT/TTS
  tests short to save credits; real build uses team keys at the event.
- Verified working on this laptop (2026-10-06): `scripts/test_sarvam.py` calls `sarvam-105b` and
  prints a Hinglish answer.
- **LLM GOTCHA (found 2026-10-08):** `sarvam-105b` has "thinking" ON by default and, for our prompts, it
  burns the whole `max_tokens` on reasoning and returns `content=None` with `finish_reason="length"`
  (even at 6000 tokens; `reasoning_effort="low"` does the same). **Always pass `reasoning_effort=None`
  explicitly** (SDK) / `"reasoning_effort": null` (REST). Then answers come in ~0.3–1 s.
  `sarvam-30b` is deprecated; available ids: `sarvam-105b`, `sarvam-105b-conversations`.

## Sarvam Voice Agents — verified from docs.sarvam.ai (2026-10-08)

The hosted agent (indus.sarvam.ai/samvaad, "Samvaad") is a **full bot with its own brain**. We do
NOT write the STT→LLM→TTS loop and we cannot plug our own LLM into it:

| Fact | Source |
|---|---|
| LLM inside the agent is picked by Sarvam (`sarvam-105b-conversations`); "no bring-your-own model at any part of the stack" | conversations/build/models |
| STT = Saaras v4, TTS = Bulbul v3/v4 (we pick speaker/language) | same |
| We control: **Greeting**, **system prompt (Instructions)**, **Variables**, **Tools**, **Knowledge base**, language settings | conversations/build/agent/overview |
| **API tool** = agent calls our HTTPS endpoint; lifecycle `run` (mid-call), `on_start` (before first word), `on_end` (after call). "Save reply into variables"; `@variable` chips go into greeting/prompt. Max wait ≤30 s. Sarvam egress IP to allowlist: `4.213.167.70` | conversations/build/tools/https-tool |
| Variables per call come from: telephony metadata (caller number), on_start hook response, campaign CSV columns, or `agent_variables` in the Instant Outbound API / Python SDK `InteractionConfig` | build/variables-personalization, api/instant-outbound/create, deploy/sdks/python |
| Channels: telephony in/out, **web widget (voice or chat)** via embed snippet, API/SDK (WebSocket), WhatsApp = enterprise-only on request | conversations/overview, deploy/overview |
| on_end hook pushes disposition, collected variables, transcript/recording refs to our URL | build/on-start-on-end-hooks |
| Agents API base `https://apps.sarvam.ai/api/...`, header `X-API-Key`, paths `/v1/orgs/{org_id}/workspaces/{workspace_id}/...` (this is the "Organization ID" organisers asked for) | conversations/api/introduction |
| Docs MCP server for building agents from Claude Code: `mcp.sarvam.ai/voice-agents`; any doc URL + `.md` gives clean markdown | conversations/mcp |

So **our product is the context layer around the agent**, not the agent itself:

```
IndiaMART data  (Dataset/ CSVs + buyer getContext JSON now; starter APIs on Day 1)
        │  app/sources/   fetch by GLID
        ▼
Context builder  raw events → sarvam-105b (chat-completion API, free) → buyer.md / seller.md
        │  app/builder/   short, dated, "last updated" line
        ▼
context_files/<glid>/{buyer,seller}.md          (+ FastAPI  GET /context/{glid})
        │                                        ▲
        │  on_start API tool: agent fetches       │  on_end hook / POST /events/{glid}:
        │  context → variable → prompt/greeting   │  new call summary → regenerate .md
        ▼                                        │
Sarvam Voice Agent (Samvaad)  ── telephony ── web widget (voice + chat) ── SDK
   same agent + same context file on every channel  ⇒  "resumes across channels"
```

Design decisions:
- **No invented mock data.** Organisers said not to; the `Dataset/` folder is the stand-in for Day-1 APIs. Build `app/sources/` on top of the CSVs and the buyer getContext JSON.
- Our backend must be reachable from Sarvam (public URL, e.g. ngrok/cloudflared) for on_start / on_end tools. Test this early on Day 1.
- GLID → agent: outbound = pass `agent_variables={"glid": ...}`; inbound = caller phone → GLID lookup inside our `/context` endpoint; web widget/SDK = `user_identifier`.
- Sarvam LLM is used in **two** places: (a) inside the agent (not our choice), (b) in our builder to write the .md (our choice, free).
- `.md` files stay under ~40 lines, sectioned, timestamped — reusable outside the bot (metric 5).
- Lookback window: to be decided (default idea: 30 days activity, 90 days enquiries).
- Fallback if the hosted agent is blocked at the event: own loop with Saaras + sarvam-105b + Bulbul via SDK.

## Build log — Sarvam agent + MCP + demo (chronological, oldest first; 2026-10-08 evening → now)

- Agent **"VANI IndiaMART"**, id `VANI-IndiaM-b67b20da-8a1b`, owner ankul.patel@indiamart.com.
  Org id `01a11128-bd2a-794c-a92a-5f518eacaba5`, workspace id `01a11128-bd2f-7b40-9f2d-a2a3b2edf5d7`
  (send org id to organisers). Dashboard: `indus.sarvam.ai/samvaad/build/update-agent/<id>?edit=true`.
- **Version 1 committed** (Day-0 memory demo). Draft is now **v2** — all further writes go to the draft.
- MCP `sarvam-voice-agents` is approved + authenticated (OAuth, re-login daily via `/mcp`). Tools seen:
  `agents` (list/get/list_voices/commit/translate/delete_tool), `configure_agent`, `create_api_tool`,
  `create_validator_tool`, `create_verifier_tool`, `configure_app_tool`, `send_chat`, `analytics`,
  `knowledge_base`/`configure_kb`, `configure_connection`/`configure_endpoint`/`configure_deployment`,
  `telephony`, `verify_phone_number`, `place_test_call`, `evals`/`run_eval`, `secrets`, `upload_agent_code`.
  Workspace limits: single-state agent only; no LLM model choice.
- **Read first before any agent write:** resource `sarvam://playbooks/agents` (build order, prompt
  style rules: English only, `##` headings, passive voice, no em dashes, "stop and wait", every tool/
  variable must exist before the prompt names it). Config schema sections:
  `sarvam://schemas/agent-config/{section}`; worked example `sarvam://examples/agent-config`.
  One configure write at a time; use `dry_run=true` first. Language names are "Hindi"/"English", not codes.
- Current v1 config (set via MCP, verified by text chat):
  - Variables: `user_name` (default "Rajesh"), `user_context` (default = Day-0 seller.md stand-in),
    `call_summary` (post-call extracted, already existed).
  - Intro (English source, platform auto-translates): "Hello, this is VANI calling from IndiaMART. Am I
    speaking with {{user_name}} ji?" → Hindi: "नमस्ते, मैं इंडियामार्ट से वाणी बोल रही हूँ। क्या मेरी बात
    {{user_name}} जी से हो रही है?"
  - Prompt (state `start`, ~2.5k chars): Persona / Environment / Objective / Speaking style / Facts
    (`{{user_name}}`, `{{user_context}}`) / Conversation guidelines (identity → recall latest item →
    help/no/busy → close with `end_interaction`) / Guardrails.
  - Language: initial Hindi, code-mixed colloquial style (Hinglish), LID on. Voice: "Ishita - Hinglish
    Support Agent" (`text_to_speech_config.internal_id` `01a0cf17-0b6e-79f0-b8ab-7392cabc497b`, TTS v4).
- Text test (`send_chat`, app_version 1) worked: after "Haan ji, Rajesh bol raha hoon" the agent
  itself recalled "kal Delhi buyers se 2 inch MS pipes ke liye 3 enquiries, 2 unread" and offered help.
  `send_chat` cannot inject variables — it uses the variable defaults, so for chat demos set the
  defaults; for phone/SDK calls pass `agent_variables`.
- **Agent wired to our API (2026-10-08 23:25, draft v2, NOT yet committed as a version):**
  - Variables now: `glid` (default "95568576"), `user_name`, `user_context`, `opener`, `next_action`, `avoid`,
    `call_summary` (post-call extracted). Prompt Facts section uses `{{user_context}}`, `{{opener}}`,
    `{{next_action}}`, `{{avoid}}`; guideline step 2 = "say the suggested first line, ask whether to continue".
  - Tool `load_seller_memory` (id 16bb8840-…, lifecycle **on_start**): GET `<TUNNEL>/context?glid={{glid}}`,
    save_to_variables context→user_context, opener→opener, next_action→next_action, avoid→avoid, name→user_name.
  - Tool `save_call_to_memory` (id bd0e64ac-…, lifecycle **on_end**): POST `<TUNNEL>/events`
    body {glid, channel:"voice", summary:{{call_summary}}}. **Known limitation:** `call_summary` is extracted
    AFTER on_end fires, so this POST arrives with an empty summary (API now skips empty summaries).
    Real path = Sarvam **call-end webhook** → `POST <TUNNEL>/webhook/sarvam` (payload schema
    `sarvam://schemas/webhook-payload`: `final_agent_variables.call_summary`, `interaction_transcript`).
    Set `webhook_config.url` on the deployment / campaign / instant-outbound call.
  - `<TUNNEL>` = cloudflared quick tunnel, **changes every restart**. Current: see `/tmp/vani_public_url.txt`.
    Start: `cloudflared tunnel --url http://localhost:8000` (log `/tmp/cloudflared.log`). After a restart,
    update both tools' URLs via MCP (`agents` delete_tool + `create_api_tool`, or dashboard Tools tab).
  - **End-to-end verified via `send_chat` (draft v2):** Sarvam's egress IP 4.213.167.70 hit
    `GET /context?glid=95568576`, and the agent's first line was "जी, आपने WhatsApp पर HP 16GB pen drive का rate
    दो सौ चालीस रुपये per piece बताया था। क्या मैं यह Barmer buyer को update कर दूँ?" — i.e. it resumed from
    the WhatsApp event. On end, `POST /events` arrived (empty summary).
- **Dashboard voice tests by the user (2026-10-08 23:38 and 23:49) passed for two GLIDs:** 95568576 (VANI said
  the ₹240/₹230 line unprompted) and **87677035 Anuradha Oil Mill** (file did not exist; Sarvam's on_start hit
  `GET /context?glid=87677035`, the API built seller.md on the fly and VANI opened with the oil enquiry).
  **on_end DOES deliver `call_summary` for voice calls** (both summaries landed in `events.jsonl`, e.g.
  "rescheduled a callback for tomorrow at 10 AM"); it was empty only for `send_chat` text tests. So the
  on_end tool is the live refresh path for voice; the webhook is the backup / production path.
  To switch the test user: dashboard → Variables → `glid` default value (user did this by hand).
- **`POST /webhook/sarvam` added and tested** with a fake payload (transcript, empty call_summary): the API
  summarised the transcript with sarvam-105b ("seller agreed ₹240/piece, ₹230 above 100 pcs, call back 11 AM"),
  appended the event, rebuilt seller.md in 1.76 s, and the next opener continued from it. Falls back to the
  last user line if the LLM fails. Reads glid from final/output/initial_agent_variables or user_identifier.
- **Buyer support on the agent (2026-10-09 00:00):** prompt is now role-neutral (uses `{{user_role}}`, buyer and
  seller objectives). New variable `user_role`. on_start tool recreated as **`load_user_memory`
  (id 938b670c-…)** with extra mapping role→user_role (old `load_seller_memory` deleted). `glid` default is
  now **274238067 (buyer Aarti Singh)** for the user's next dashboard test. `send_chat` test passed: first
  line was "आपने बताया था कि VP Precon का quote एक हज़ार आठ सौ पचास रुपये per bollard बहुत ज़्यादा है…" (from a live
  voice event posted to `/events/274238067`).
- **2026-10-09 11:15 IST: tunnel restarted** (old quick-tunnel URL died overnight). New URL
  `https://surrounding-supports-boats-buffalo.trycloudflare.com`. Both tools recreated on it:
  `load_user_memory` on_start id `b4cd36b1-…`, `save_call_to_memory` on_end (recreated). `glid` default
  back to **95568576**. User deleted `context_files/95568576/seller.md` on purpose to watch the API build
  it live during their dashboard test — do not pre-generate it.
- **2026-10-09 ~11:30 IST user voice tests after tunnel restart:** seller 95568576 (file built live, OK) and
  **buyer 59681744 Ramesh** (file built live; VANI opened with the 23 Sep glass hand bells enquiry). Buyer
  path is verified by voice too. `glid` default currently **59681744**.
- **2026-10-09 ~12:10 IST hard-case voice test passed: seller 93557756 Visionary Style Enterprise, Surat**
  (22 VANI attempts, told VANI on 18 Sep to stop calling, already met the executive). VANI recalled the
  executive conversation and did NOT pitch a meeting. Good "business impact" demo: memory stops the
  23rd pitch. Sheets to validate: gc_bot_calls (21 rows), gc_bot_call_turns attempts 296884 / 369610.
- **2026-10-09 12:30 IST agent finish:** voicemail set via `configure_voicemail` (English copy, detection on).
  Output variables added: `call_outcome` (enum resumed_and_helped / callback_fixed / not_interested /
  do_not_call / wrong_person / no_conversation, post-call extracted) and `callback_time` (post-call
  extracted). `evaluation_config` criterion "Conversation resumed" = call_outcome in
  [resumed_and_helped, callback_fixed]. Shared LLM prompt now forbids an opener that contradicts "avoid"
  (verified on 93557756: "Aapne bola tha ki executive aa chuke hain, abhi koi aur help chahiye kya?").
- **Agent v2 committed 2026-10-09 12:35 IST.** Draft is now v3.
- **Telephony (checked 12:36):** workspace has **no connections / numbers** (`telephony list_connections`
  = 0). So inbound ("user calls VANI") needs a number bought in the dashboard or given by Sarvam at the
  event. **Outbound test call works without a number:** `verify_phone_number(phone)` → user gets OTP →
  `verify_phone_number(phone, otp)` → `place_test_call(app_id, phone_numbers=[...], app_version=2,
  app_variables={"glid": "..."})`. Spends credits, rings a real phone. For inbound later: deployment
  with `webhook_config.url=<TUNNEL>/webhook/sarvam`; on_start tool should pass the caller number to
  `/context?phone=` (Sarvam call-context variable name for caller number still to confirm in the tool
  picker, labelled "User Identifier"). (playbook says required), commit v2, phone test
  (`verify_phone_number` → `place_test_call` with `app_variables={"glid": ...}`), web widget embed.

**2026-10-09 17:40 IST — "voice change not reflected on localhost" solved + v10 committed (draft now v11).**
- Cause: the dashboard "Test agent" runs the DRAFT; the web widget on `/demo` and `/` runs the latest COMMITTED
  version. The user changed the voice in the draft (v10) → widget still ran v9 (Ishita). Rule: **any dashboard
  change → `agents commit`** before testing on localhost.
- v10 = voice **"Chaitra - Conversational Voice"** (`01a0cf16-944c-…`; catalogue describes it as a Kannada showcase
  voice, user liked it in the dashboard), VAD 4/6/-40 (faster, more sensitive than v9's 6/8/-35), pace 1.15,
  **inactivity nudge 12 s** (was 5 s: "Hey, are you still on the call?" fired while people were still thinking),
  nudge text "Hello, are you there?" / "हैलो, आप सुन रहे हैं?".
- on_end tool `save_call_to_memory` recreated (id `4663424b-…`) and now also posts `outcome` (= `call_outcome`) and
  `callback_time`. API: `Event` has `outcome` / `callback_time`; `POST /events` **skips** outcomes
  `no_conversation` / `wrong_person` (test calls where nobody really spoke were becoming the newest memory and
  the next opener continued from "the user gave an unclear response"); a callback time is appended to the summary
  line. Webhook summariser now uses the real role (was always "seller"). `/call` default app_version → 10.
- Verified: `send_chat` on v10 → "अच्छा, तो आपको SanDisk Memory Card की enquiry आई थी, क्या आप उसका reply देना चाहेंगे?".
- Sarvam analytics MCP reports (attempts / interactions / tool_table) timed out at 17:30 IST; retry later.
- Analytics (worked at 17:45 with a 25-min window): widget calls have agent response time ~0.6 s; `user_id` for
  widget calls = the page's GLID, dashboard calls = hashed email. Greeting once came out "नमस्ते आरती ji, आप कैसी हैं?"
  despite the rule → `prefs.clean_greeting()` now fixes कैसी→कैसे and strips "ji/जी" after the name in code.

**2026-10-09 17:55 IST — "make all the changes" round (user asked to apply the review):**
- Memory file: new Flags line `- Recent VANI calls (live): 9 Oct resumed_and_helped · …` (`seller_md.recent_calls_line`,
  outcome only, newest first; "summary noted" for events saved before outcomes existed).
- `/demo`: freshness number stays visible ("updated 40 s ago · freshness 1.6s"). Captions: verified in the embed
  source (`sarvam-convai-embed@1.0.19`) that the widget logs user speech as `console.log("Transcript:", json)`
  (`server.event.transcription`) and VANI's lines as `console.log("Text message:", obj)` (`server.media.text`); the
  hook now listens to both. Field names inside those messages still unverified by a real mic call.
- Greeting prompt has a seller example ("आपको X की enquiry आई थी"); seller fallback greeting names the latest enquiry.
- README.md written (architecture, sources, lookback 30/180 d, refresh logic, real vs simulated table, limitations,
  run). skills.md started as the dated journey log.
- **Test memories reset:** `DELETE /events/95568576` and `/274238067` (today's junk test calls / "tshirt" search).
  Backups in `context_files/_backups/<glid>.jsonl`. New openers: Alfa = HP Pen Drive 16gb enquiry; Aarti = Concrete
  Cylindrical Bollards quotes.
- **ngrok installed** (`brew install ngrok`, v3.39). `scripts/tunnel.sh`: uses a static ngrok domain when
  `NGROK_DOMAIN` is in `.env` (user must sign up at dashboard.ngrok.com, `ngrok config add-authtoken …`, claim the free
  static domain), else falls back to cloudflared. Once static: set both tool URLs once, commit, never re-point again.
- **18:05 IST `/demo` rebuilt as three channel screens (user request):** left = WhatsApp phone, middle = website
  browser, **right = a separate call phone** (idle screen with "VANI will open with" greeting + opener + which event
  it comes from, "☎ VANI calls <first name>" button → incoming → in-call with captions → "Call ended / ✔ Saved <summary>"
  screen). The memory file moved to a **slide-out drawer** (🧠 Memory button in the top bar, freshness badge on it;
  deep link `&mem` opens it). Browser panel unchanged, user wants to discuss it in detail next.
- **18:30 IST `/demo` visual pass:** WhatsApp phone now dark theme with WhatsApp Web's own default wallpaper tile
  (`web/wa-bg.png`, dimmed), real IndiaMART logo DP (`web/im-logo.png`, 57 px app icon from indiamart.com), name
  "IndiaMART" + blue tick. Whole page restyled to the user's design language (screenshot of their Test.IM dashboard):
  warm light canvas `#f1f1ee`, white 24 px cards with title+subtitle, floating pill top bar (brand / user chips /
  memory+reset+avatar), black primary pills, grey text. Memory drawer is a white card with a black "VANI will open
  with" box (class `openbox`; it was `.open`, which collided with `.drawer.open` and painted the drawer black).
- **Real indiamart.com in the middle panel is NOT possible:** all IndiaMART hosts send `x-frame-options: sameorigin`.
  Proposed instead (user to confirm "go with A"): a Tampermonkey userscript / bookmarklet on the real site that posts
  searches, product views, Get Latest Price / Call Supplier clicks to `POST /events` with the active GLID.
- **18:50 IST option 2 built: Chrome extension `extension/` (MV3, Load unpacked).** `rules.json` strips
  `x-frame-options` / CSP on `*.indiamart.com` main+sub frames so `/demo` can iframe the real site; `capture.js`
  content script (all frames) captures search (`?ss=`/`?q=`, form submit, Enter in a search box), `/proddetail/`
  page opens (h1 + supplier + price), clicks on Get Latest Price / Contact Supplier / Call Supplier / Send Enquiry /
  Shortlist / Reply / Call buyer, and 1-s dwell on product cards (batched); shows a black on-page badge; sends via
  `chrome.runtime.sendMessage` → `background.js` → `GET /active` → `POST /events/{glid}` (channel web, meta.source
  chrome-extension); also `postMessage({vani:"url"|"event"})` to the parent demo page. API now has CORS allow-all.
  `/demo` website card has an **Emulated / Live indiamart.com** segmented toggle (localStorage `vani_site_mode`,
  deep link `&live`), editable URL bar + ⌂ in live mode, listens for the frame's postMessages and polls `/events`.
  Headless Google Chrome ignores `--load-extension` (removed in Chrome 137+), so testing uses Playwright Chromium
  (`pip install playwright` in .venv, script `$CLAUDE_JOB_DIR/tmp/ext_test.py`). **Tested 19:05 IST: PASS** — with
  the extension loaded, `/demo#…&live` rendered the real www.indiamart.com home inside the frame (title + h1 read
  back), and a real tab on `dir.indiamart.com/search.mp?ss=pen+drive` produced the event
  `Buyer searched "pen drive" on indiamart.com` in `events.jsonl` via background → `/events/{glid}`. Clicks and
  product-page capture are not yet exercised (need a real mouse). Found and fixed: the hidden emulated panel's
  dwell observer fired on layout shifts while in live mode → observer disconnected in live mode. Test events
  removed from 274238067 (backup `_backups/274238067_before_exttest.jsonl`). Login inside the frame is untested
  (third-party cookie rules may block it; the same extension works in a normal tab as fallback).
- **19:00–19:20 IST user loaded the extension and tested live mode on Aarti 274238067:** captured from the REAL site:
  `searched "tshirts"`, `opened the product page Brown Round Param Agar Wood Agarbatti, Thickness: 3 mm, ₹ 480/Dozen`
  (price read from the page, supplier name NOT found → improve selector), `searched "Diesel Engine Pump Sets"`
  (export.indiamart.com). Fixes made during the test: (1) API skips a duplicate web line within 10 min (search page
  loaded twice); (2) `capture.js` `isQuery()` ignores URL/hostname/email values (a form field with
  "export.indiamart.com" was logged as a search) → user must press the refresh icon on chrome://extensions;
  (3) greeting now names the NEWEST live event: `greeting_rule(..., latest=<newest live summary>)` in both builders
  (before, the LLM kept the dataset topic "Concrete Cylindrical Bollards"); (4) insight prompt says the "no more
  help" example must not be copied (one rebuild had produced exactly that line). Verified: greeting "नमस्ते आरती,
  आप कैसे हैं? Diesel Engine Pump Sets के बारे में बात करनी थी…", opener continues from that search.
  Not yet seen: a click event (Get Latest Price etc.) and a voice call after a live-site action.
- **23:10 IST WhatsApp bot rewrite (user: "acknowledge the question, ask further; never say VANI will call"):**
  `POST /whatsapp/{glid}` now keeps a thread in `context_files/<glid>/whatsapp_thread.json` (user+bot turns,
  `GET /whatsapp/{glid}` returns it; demo page re-renders it on load; reset deletes it). Prompt = recent chat first,
  then the memory card as BACKGROUND, but the full card is passed only when the message touches memory
  (enquir/buyer/lead/rate/quote/… or a ≥5-letter word that appears in the card); otherwise only the card's first
  line (who they are). Rules: reply is about the last message, ONE next question, concrete "when" answers (quotes
  come on this chat in a few hours), confirm agreed steps, no made-up counts, output only the message (last paragraph
  kept, labels stripped; sarvam-105b sometimes thinks aloud first). temperature 0.2. Replays verified for seller
  87677035 (air purifier thread + "aur meri oil enquiry ka kya hua?" → answers from memory) and buyer 274238067.
  Demo page no longer prints "🧠 VANI now knows this · Xs" in the chat (freshness only in the top badge).
  Known wobble: a seller who is BUYING in chat sometimes gets seller wording ("dispatch", "verified buyers").
- **23:15 IST tunnel died** ("Unauthorized: Tunnel not found" in cloudflared.log) → VANI said "no recent activity"
  (fallback MEMORY NOT LOADED). Restarted: new URL `https://sullivan-packs-interval-flexibility.trycloudflare.com`.
  **Tools updated IN PLACE with `configure_app_tool(tool_id=…)`** (no delete/recreate, prompt untouched):
  load_user_memory `52f351cf-…`, get_more_history `41d75e70-…`, save_call_to_memory `279cf344-…`. The user had
  committed v11 themselves; **v12 committed 23:20 IST** with the new URLs, draft now v13. MCP login expired at
  ~23:10 and the user re-ran `/mcp`. Reminder: on any tunnel restart → `configure_app_tool` ×3 + `agents commit`.
- **23:30 IST mid-call refresh (user: "does VANI know mid-call updates?" → was NO; now on demand): v13 committed,
  draft v14.** Memory is still loaded once at call start (platform limit for the widget), but prompt step 3 now
  tells VANI to call `get_more_history` also when the user says they just did something on WhatsApp / website
  ("maine abhi WhatsApp pe bheja"); tool description + question hint updated (tool id in v13 draft was
  `f3656139-…`; ids change on every commit → always `agents get include=tools` before `configure_app_tool`).
  `/history` now prepends LIVE EVENTS (fresh, newest first, with today's date/time) and the WhatsApp thread.
  Verified by send_chat on v13: WhatsApp message posted mid-chat → "Maine abhi WhatsApp pe … bheji hai, dekho" →
  VANI: "मैंने देख लिया। आपका budget दो हज़ार पाँच सौ रुपये per chair है और आपको दस office tables भी चाहिए…" (~1 s).
- **23:45 IST skills.md updated** with the full evening log (v10→v14: voice tuning, call outcomes, greeting guard, three-screen demo, Chrome extension, ngrok option, WhatsApp thread bot, mid-call refresh) + new tools in the table. Day-2 open items listed at its end. Not yet committed to git.
- **2026-10-10 00:05 IST emulated website now searches the REAL indiamart.com** (user request: "whatever I search, search through the actual indiamart and show the cards here"). `app/sources/im_search.py`: the desktop search API (`dir.indiamart.com/api/search.rp`) refuses outside IPs (429 "Source IP not allowed") and the desktop page renders 0 results even in a real headed Chrome; the MOBILE page `m.indiamart.com/isearch.php?s=<q>` (fetch with a phone UA) is server-rendered and embeds the result list as JSON (`let mcatCardsData1 = [...]`, each card has the full record under `rawData`). Parsed with `json.JSONDecoder.raw_decode`, ~0.2 s, cached 10 min per query. `GET /search?q=` returns title, price_text, moq, company, city, member_since, gst_verified, rating(+count), image (https), url, seller_glid, specs. `/demo` buyer panel: search box → `paintResults(q)` renders the real listings (image, price, supplier, rating) under "Results for …" with a "← Picked for you" link; Get Latest Price / Call Supplier / card click post events that name the real product, supplier, city and price. Scroll-capture re-armed via `armObserver(site)` (extracted from renderSite). Verified headless (Playwright): 10 real cards for "pen drive", event text `Buyer sent an enquiry on indiamart.com for Card Pen Drive from Techsol, Navi Mumbai (₹ 190/Piece) (Get Latest Price)`. httpx added to requirements.txt. Seller panel (Lead Manager) unchanged.
- **2026-10-10 00:15 IST emulated site restyled + 3 CTAs per card (user request):** header now IndiaMART-like (white 56 px bar, real wordmark `web/im-wordmark.png` from hm.imimg.com/template-mdc/imLogo1.png, location pill, grey search box with teal 🔍 button `--im-teal:#1d8480` = the real site's button colour, "Get Best Price" outline, Exporters/Sell/Help/Messages/user nav; page background #e9eaea). Cards fixed 236×392 px (title 2-line clamp, image 150 px, CTAs pinned to the bottom). CTAs: **Get Latest Price** (web enquiry event), **💬 WhatsApp** → `productToWhatsApp(it)` puts "Hi, I am interested in <product> from <supplier>, <city> (<price>)…" into the left WhatsApp phone and sends it (= whatsapp event + bot reply), **📞 Call** → `productCall(it, summary)`: refuses with a toast if a call is ringing / in progress (`callBusy()`), else awaits `act()` (web event "Buyer clicked Call on indiamart.com for …", memory rebuilt) and then clicks #ring so VANI calls about that product. `act()` now returns the post promise. Headless test passed (card 236×392, 3 buttons, WhatsApp bubble, incoming screen, "call already in progress" toast).
- **2026-10-10 00:30 IST emulated HOME rebuilt like www.indiamart.com** (user: "home page also good IndiaMART looking"): `paintPicked()` now renders the real site's layout: blue hero ("India's Largest Online B2B Marketplace", welcome + active requirement, pills Post Requirement / View my quotes), stats strip (21Cr+ buyers…), "Picked for you" round-image tiles on the blue→grey gradient (the user's dataset categories/keywords), then 3 "Explore" rows (one per top category) of 6 real product cards, and a Lens banner. Tile images and row cards come from `GET /search?q=<category>&limit=6` fetched in parallel after paint (skeleton shimmer meanwhile; guarded by `lastSite !== s` on user switch). Tile / "View all" → runs the search; row card click → "opened the product page X from Y (price)" event; hero pills → events. Verified headless: 8/8 tiles got real images, 3 rows × 6 cards, tile click → results, back → home. Seller Lead Manager panel unchanged.
- **2026-10-10 00:45 IST home shows DIFFERENT categories** (user: "why same category, add different"): Aarti's dataset items are all bollard/pipe variants, so `paintPicked` now (1) collapses near-duplicates by key word (max 3 "Picked for you" tiles), (2) adds a real **"Trending on IndiaMART"** tile row and (3) three real **"Explore by Industry"** rows (Automobile / Housewares / Handicrafts…) after the one own-category row. Source: new `app/sources/im_home.py` → `GET /home-feed` parses www.indiamart.com (server-rendered, 0.13 s, cached 1 h): 18 trending names+images, 8 industries × 6 products. Any tile / industry card click runs that search. Verified headless: picked = [RCC Precast Bollard, Ductile Iron Pipe], trending 6 real tiles, rows = own + 3 industries, click → results.
- **2026-10-10 00:50 IST card CTAs final + WhatsApp with photo:** CTA row = full-width "Get Latest Price" (teal, chat icon) then 50/50 "WhatsApp" (white, teal border, green WA icon) / "Call Now" (teal, phone icon), inline SVG icons (`ICON`), card 252×396. Website-action toasts (📝 / 👁) removed (user: don't show). **WhatsApp CTA sends a media message:** `sendWhatsApp({image, product})` → bubble shows the product photo (`.msg .pic`) above the text; `POST /whatsapp` `WhatsAppMsg` now has optional `image` / `product`, stored on the user turn in `whatsapp_thread.json`, and the thread re-render on load shows the photo again. Tested end-to-end on Aarti (files restored from backup afterwards).
- **2026-10-10 01:00 IST emulated browser: ← → history** replaced the mac dots. `navStack`/`navPos` of entries {type:'home'} / {type:'results', q, focusId}; `paintPicked` and `paintResults` push (unless `navSilent`), ← → re-run the painter for that entry; a new search drops the forward entries; user switch / seller view resets. Own-category row cards now open the listing with that product highlighted (`paintResults(q, display_id)`, `.card.focus`) after saving the "opened the product page" event (before: event only, looked unclickable once toasts were gone). Headless test: 2 searches → back, back (home), forward, new search all correct.
- **2026-10-10 01:10 IST PDP + "Your recent activity" (user request):** clicking a product card / own-category row card opens an IndiaMART-style product page (`paintProduct(x, q)`: breadcrumb, 300 px image, title, price+MOQ, specs table from `specs`, supplier box with GST/rating/years, the 3 CTAs; URL = real proddetail URL; history entry type `product`). Web events now carry structured `meta`: `{kind:'search', q}`, `{kind:'view', q, product:{…full card…}}`, `{kind:'enquiry', product}` (`act(summary, meta)` → `postEvent(channel, summary, meta)`). Home page has a new white "Your recent activity · loaded from <name>'s memory" section under the stats strip: recent-search chips (click = search again) and "Products you viewed" mini cards (click = PDP again), both read from `GET /events/{glid}` web events with meta; older events without meta fall back to plain summary lines. Tested with real events on Aarti (restored afterwards).
- **2026-10-10 01:40 IST two call flows + call intents (user design):** call phone idle screen = "IndiaMART helpline" + **📞 Call VANI** button (no "VANI will open with" box; the preview stays in the memory drawer). **Flow A, VANI calls the user (outbound):** triggers = Get Latest Price on a product (1.5 s after the enquiry event), Post Requirement pill, a WhatsApp message that asks for help (`needs_help()` regex in api.py, `needs_call` in the `/whatsapp` response; negations like "koi dikkat nahi" excluded). Phone shows "IndiaMART is calling you… About <label>" + VANI's planned first line; Accept → widget call; Decline → missed. Memory records `voice` events "VANI called Aarti about the enquiry for X; Aarti picked up / no answer" (`meta.kind` vani_call). **Flow B, user calls VANI (inbound):** Call Now on a card → call dedicated to that product; dial button → helpline call where VANI recalls the latest activity and asks what help is needed. Records "Buyer called VANI about X" / "Buyer called the IndiaMART helpline" (`meta.kind` user_call). **Mechanism (no agent change):** page `POST /active {glid, call:{direction, source, reason, label, product}}` → API `_call_lines()` writes greeting + opener for THAT call with sarvam-105b (~0.6-1 s, template fallback) + a `card_line` ("THIS CALL: …"), stored in `_active.json`; the agent's on_start `GET /context?glid=&uid=` (uid path) returns them as `greeting`/`opener` and prepends the card line to `call_card`, then the intent is consumed (`DELETE /active/call`; also cleared on call end). Verified: all three intents via API (greeting override, consumed after one fetch) and in the browser (enquiry → incoming screen with reason, decline → record; Call Now → "Calling IndiaMART…").
- **01:55 IST outgoing-call sound:** Call VANI / Call Now now ring immediately with `web/ringback.ogg` (real network recording from Wikimedia Commons, CC BY-SA 3.0, credited in README) looped via an `Audio` element, minimum 2.5 s, then a pickup click, "VANI answered" → "IndiaMART helpline · VANI". The synthesised oscillator ring is kept only for the INCOMING screen. Note: two parallel `.venv/bin/python` heredoc runs hit a sandbox PermissionError on pyvenv.cfg; run such edits serially.
- **02:10 IST in-call keypad:** emoji buttons replaced by an iOS-style grid (mute, keypad, speaker, add call, video, contacts; SVG icons, translucent round keys) + red SVG end key; incoming screen has red/green SVG decline/answer keys. Only mute and end work: mute toggles a white 'on' state, sets status "Muted", and disables audio tracks of mic streams (getUserMedia is wrapped to keep handles; the widget's shadow-DOM media is tried too); dummy keys toast "X is not available in this demo". Outgoing minimum ring raised to 4 s. **Sandbox issue since ~01:15 IST:** shell children get EPERM on the project dir (`.venv/pyvenv.cfg`, `os.getcwd()`), even with the sandbox disabled → headless Playwright checks are blocked; the Read/Edit tools and the running uvicorn are fine. Likely macOS Files-and-Folders permission for the terminal; user to re-allow.
- **2026-10-10 01:45 IST VANI sends WhatsApp mid-call (user request):** new run tool **`send_whatsapp`** (id 973967b3-…, draft v14) → `POST <TUNNEL>/whatsapp/send` body {glid:{{glid}}, request:<llm_prompt>}, resp_template `{{spoken}}`. API `whatsapp_send()` composes the message with sarvam-105b from the products the user touched (events meta product, `_active.json.last_call.product`), seller enquiries and the call card: Hinglish, one fact per line (📦💰🏢📍⭐🔗 with real product + supplier links), appends a bot turn (`via:'call'`, product image) to `whatsapp_thread.json`, posts a whatsapp event "VANI sent on WhatsApp during the call: …". Prompt step 4 (details are sent on WhatsApp, never read digit by digit; say it in one line + call the tool in the same turn); `tool_names` = [get_more_history, send_whatsapp]. **Bug found via the chat trace:** the tool fired but got HTTP 422 because `POST /whatsapp/{glid}` was declared before `/whatsapp/send` ("send" parsed as GLID) → route moved above it; a `RequestValidationError` handler keeps the last 10 rejected bodies at `GET /debug/422`. Verified through the tunnel with the exact tool body: a real message with Powerpace Energy details + links landed in Aarti's thread. `/demo` polls `/whatsapp/{glid}` every 3 s during a call and 90 s after and shows new bot turns (image + text, sysline "📲 Sent by VANI during the call"). **Draft v14 NOT committed yet** → the widget still runs v13 without the tool until `agents commit`. TODO: strip tracking tags from `supplier_url` in `app/sources/im_search.py` (`.split("?")[0]`) and in the "supplier page" line of `whatsapp_send()`.
- **~01:15 IST macOS revoked the terminal/Claude app's access to ~/Desktop** (TCC "Files and Folders"): `ls ~/Desktop` → Operation not permitted; Read/Edit tools, python in the venv and the MCP project approval (stored in `.claude/settings.local.json`) all failed. uvicorn kept running. Fix = System Settings → Privacy & Security → Files and Folders (or Full Disk Access) → allow Desktop for the app running Claude Code, then restart Claude Code and re-approve + authenticate the MCP via /mcp.
- **2026-10-10 02:00 IST (new session after the macOS block; Desktop access restored):** pending note merged into CLAUDE.md, supplier links cleaned. WhatsApp phone header now has a **↻ refresh button** (`#waRefresh`): fetches `/whatsapp/{glid}`, appends any turns after `waKnown` (user → out bubble, bot → in bubble with photo, `via:'call'` → sysline), says "No new messages" otherwise; `waKnown` is set from the thread rendered at load. **Agent v15 commit still pending:** the MCP server keeps answering "needs you to sign in again" even after re-approval; the user must complete the OAuth login via /mcp, then `agents commit`. Demo widget therefore still runs v13 (no send_whatsapp) until then.
- **2026-10-10 10:40 IST morning restart (Day 2):** laptop slept overnight → uvicorn + cloudflared dead, old tunnel gone, MCP login expired. Restarted both (`nohup .venv/bin/uvicorn app.api:app --port 8000`, `cloudflared tunnel --url http://localhost:8000`), new URL **`https://header-notebook-plastics-saying.trycloudflare.com`**. User re-authenticated MCP. The user had committed up to v18 themselves overnight; draft was v19 with all 4 tools still on the dead URL (API log showed only 127.0.0.1 requests, none from Sarvam) → `configure_app_tool` ×4 in place (load_user_memory c637b3f6, get_more_history c0ba1fce, save_call_to_memory 6ee3b860, send_whatsapp 5f081a67), **v19 committed → draft v20**. send_chat on v19 opened with Aarti's latest activity (7.5 KVA diesel generator) = memory reaches Sarvam again. Tool ids change on every commit: always `agents get include=tools` first.
- **10:45 IST WhatsApp-from-call verified live on v19** (Sarvam IP → `POST /whatsapp/send` 200, message + photo in Aarti's thread). Quality bug: Aarti had only TALKED about a generator (voice summary), never clicked one → no product card → the message used the last clicked product (scooter battery). Fix in `whatsapp_send()`: a 30-token sarvam-105b call extracts the product named in the request; if no known card matches its words, `search_indiamart(want, limit=3)` fetches real listings and they are listed FIRST (`live_note` in the prompt). Note: uvicorn was started WITHOUT `--reload` this morning → restart it after api.py edits (`pkill -f 'uvicorn app.api' && nohup .venv/bin/uvicorn app.api:app --port 8000 ...`).
- **10:50 IST greet by name (user rule):** call-intent greetings (`_call_lines`) now always address the user by name: prompt rule + `_ensure_name()` guard inserts the name after नमस्ते/Hello if the LLM drops it; buyers by FIRST name, sellers by company name; Hindi greetings must be Hindi sentences (English only for product names). Normal greetings already used the name.
- **11:00 IST GIT / DATA LEAK FOUND:** `.gitignore` had `Dataset` and `web/config.js` glued on one line (`Datasetweb/config.js`) → the user's commit ce91289 (9 Oct) pushed the whole 69 MB organiser **Dataset/** (real customer names) and **web/config.js** (Sarvam embed key) to **public** GitHub repo Ankulraja/vani-context. Fixed going forward: `.gitignore` repaired, both untracked (commit on Ankul-main, fast-forwarded to main, pushed). Side effect: the ff on main deleted the working copies (restored from a55123c with `git restore --source … --worktree`). STILL OPEN (user decision): rewrite history to purge them (`git filter-repo --path Dataset --path web/config.js --invert-paths` + force-push both branches), make the repo private, rotate the Sarvam embed key in the dashboard and update web/config.js. .DS_Store also ignored + untracked.
- **11:15 IST persona renamed to Tanya (user request):** the agent introduces herself as "Tanya from IndiaMART" (VANI stays the product/service name). Changed: agent prompt Persona + steps 1 (who is calling / wrong person), voicemail message (`tool_runner_parameters`), **committed v20 → draft v21**; API `CALL_LINES_PROMPT` / fallbacks / `WA_SEND_PROMPT` say Tanya; demo call phone shows "Tanya" (avatar T, Call Tanya, Tanya answered, helpline · Tanya, missed call / sent-by lines). Memory event summaries still say VANI (product) on purpose.
- **11:25 IST barge-in fix (user: "when I interrupt she does not stop"):** `allow_interrupt_during_playback` was already true, but `vad_config.primary_vad` was `basic-vad` and `probability_modulator_config` was null = Sarvam defaults that DAMPEN interruptions while the bot speaks (×0.5 for the first 2 s, ×0.8 after). Changed to `hybrid-vad`, resist duration 0.6 s, start multiplier 0.85, speaking multiplier 1.0 (no dampening), end-of-speech boost 1.5 kept; frames 4/6/-40 kept. Committed as v21 → draft v22. Voice on the agent = **Sarika - Conversational Voice** (`01a0cf16-97b2-…`), single voice, no per-language mapping, pace 1.1 (user changed it overnight from Chaitra). Still user-side: use earphones on the demo so Tanya's own audio does not feed the mic.
- **11:45 IST seller call analysis (user request) → `docs/seller_call_insights.md`.** Key numbers: VANI→seller calls end Not Interested 42 %, General 30 %, Call later 16 %, Meeting fixed 11 %; 19 % hang up abruptly; VANI's pitch is a sales-executive meeting in 30 % of calls; avg 3.8 attempts/seller, 341 sellers called 10+ times, 496 sellers still called 5+ times after 2× Not Interested; 521/1,267 sellers with enquiries replied to none. Seller→IndiaMART WhatsApp: 89 % of typed turns are the BUY-LEAD flow (seller acting as buyer); real support asks = photo/document uploaded but not added as product (925), product price/details, phone number requests, catalog management, stop-calls (23), complaints/call-me. Implications listed in the doc (no re-pitch after 2× NI, open with unread enquiries, honour callback times, treat seller-on-WhatsApp as buyer).
- **12:05 IST TWO AGENTS (user decision: one per role, not four):** **buyer agent = existing `VANI-IndiaM-b67b20da-8a1b`** ("VANI IndiaMART", committed v22, draft v23; glid default 274238067, user_role buyer) and **seller agent = clone `VANI-IndiaM-61f2af95-c5b7`** ("VANI IndiaMART Seller", committed v1, draft v2; glid default 95568576, user_role seller). The clone copied all 4 tools on the current tunnel (seller tool ids: load_user_memory de106a1a, get_more_history 8f581f67, save_call_to_memory 436b3d19, send_whatsapp 108906c0) → **every tunnel restart now = 8 `configure_app_tool` calls + 2 commits**. Prompts: shared Persona/Style/Guardrails; each has Playbook A (IndiaMART called) and Playbook B (user called) for its role; the seller prompt encodes the dataset insights (never pitch a meeting/paid plan unless asked, open with unread enquiries, honour callback, catalog/photo asks, stop-calls). Prompt gotcha: `tool:name.` with a trailing period is parsed as a tool name → write "the tool:name tool, as described in step N". `web/config.js` (+ example) has `appIdSeller`; `ensureWidget()` picks the app-id by `user.role` (re-mounts the widget when the agent changes); `/call` picks `SARVAM_APP_ID_SELLER` for sellers.
- **12:15 IST seller agent now carries the dataset insights explicitly** (section "What 9,657 past IndiaMART calls to sellers taught us": 30 % meeting pitch / 42 % NI / 19 % hang-ups → never pitch unless asked; 36 s avg → value in first two turns; 14 % busy → one question for a time; repeat calling after 2× NI → acknowledge + enquiries only; 3 % 'bot?' → one honest line; already-paid / executive-visited → never contradict; free is enough → agree; 41 % never replied to enquiries → read the latest unread enquiry; denied callback → accept; WhatsApp = catalog/photo asks and 89 % seller-as-buyer → help as buyer). Playbook B gained a 'seller wants to BUY' branch. **Seller agent committed v2 → draft v3.** Hard-case test target: 93557756 Visionary Style.
- **12:30 IST start page (user request):** `GET /` now serves `web/start.html` (old detailed page stays at `/index.html`): GLID box + dropdown + cards of 10 curated users (`GET /users` → `DEMO_USERS` in api.py, scored from the dataset: buyers Aarti Singh 274238067, Ramesh 59681744, Shinehomz 274154429, Akshay Chavan 99718542, Prem Kumar 43279328; sellers Alfa 95568576, Govind Enterprise 253633098, DK Bean Bags 35178044, Anuradha Oil Mill 87677035, Visionary Style 93557756). `GET /lookup/{glid}` = cheap role/name check (404 if not in dataset); the page then calls `/context?glid=` (builds the .md, ~2 s) and opens `/demo#<glid>`. `/demo` now loads USERS from `/users`, accepts ANY dataset GLID (`userFromLookup` adds a chip), shows only the current role's chips + "⌂ change user" link, and reacts to hashchange. Verified headless (bad GLID message, DK Bean Bags card → demo, uncurated Wicks N More 7444262 opens with its own chip).
- Still user-side: earphones for widget calls; one real mic call on `/demo` to confirm captions; listen to Chaitra
  on a full Hindi call (switch back to Ishita `01a0cf17-0b6e-…` + commit if it sounds off); git commit.

## Dataset findings (2026-10-08 night)

- `scripts/explore_seller.py [glid]` prints one seller's profile + latest rows from every file (works).
- Cross-channel coverage: only 5 sellers appear in all 9 files, 47 in 8, 116 in 7. Most have 2–4.
- **Demo seller = GLID 95568576, "Alfa Enterprises", New Delhi, Compact Flash Card / HP Pen Drive,
  proprietorship, GST verified, is_paid=-1 (free), do_not_call=0, no frustration.** Why: richest story:
  - 175 enquiries (latest 2 Oct 09:22, "HP Pen Drive 16gb" from Barmer, unread; 30 Sep SanDisk cards).
  - 88 thread replies (seller replies with templated "Hi <name>, Thanks for your Enquiry..." + WhatsApp number).
  - 85 buyer calls (latest 29 Sep not connected; 27 Sep connected 71 s).
  - 90 buyleads bought, ~daily until 1 Oct, 200 credits each.
  - 5 VANI bot calls Jun–Jul: 20 Jun not interested ("account for demo"), 9 Jul agreed meeting 1 Aug 3 PM
    Sector 18 (full 14-turn Hinglish transcript exists, bot persona "Payal"), 23 Jul **Meeting Fixed**
    (SanDisk pen drive enquiries, exec meeting next day 3 PM Delhi).
  - 134 WhatsApp chatbot rows: 25 Jul seller sent product list (HP/SanDisk/Samsung pen drives + memory
    cards) and photos; RM "Bharti Verma" joined chat and shared summary.
  - 5 executive calls 12–13 Aug (DSR module, one 466 s answered). 4 PNS call extractions (seller role,
    SanDisk 8GB Cruzer Blade quoted ₹210/piece on 8 Aug).
- Backup demo seller: GLID 209139024 "Shreeva Enterprises", Jaipur, Door Seals (all 9 files, 22 exec
  calls, 12 PNS extractions, WhatsApp buy-lead flow on 2 Sep, bot calls Aug "busy, call later").
- Data quirks: `read_status` 0 = unread, -3 = read (verify); `is_paid` -1/0; WhatsApp `user_message`
  often NaN (template pushes); `bot_call_turns` only for 420 sellers; buyleads only 16 Aug–1 Oct;
  profile `eng_*` may be NaN. Dates are strings `YYYY-MM-DD HH:MM:SS`, some with `.000`.
- Column/key map: enquiries `seller_glid`/`enquiry_date`; replies `seller_glid`/`reply_date`/`message_from`;
  buyer calls `seller_glid`/`call_datetime`; buyleads `seller_glid`/`purchase_date`/`keyword`;
  WA chatbot `glid`/`entry_date`; WA msgs `glid`/`entry_date`; bot calls `fk_glusr_usr_id`/`call_start_time`;
  turns `fk_glusr_usr_id`/`attempt_id`/`turn_no`; exec calls `fk_glusr_usr_id`/`call_start_time`/`status`;
  extractions `glid`/`call_date`/`seller_role_on_call`.

## Code built so far (2026-10-08 night) — all working

| File | What it does | Timing |
|---|---|---|
| `app/sources/seller.py` | `get_seller_events(glid, as_of=None) -> dict`. Reads the 11 CSVs (cached with lru_cache), applies lookback (30 d activity / 180 d conversations), returns profile, enquiries (+unread count), replies, buyer-call stats, buylead stats, WhatsApp turns, VANI calls + latest transcript (with its date), executive-call stats, PNS quotes, and `live_events` (from `context_files/<glid>/events.jsonl`). Only file that knows CSV columns → swap for real APIs here. | ~0.6 s |
| `app/builder/seller_md.py` | `build_seller_md(glid, as_of=None, use_llm=True) -> dict`. Facts rendered by code (`render_facts`), 4 insight fields by `sarvam-105b` (`llm_insight`: story, Hinglish opener, next_action, avoid) with rule-based fallback. Writes `context_files/<glid>/seller.md` (~33 lines, ~2.5 KB) + `events.json`. Returns timings for the freshness metric. | 1.7 s with LLM, 0.6 s without |
| `scripts/explore_seller.py [glid]` | prints a seller's raw history from every file | — |
| `app/sources/buyer.py` | `get_buyer_events(glid)`. Parses the Kibana CSV once (lru_cache; 237 usable GLIDs, 141 rows unusable: 68 NaN + truncated JSON), latest snapshot per GLID. Returns profile (name, company, city, customer_type, verifications, vintage), 30-day activity stream (ENQ / C2C=called seller / Browse / Search / BL), counts, top categories, sellers_contacted, last_enquiry, last_lead, active_buyleads, WhatsApp texts (parsed from CHAT_CONTENT), IndiaMART connect calls, tickets, live_events. `buyer_glids()` lists them. | 0.2 s (after first load ~1 s) |
| `app/builder/insight.py` | shared `llm_insight(slim, role, extra)` → story / opener / next_action / avoid via sarvam-105b (reasoning off) | ~1–1.5 s |
| `app/builder/buyer_md.py` | `build_buyer_md(glid)` → `context_files/<glid>/buyer.md` (~34 lines). Hint to LLM: WhatsApp "You just spoke with X" = buyer phoned seller X. | 1.7 s |
| `app/api.py` | FastAPI. `GET /context/{glid}` → flat JSON (`name`, `company`, `city`, `opener`, `next_action`, `avoid`, `story`, `unread_enquiries`, `context`=full seller.md, `updated_at`, `build_seconds`); `?rebuild=true` forces regeneration. `GET /context/{glid}/seller.md` raw file. `POST /events/{glid}` body `{channel, summary, time?, meta?}` → appends to `context_files/<glid>/events.jsonl`, rebuilds, returns `freshness_seconds` + new opener. `GET /health`. | cached GET 0 s; POST→fresh file **~1.8 s** |

**Sarvam User Identifier → GLID (2026-10-09 13:45):** `GET /context?uid=…` (`resolve_uid`): a GLID (web widget
`user-id`) or a caller number (inbound) → GLID; anonymous `user_<ts>` or unknown → falls back to `?glid=`
(agent default). on_start tool `load_user_memory` (id 4c1175ce-…, draft v3) now sends
`glid={{glid}}&uid={{user_identifier}}` and also saves `glid` back from the response.
Verified in a `send_chat` test: Sarvam called `GET /context?glid=93557756&uid=` — the variable name was
accepted but the value was EMPTY in the text-chat runtime (no identifier there). Still to verify with the
web widget (sets user-id) and a phone call (caller number). If it stays empty, candidates to try are
`user_id`, `caller_number`, `phone_number`, or ask Sarvam staff at the event.
**IMPORTANT: the web widget (and any deployment/campaign) runs the latest COMMITTED version, not the draft.**
Analytics (`analytics report interactions`, filter needs key `field` not `column`) showed every widget session
at 13:42–13:56 IST ran app_version 2 with glid=93557756 (v2's frozen default) regardless of the page's
user-id, because v2's on_start tool had no uid param. **v3 committed 14:05 IST** (uid param + glid save-back);
draft is now v4. After any tool/prompt change that must reach the widget: `agents commit`.
The user's widget test calls (speakers / 500 table chairs / helicopter / VIP darshan) polluted
`context_files/93557756/events.jsonl`; cleaned 14:06, backup in `/tmp/events_93557756_backup_*.jsonl`.
A teammate (vishal.1@indiamart.com) is in the workspace and ran a dashboard test at 14:10 IST with glid=1234
(unknown → API 404 → agent fell back to defaults "Rajesh / No memory loaded yet"). Expected behaviour; on
Day 1 maybe return a friendly "new user" memory instead of 404.
**v4 committed 14:20 IST:** prompt now has explicit seller-vs-buyer rules (Environment: what each role is and
what never to ask; Objective: role vocabulary "aapko enquiry aayi hai" vs "aapne enquiry bheji thi"; step 2
branches per role; step 3 = new requirement not in memory → note + ask quantity, never promise non-IndiaMART
products). Reason: user felt seller and buyer calls sounded the same; cause was widget sessions all running
seller 93557756 while the user role-played a buyer.
**v5 committed 14:35 IST (user request):** greeting is now "Hello {{user_name}} ji, how are you?" (English
source, auto-translated); VANI does NOT introduce itself unless asked ("kaun bol raha hai?" → "VANI from
IndiaMART" in one line). Step 1 treats any normal reply as identity confirmed. Note: this departs from the
Sarvam playbook (opening line should say who is calling) — the user chose it; revisit if judges dislike it.
**v6 committed 14:36 IST:** auto-translation produced "आप कैसी हैं?" (feminine); Hindi maps patched by hand to
"नमस्ते {{user_name}} जी, आप कैसे हैं?" in all three `multilingual_audio*` maps. Re-patch after any English
intro edit (editing the English regenerates the translations).
**v7 committed 14:40 IST (user request, no "ji" in greeting):** English "Hello {{user_name}}, how are you?",
Hindi maps patched to "नमस्ते {{user_name}}, आप कैसे हैं?". The prompt still addresses the user as
"{{user_name}} ji" mid-call (speaking style rule) — ask the user if that should go too.
**v8 committed 15:45 IST:** tools recreated on tunnel `occasional-advisor-combination-profit` —
`load_user_memory` id 9aac9410-…, `save_call_to_memory` id 4975fb77-…. Fallback defaults changed so a
failed memory fetch is obvious: `user_name` = "ji" (greeting becomes "Hello ji…"), `user_context` =
"MEMORY NOT LOADED…". If VANI ever says "Hello ji" → the on_start tool could not reach the API (tunnel
down / URL changed).
**BUG FOUND 2026-10-09 ~16:00 IST (not fixed yet): widget always loads seller 93557756.** Sarvam analytics
(`attempts` report) shows widget sessions with `user_id` = 87677035 / 274238067 / 95568576 (page's user-id DOES
reach Sarvam), but `agent_variables.glid` = 93557756 and memory = Visionary Style. Cause: the on_start query param
`uid` is bound to agent variable `user_identifier`, which Sarvam leaves EMPTY (API log: `GET /context?glid=93557756&uid=`),
so `/context` falls back to the frozen `glid` default 93557756. Fix options: (a) find the real system-variable name
for the User Identifier in the dashboard tool editor and rebind `uid`; (b) demo hack: page POSTs the selected GLID to
the API as "active GLID", API uses it when uid is empty; (c) newer embed SDK with agentVariables.
**Option (b) DONE 15:45 IST:** `POST /active {glid}` writes `context_files/_active.json`; `web/index.html` calls it on
every Load memory. `GET /context` uses the active GLID only when the `uid` param is present but unusable (= agent
call); page calls (no uid) and real uids are unaffected. No agent change needed. Verified by `send_chat` on v8:
active=274238067 → VANI opened with Aarti Singh's VP Precon bollard quote. Limit: one on-screen user at a time.
**v9 committed 16:25 IST (draft now v10): call card + history tool + language memory + personalised greeting.**
- `GET /context` now also returns `call_card` (~1.2 KB, built by rules in `app/builder/call_card.py`: who, story,
  2 newest live events, open items, warnings, next/avoid), `greeting` and `language`. The agent saves
  `call_card` → `user_context` (full .md stays in `context` for the web page / other uses).
- `GET /history?glid=&question=` (run tool `get_more_history`, id 5e5ab452-…, also listed in state `tool_names`;
  a run tool must be in `tool_names` before the prompt may say `tool:get_more_history`). sarvam-105b answers in
  1-2 spoken sentences in the user's language from the full .md + events.json (~0.6-0.8 s). resp_template
  `{{answer}}`. Prompt step 3: say a hold line, then call the tool in the same turn. Verified in send_chat:
  "थोड़ा समय दीजिए, मैं details check कर लेती हूँ। आप बस line पर बने रहिए।" → tool → answer spoken.
- Language memory: post-call variable `user_language` (enum of Sarvam language names + unknown) → on_end tool
  `save_call_to_memory` (id 512af0bd-…) posts `language` → `app/builder/prefs.py` writes
  `context_files/<glid>/prefs.json` and rebuilds (even when the summary is empty). on_start tool
  `load_user_memory` (id cf0895d9-…) saves `language` → `preferred_language`; prompt says reply in it.
  Initial platform language stays Hindi (workspace can't set it per call, no code hooks); LID switches if the
  user speaks another language. Not yet verified by a real voice call.
- Greeting: intro is now `{{greeting}}` in English + all multilingual maps. The insight LLM writes it in the saved
  language (Hindi = Devanagari with product names in English, neutral "आप कैसे हैं"), with the latest topic, no
  numbers. Default `greeting` = "Hello ji, how are you?" (= memory did not load).
**Stale-opener fix 16:35 IST (API only, no agent change):** Alfa 95568576's opener kept offering the old
"August meeting" (the LLM had no today's date, and earlier voice summaries repeated it). Now `prefs.date_rule()` tells
both insight prompts today's date and that past meetings/callbacks are never offered; the live-event rule has an
exception for past-dated items; `stale_month()` checks the opener for a month that is already over and retries
(max 3), then falls back to the rule-based opener. Seller opener prompt also now uses seller vocabulary
("aapko X ki enquiry aayi thi"); before it said "aapko Samsung memory cards chahiye" to the seller. Build time is
~1.3-2 s, up to ~4.6 s when a retry happens.
**Web widget:** package `sarvam-convai-embed@1.0.19` = `<sarvam-widget>` custom element, **voice only**
(interaction_type "call" hardcoded), attributes api-key / app-id / org-id / workspace-id / user-id / button-*
/ logo-url / position; no agent-variables (docs describe a newer SDK with `agentVariables`). It sends
`user_identifier = user-id`, so the page sets `user-id = GLID`. Needs an **embed-scoped API key** in
`web/config.js` (git-ignored; template `web/config.js.example`). Text chat is NOT available in this widget.
**Phone → GLID (inbound):** `GET /context?phone=+91XXXXXXXXXX` → `glid_from_phone()` reads
`data/phone_to_glid.json` (demo map, last-10-digit match; dataset has no numbers). Add the team's numbers there.
Day 1: replace with the IndiaMART user-lookup API. Unknown number → 404.
**Role detection:** `role_of(glid)` = seller if in `gc_seller_profile.csv`, else buyer if in the getContext export,
else 404. `GET /context` returns `role`, `name` (buyer person name / seller company), builds the right file.
`GET /context/{glid}/md` returns whichever file exists. `POST /events` rebuilds the right file too.
**Demo buyer = GLID 274238067 "Aarti Singh", Gharaunda** (new free user; 29 Sep enquiries + calls for Concrete
Bollards to 11 sellers, active buy-lead "Concrete Cylindrical Bollards", 30 Sep phoned 4 sellers, WhatsApp
seller replies). Backup buyer: 59681744 Ramesh, Global Print And Solution, Mumbai (paper bags / hand bells;
IndiaMART connect calls "not interested"). Buyer data has no phone numbers either.
**Demo web page (2026-10-09 13:00):** `web/index.html` served at `http://localhost:8000/` (StaticFiles mount, must
stay the last route). Sections: 1 who (GLID or phone, quick-pick of the 5 tested GLIDs) → 2 memory file
rendered + opener box → 3 "Chat with VANI" (injects `web/widget.html` = Sarvam embed snippet, user must paste it;
`web/widget.html.example` explains) + "Call me" (`POST /call` → Sarvam Instant Outbound; returns 503 until
`.env` has SARVAM_AGENT_API_KEY / SARVAM_CONNECTION_ID / SARVAM_AGENT_NUMBER, i.e. a Sarvam number exists)
→ 4 simulate an event on another channel (`POST /events/{glid}`, shows freshness seconds) → 5 events list
(`GET /events/{glid}`). Public via the tunnel too.
Run API: `uvicorn app.api:app --port 8000` (log in `/tmp/vani_api.log` when started by Claude).
**Live events** (`events.jsonl`) are rendered in a "## Latest across channels (live)" section right under
the story, and the LLM prompt forces the opener to continue from the newest live event. Verified: after
POSTing a WhatsApp event ("HP 16GB at ₹240, call back 11 AM") the opener became "Seller ne WhatsApp par
HP 16GB pen drive ka rate 240 rupees bataya tha, main Barmer buyer ko update karna chahti hoon."
To reset the demo: delete `context_files/95568576/events.jsonl` and call `/context/95568576?rebuild=true`.

**Simplified showroom demo page `/demo` (2026-10-09 17:00 IST, `web/demo.html`, route in `api.py`):** three panels, almost
no explanatory text, meant for the video / judges. Deep link `/demo#<glid>` (dev: `&scr=incoming|incall` shows a call screen).
- **Phone (left):** WhatsApp chat with "IndiaMART". Typing a message → `POST /whatsapp/{glid}` {text}: appends a
  whatsapp event, rebuilds the .md, then sarvam-105b writes a 1–2 line reply from the fresh call card (~2 s total;
  canned fallback). Reply shown as a bubble + "🧠 memory updated in Xs".
  **"☎ VANI calls <name>"** (top bar) → incoming-call screen with ringtone (WebAudio) → Accept → in-call screen (timer,
  waveform, live captions) that **drives the hidden Sarvam web widget**: the page mounts `<sarvam-widget>` with
  `visibility:hidden`, clicks its expand button then its "Start" button inside the open shadow root, and reads the
  state back from the shadow DOM text ("Connecting…" / "End Call"). End button clicks the widget's "End Call".
  Captions come from hooking `console.log("Transcript:", json)` which the widget emits (shape unverified; harmless if
  absent). Verified headless: collapsed=1 button, expanded → "Start" found. **Not yet verified with a real mic call.**
  After the call the page polls `/events/{glid}` every 3 s (2 min) for the on_end voice summary, then re-renders.
- **Desktop (middle):** browser frame. Buyer → indiamart.com with search + cards from `GET /site/{glid}` (top
  categories + recent keywords from the dataset). Seller → seller.indiamart.com Lead Manager with the real enquiries
  (unread flag, message). Actions post `web` events via `POST /events/{glid}`: search, open card/enquiry, Get Latest
  Price / Call Supplier, Reply / Call buyer. **Scroll capture:** IntersectionObserver; a card that comes into view
  after load for 0.9 s gets a "👁 seen" badge + toast; views are batched (3.5 s) into one event "Buyer browsed on
  indiamart.com: A, B". Posts are serialised (one rebuild at a time).
- **Memory (right):** `buyer.md`/`seller.md` rendered, "Latest across channels (live)" highlighted green, flash on
  change, badge shows "✔ whatsapp → buyer.md in 1.5s" then "updated N s ago". Top box = "VANI will open with"
  (greeting + opener). "reset" button → `DELETE /events/{glid}` (drops events.jsonl, rebuilds from dataset).
- Every user switch POSTs `/active` so a VANI call (widget/dashboard) loads that user. Background poll (6 s) picks
  up events from other channels. The old detailed page stays at `/` (`web/index.html`).
- New API routes: `GET /site/{glid}`, `POST /whatsapp/{glid}`, `DELETE /events/{glid}`, `GET /demo`.

Run: `python -m app.builder.seller_md 95568576` (add `--no-llm` for rules only).
Sample output for 95568576 is in `context_files/95568576/seller.md` (git-ignored, regenerate any time).
Known nit: the LLM "story" sometimes over-weights old "Not Interested" calls over the later "Meeting Fixed";
prompt could tell it to weight the most recent VANI outcome. Opener lacks the "ji" address sometimes.

## Repo state (as of 2026-10-10 12:45 IST)

```
vani-context/                     branch Ankul-main (main is fast-forwarded to it); remote github.com/Ankulraja/vani-context (PUBLIC, see risk 1)
├── .env                          SARVAM_API_KEY (+ optional NGROK_DOMAIN, SARVAM_APP_ID, SARVAM_APP_ID_SELLER)  git-ignored
├── .gitignore                    .env .venv/ __pycache__/ context_files/ Dataset/ web/config.js .DS_Store web/widget.html
├── .mcp.json                     Sarvam Voice Agents MCP (OAuth daily via /mcp)
├── app/api.py                    FastAPI: /, /demo, /users, /lookup/{glid}, /context (+/{glid}, /md), /history, /events (+/{glid}, DELETE),
│                                 /active (+DELETE /active/call), /whatsapp/{glid} (GET/POST), /whatsapp/send, /webhook/sarvam,
│                                 /search, /home-feed, /site/{glid}, /call, /health, /debug/422
├── app/sources/seller.py buyer.py   dataset → events dict (only files that know the raw layout; swap for real APIs here)
├── app/sources/im_search.py im_home.py   live indiamart.com search (mobile page JSON) and home feed (trending + industries)
├── app/builder/seller_md.py buyer_md.py insight.py call_card.py prefs.py   facts by code + sarvam-105b insight → .md, call card, language prefs
├── web/start.html demo.html index.html   start page, three-screen demo, old detailed page; config.js(.example), widget.html.example
├── web/im-logo.png im-wordmark.png wa-bg.png ringback.ogg
├── extension/                    Chrome MV3 extension for the "Live indiamart.com" mode
├── scripts/explore_seller.py test_sarvam.py tunnel.sh
├── data/phone_to_glid.json       demo caller-number → GLID map
├── docs/seller_call_insights.md  dataset analysis (10 Oct)
├── context_files/                generated memory (git-ignored): <glid>/{buyer|seller}.md, events.json, events.jsonl, prefs.json,
│                                 whatsapp_thread.json; _active.json; _backups/
├── Dataset/                      organiser data (git-ignored, never commit)
├── README.md skills.md CLAUDE.md
└── .venv/                        Python 3.13: sarvamai, fastapi, uvicorn, pandas, httpx, playwright (tests)
```
Run: `source .venv/bin/activate; uvicorn app.api:app --port 8000 --reload` + `cloudflared tunnel --url http://localhost:8000`.
Headless checks: Playwright scripts in `/tmp/vani_tests/` (recreate as needed) or
`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --screenshot=… "http://localhost:8000/demo#<glid>&scr=incall&state=oncall"`.

## Next steps (Day 2, in order)

1. User: make the GitHub repo private, then say "purge it" → history rewrite + force-push; rotate the Sarvam embed key.
2. Commit + push the current work (start page, two agents, insights doc).
3. skills.md: add the Day-2 entries (two agents, Tanya, call flows, WhatsApp-from-call, start page, dataset analysis, data-leak lesson).
4. Demo rehearsal with earphones: buyer flow (Aarti: search → Get Latest Price → Tanya calls → ask for supplier details on
   WhatsApp) and seller flow (Alfa: Call Tanya → unread enquiry; Visionary Style: "phir se call?" → no pitch). Record the 5–7 min video.
5. Optional if time: seller triggers (Call buyer in Lead Manager → call about that enquiry; new unread enquiry → Tanya calls),
   a "lift" number (cold vs personalised opening), approach note, static ngrok domain.

## Conventions

- Commit messages: short imperative subject. Do not commit `.env`, `.venv/`, `context_files/`.
- Keep `skills.md` updated as a dated log — it is 15% of the score.
- When a Sarvam call fails, paste the error; SDK field names may differ from docs.
