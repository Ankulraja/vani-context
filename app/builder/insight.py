"""Shared LLM step: events dict -> 4 short insight fields (story, opener, next_action, avoid).

Used by seller_md.py and buyer_md.py. Always pass reasoning_effort=None to sarvam-105b, otherwise
the model spends every token "thinking" and returns empty content.
"""
from __future__ import annotations

import json
import os
import re
import time

from dotenv import load_dotenv

from app.builder.prefs import date_rule, stale_feedback, stale_month
from app.sources.seller import ROOT

load_dotenv(ROOT / ".env")
LLM_MODEL = "sarvam-105b"

PROMPT = """You write the memory file an IndiaMART voice bot (VANI) reads before talking to a {role}.
Below is the {role}'s recent activity as JSON. Write ONLY a JSON object with these keys:
- "story": 2 sentences, English, third person ("the {role}"), what this {role} has been doing and what matters right now. No fluff.
- "opener": the first line VANI should say on the NEXT conversation, after the {role} confirms their name.
  Hinglish in Roman script, under 25 words. It refers to the single most recent concrete thing (an enquiry,
  a call with a seller, a buy-lead, a quote, a callback that was promised) in PAST tense ("aapne bola tha",
  "aapne enquiry bheji thi") and then asks one short question to continue. Never say the agent is doing
  something "right now".
- "next_action": one line, English, the most useful thing VANI can help with on this call.
- "avoid": one line, English, what VANI must not do or repeat, based on past interactions.
{greeting_rule}
Rules:
- "live_events_newest_first" are the NEWEST things that happened, on other channels (voice call, WhatsApp,
  chat, app), after the rest of the data. The FIRST item is the newest. If the list is non-empty, the opener
  MUST continue from that first item (what the {role} said or agreed there), and the story must mention it.
  EXCEPTION: if that item is only about a date that is already past (an old meeting or callback, see the
  date rule below), do not build the opener on it; use the freshest open item instead.
  This is how VANI resumes a conversation across channels.
- Judge mood from the MOST RECENT outcome, not older ones.
- The opener must never contradict "avoid": if the user declined help, a pitch, a meeting or more calls, the
  opener acknowledges that and asks only about something new and useful to THEM (e.g. a fresh enquiry),
  or simply asks if there is anything they need. Never re-offer what was declined. Example for a user who
  said they need no more help: "Aapne bola tha abhi koi help nahi chahiye. Bas confirm karna tha, sab theek
  chal raha hai na?" (no offer of listing, profile, catalog, meeting or executive help in that case).
- Facts must come from the JSON only. Do not invent names, dates or numbers.
{extra}
{date_rule}
{role_upper} JSON:
"""


def llm_insight(slim: dict, role: str, extra: str = "", greeting_rule: str = "") -> tuple[dict, float, str]:
    """Returns (insight, seconds, source) where source is 'llm' or 'error:<msg>'."""
    t0 = time.perf_counter()
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        prompt = PROMPT.format(role=role, role_upper=role.upper(), extra=extra, greeting_rule=greeting_rule, date_rule=date_rule()) + json.dumps(slim, ensure_ascii=False)
        for attempt in range(3):  # retry only if the opener brings up a month that is already over
            r = client.chat.completions(model=LLM_MODEL, temperature=0.2, reasoning_effort=None, max_tokens=800,
                                        messages=[{"role": "user", "content": prompt}])
            text = r.choices[0].message.content or ""
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
            data = json.loads(text[text.find("{"): text.rfind("}") + 1])
            month = stale_month(data.get("opener", ""))
            if not month:
                break
            prompt += stale_feedback(month)
        if stale_month(data.get("opener", "")):
            data["opener"] = ""  # still stale: the caller fills a rule-based opener
        for k in ("story", "opener", "next_action", "avoid"):
            data.setdefault(k, "")
        return data, time.perf_counter() - t0, "llm"
    except Exception as e:  # noqa: BLE001
        return {}, time.perf_counter() - t0, f"error:{str(e)[:80]}"
