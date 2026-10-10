# skills.md — build journey (Voice AI Hackathon 2.0, Problem 2: Memory Across Channels)

Dated log of what was learnt and built, and the tools used. Setup and learning before Day 1 is allowed by the
rules; the dataset-based prototype below is that learning phase and will be rebuilt on the real starter APIs on Day 1.

## Tools used

| Tool | For |
|---|---|
| Sarvam Voice Agents (Samvaad) | the hosted voice bot: STT Saaras v4, LLM sarvam-105b-conversations, TTS Bulbul; on_start / run / on_end API tools |
| Sarvam chat completions `sarvam-105b` | writing the memory file's insight fields, the mid-call history answers, the WhatsApp replies (free) |
| Sarvam Voice Agents MCP server (`mcp.sarvam.ai/voice-agents`) | configuring, testing (`send_chat`), committing and reading analytics of the agent from Claude Code |
| Claude Code | pair-programming: exploring the dataset with pandas, writing the FastAPI backend, builders and demo pages |
| Python 3.13, pandas, FastAPI, uvicorn | data sources, context builder, API |
| cloudflared / ngrok | public URL so Sarvam can call the local API |
| Sarvam web widget `sarvam-convai-embed` | voice calls from the demo page |
| Chrome extension (Manifest V3) | shows the real indiamart.com inside the demo and captures searches, product opens and clicks as events |
| Playwright Chromium | headless test of the extension and the demo page |
| Sarvam analytics (via MCP) | reading real call sessions: response time, which user id and agent version each call used |

## Log

- **2026-10-06** Read the hackathon deck. Picked Problem 2. Installed the Sarvam SDK; first `sarvam-105b` call worked.
- **2026-10-08** Learnt: `sarvam-105b` has thinking on by default and returns empty content for our prompts unless
  `reasoning_effort=None` is passed. Read the Voice Agents docs: the hosted agent brings its own LLM, so our product is
  the **context layer around the agent** (on_start tool loads memory, on_end tool writes the call back).
  Explored the organiser dataset (11 seller CSVs, 1 buyer getContext export). Built `app/sources/seller.py` and
  `app/builder/seller_md.py` (facts by code, insight by LLM, rule-based fallback). First `seller.md` in 1.7 s.
  Created agent "VANI IndiaMART" via MCP, committed v1 (memory via variables), then v2 (memory via API tools).
  First end-to-end voice test: VANI opened with a WhatsApp event posted a minute earlier.
- **2026-10-09** Buyer side (`buyer.py`, `buyer_md.py`), role-aware API, seller-vs-buyer prompt rules (v4), casual
  greeting (v5–v7), call card instead of the full file (v9: ~1.2 KB to the agent, full file stays for other uses),
  `get_more_history` run tool with a spoken hold line, language memory (greeting in the language spoken last),
  stale-opener guard (no past meetings offered), demo page `/demo` (phone + desktop + live memory file), Sarvam
  web widget driven from a fake incoming-call screen.
  Learnt the hard way: the dashboard tests the **draft**, the widget runs the latest **committed** version; the
  widget's user-id does not reach the on_start tool (worked around with an "active GLID"); a 5-second inactivity
  nudge interrupts people who are thinking (now 12 s); test calls where nobody spoke were polluting the memory
  (now skipped using the agent's `call_outcome`). Agent at v10.
- **2026-10-09 (evening)** Agent v10 → v14. What changed and what was learnt:
  - **Voice tuning (v10):** switched the voice to "Chaitra - Conversational Voice", faster voice-activity detection,
    pace 1.15. Learnt that a change made in the dashboard is only a draft; the widget on our page kept using the old
    voice until the agent was committed. Rule written down: dashboard change → commit → then test on localhost.
  - **Cleaner memory of calls:** the on_end tool now also sends `call_outcome` and `callback_time`. The memory file
    shows one "Recent VANI calls" line (outcome only, newest first) so repeated test calls never bury real activity.
    Calls with outcome `no_conversation` / `wrong_person` are not saved at all.
  - **Greeting guard in code:** the LLM sometimes wrote "आरती ji, आप कैसी हैं" despite the prompt; `prefs.clean_greeting()`
    now fixes the gender form and strips "ji" after the name. Lesson: put hard rules in code, not only in the prompt.
  - **Demo page rebuilt as three screens** (`/demo`): WhatsApp phone on the left, a browser with indiamart.com in the
    middle, a separate call phone on the right (incoming call → in-call captions → "Saved" screen). The memory file
    moved to a slide-out drawer with a freshness badge. Restyled to the team's design language (warm canvas, white
    cards, black pill buttons). WhatsApp panel uses WhatsApp's own wallpaper and the IndiaMART logo as the DP.
  - **Real indiamart.com in the demo:** the site blocks iframes (`x-frame-options: sameorigin`). Built a small Chrome
    extension that removes that header for the frame and injects a capture script on every `*.indiamart.com` page.
    It sends searches, product-page opens (title, supplier, price), Get Latest Price / Contact Supplier / Reply clicks
    and 1-second card views to `POST /events/{glid}`. Tested with Playwright, then by hand: a real search for
    "Diesel Engine Pump Sets" on indiamart.com changed VANI's next greeting within 2 s. Fixes found during the test:
    duplicate web events within 10 min are skipped; a form field holding a hostname was being logged as a search;
    the greeting now names the newest live event instead of the old dataset topic.
  - **Static tunnel option:** installed ngrok; `scripts/tunnel.sh` uses a static ngrok domain when `NGROK_DOMAIN` is set,
    else a cloudflared quick tunnel. The quick tunnel died once more during the evening (VANI then said "no recent
    activity" = memory not loaded); re-pointed the three tools in place with `configure_app_tool` and committed v12.
  - **WhatsApp bot rewrite (v12 era):** the emulated WhatsApp assistant now keeps a thread per user
    (`whatsapp_thread.json`). The prompt puts the recent chat first and the memory card only as background, and only
    the full card when the message touches memory (enquiry, rate, buyer, a product named in the card). Rules: answer
    the last message, ask one next question, give concrete timelines, never say "VANI will call you". Lesson:
    sarvam-105b sometimes thinks aloud before the answer, so only the last paragraph is kept.
  - **Mid-call refresh (v13, v14):** the memory is loaded once at call start (platform limit), so the prompt now tells
    VANI to call `get_more_history` when the user says "maine abhi WhatsApp pe bheja". `/history` prepends the live
    events of the last minutes and the WhatsApp thread. Verified in a text test: a WhatsApp message sent mid-chat was
    read back by VANI about 1 s later ("आपका budget दो हज़ार पाँच सौ रुपये per chair है...").
  - **Test memories reset** for the demo users (backups kept under `context_files/_backups/`).
  - **Real search inside the emulated website (10 Oct 00:05):** the user wanted the look-alike IndiaMART page to search the
    real site. Dead ends first: the desktop search API rejects outside IPs, and the desktop page shows zero results
    even in a real headed Chrome driven by Playwright. The mobile site is server-rendered and embeds the results as JSON,
    so `app/sources/im_search.py` fetches it with a phone user agent and parses that blob (0.2 s, cached). Cards now show
    the real product, price, supplier, city, rating and image, and clicks post events that name them, so VANI can say
    "aapne Techsol se Card Pen Drive ka rate pucha tha". Lesson: when a site blocks you, check its mobile version.
  - Still open for Day 2: a measured "lift" of the personalised opening vs. a cold greeting, the app channel in the
    demo, one real mic call on `/demo` to confirm captions, swap the dataset loaders for the Day-1 starter APIs,
    the 5–7 minute video.

## 2026-10-10 13:40 IST — Tanya becomes real IndiaMART customer care (facts + guardrails)

- Researched IndiaMART from public sources (help.indiamart.com, corporate.indiamart.com): what the platform is and is not
  (matchmaking, not a party to the deal), helpline and hours, BuyLead vs direct enquiry, Lead Manager, badges (Verified /
  TrustSEAL / Star / Leading), paid plans and weekly BuyLead quotas, Pay with IndiaMART discontinued (31 Mar 2024), the Buyer
  Payment Protection Plan (12 Feb 2026) conditions, safe-deal and fraud-reporting advice.
- Cross-checked with the organiser dataset: WhatsApp chatbot intents (catalog/photo help, 89 % seller-as-buyer), bot-call
  dispositions and summaries (old bot pitched meetings; 42 % not interested), seller profile flags (do-not-call, frustration,
  executive already in touch, is_paid 5 %), executive-call modules.
- Added to BOTH agent prompts: "IndiaMART facts the agent may state" (plan prices deliberately excluded because IndiaMART's own
  pages disagree) and a prioritised 9/10-rule guardrail set (identity, scope, truth, promises/no selling, money+OTP, privacy,
  disputes/complaints, respect, must-avoid). Buyer committed v23, seller v3.
- Verified by text chat: off-topic question -> IndiaMART-only redirect; "TrustSEAL price / Pay with IndiaMART" -> no price,
  sales callback, service closed; "paid 50k to personal UPI + shared OTP, refund?" -> never pay personal UPI / share OTP,
  complaint registered, helpline, police, no protection for direct payment; "paid plan, no orders, refund" -> one apology,
  complaint noted, helpline, help with enquiries, no refund promise.
- Tooling lesson: the Sarvam MCP `agents get include=[...]` returned only the summary from this client, so the live prompts
  were recovered from Claude Code session transcripts; copies now live in `docs/agent_prompt_*.md`.
- Also today: Sarvam embed key moved from `web/config.js` into `.env` (`GET /config.js` is now an API route); start-page
  dropdown and the top-bar "updated N s ago" badge removed on request.
