# CLAUDE.md — VANI Context (Voice AI Hackathon 2.0)

This file is the handoff for any LLM session working in this repo. Read it first; it replaces
re-reading the hackathon PDF and the earlier chat. Keep it updated when the plan or state changes.

## How to work with the user

- The user is new to Python, AI/LLMs and voice bots. Explain in **simple, short English**. Avoid
  jargon; when a term is needed, define it in one line.
- **Since 2026-10-08 night: Claude does the work itself** (writes files, runs scripts, configures
  the agent via MCP). Tell the user in short Hinglish what was done and what was found. Do not hand
  them step lists any more unless something is only possible on their side (login, mic test, commit).
- **Always update CLAUDE.md** after each piece of work (state, findings, next step).
- Prefer tables and short bullet lists over long paragraphs.
- The user's day job is Next.js frontend (IndiaMART ads PDP). JS/Next.js is familiar; Python is not.
- Never print or commit the Sarvam API key. It lives in `.env` (git-ignored).
- The user is **Ankul Patel**, email `ankul.patel@indiamart.com`. The Claude Code login may show a
  different IndiaMART email; ignore it. Sarvam account / MCP login / Org ID = Ankul's email.
- Since 2026-10-08 the user wants replies in **Hinglish** (Hindi words, Roman script, simple).
  Code, file names and commands stay in English.

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

## Sarvam agent + MCP state (2026-10-08, evening — MCP WORKING)

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

Run: `python -m app.builder.seller_md 95568576` (add `--no-llm` for rules only).
Sample output for 95568576 is in `context_files/95568576/seller.md` (git-ignored, regenerate any time).
Known nit: the LLM "story" sometimes over-weights old "Not Interested" calls over the later "Meeting Fixed";
prompt could tell it to weight the most recent VANI outcome. Opener lacks the "ji" address sometimes.

## Repo state (as of 2026-10-08)

```
vani-context/
├── .env                 SARVAM_API_KEY=...   (git-ignored, never commit)
├── .gitignore           .env  .venv/  __pycache__/  context_files/  Dataset
├── .mcp.json            Sarvam Voice Agents MCP server (commit this)
├── .venv/               Python 3.13.5; sarvamai 0.1.35, python-dotenv, fastapi, uvicorn,
│                        pydantic, streamlit, pypdf
├── requirements.txt
├── app/{sources,builder,bot}/__init__.py     empty packages
├── data/sample/         empty (no mock data — use Dataset/ instead)
├── context_files/       empty — generated .md output
├── Dataset/             organiser data (git-ignored), see "The dataset" section
├── scripts/test_sarvam.py                     LLM smoke test (works)
├── pss-runner/          UNRELATED Node page-speed tool with its own .git — untracked; user to move out
├── README.md, skills.md                       empty
└── CLAUDE.md            this file
```
Git: 2 commits on `main` ("first commit", "add project structure"). Uncommitted: `.gitignore`,
`scripts/test_sarvam.py`, `CLAUDE.md`, `.mcp.json`. Run `source .venv/bin/activate` first.
Hackathon deck PDF: `~/Desktop/Voice_AI_Hackathon_2.0_Deck_Revised - Final.pptx.pdf` (read with pypdf).

## Next steps (in order)

2026-10-09 14:40 IST: user asked to stop the server + tunnel; both killed. User runs them himself now.
Background processes Claude started on 2026-10-08 (may be dead after a reboot): `uvicorn app.api:app --port 8000`
(log `/tmp/vani_api.log`) and `cloudflared tunnel --url http://localhost:8000` (log `/tmp/cloudflared.log`,
URL in `/tmp/vani_public_url.txt`). Restart both, then re-point the two agent tools at the new URL.

**Rule check before Day 1:** the deck says "all build work happens during the 2 days; setup/learning beforehand
is fine". Tonight's code is a learning prototype on stand-in data. Plan: on Day 1 rebuild `app/sources/` on the
real starter APIs, re-create the agent tools, and log all of it in `skills.md` so the journey is honest.

1. User: add Day-0 lines to `skills.md`; move `pss-runner/` out; press "Test agent" in the dashboard (draft v2)
   to hear the memory opener by voice; send Org ID to organisers.
2. (done 2026-10-09 00:00) Buyer side: source + builder + role-aware API, tested end to end with the agent.
3. Agent polish via MCP: voicemail message (`configure_voicemail`), call goal / evaluation criteria, then
   `agents commit` → v2. Intro line may address the company name ("Alfa Enterprises ji") — fine for sellers.
4. Phone test: `verify_phone_number` (OTP to the user's phone) → `place_test_call(app_variables={"glid": "95568576"})`
   with `webhook_config.url=<TUNNEL>/webhook/sarvam` where supported; confirm the webhook arrives.
5. Web widget / chat channel: Deploy with Code → Embed (dashboard). Demo flow: chat on widget → event →
   phone call resumes (or reverse). Record the 5–7 min video.
6. Freshness dashboard: tiny Streamlit page showing seller.md, events.jsonl and `freshness_seconds` per event.
7. README (architecture, sources, lookback 30 d/180 d, refresh logic), `skills.md` build journey, approach note.

## Conventions

- Commit messages: short imperative subject. Do not commit `.env`, `.venv/`, `context_files/`.
- Keep `skills.md` updated as a dated log — it is 15% of the score.
- When a Sarvam call fails, paste the error; SDK field names may differ from docs.
