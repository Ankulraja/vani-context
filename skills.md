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
