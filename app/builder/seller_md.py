"""Builder: seller events dict -> compact seller.md

Two layers, by design:
  1. FACTS   — rendered by code from the events dict. Instant, exact numbers, never hallucinated.
  2. INSIGHT — 4 short fields written by the Sarvam LLM (story so far, Hinglish opener,
               next best action, what to avoid). If the LLM fails we fall back to a rule-based opener,
               so the file is always produced.

Output: context_files/<glid>/seller.md  (kept under ~40 lines)
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from app.sources.seller import ROOT, get_seller_events

load_dotenv(ROOT / ".env")
OUT_DIR = ROOT / "context_files"
LLM_MODEL = "sarvam-105b"


# ---------------------------------------------------------------- helpers
def _day(d: str | None) -> str:
    """'2026-10-02 09:22' -> '2 Oct 09:22'"""
    if not d:
        return "-"
    dt = datetime.strptime(d, "%Y-%m-%d %H:%M")
    return f"{dt.day} {dt.strftime('%b')} {dt.strftime('%H:%M')}"


def _yn(b: bool) -> str:
    return "yes" if b else "no"


# ---------------------------------------------------------------- facts (code)
def render_facts(ev: dict) -> dict[str, str]:
    p = ev["profile"]
    who = [
        f"- {p['company']}, {p['city']} ({p['state']}), {p['business_type'] or 'business'} · "
        f"{'Paid' if p['paid'] else 'Free'} seller · GST {_yn(p['gst_verified'])}, mobile {_yn(p['mobile_verified'])}, email {_yn(p['email_verified'])}",
        f"- Sells: {', '.join(p['categories']) or '-'} · {p['product_count']} products · catalog score {p['catalog_quality_score'] or '-'}",
    ]

    last = ev["enquiries"][0] if ev["enquiries"] else None
    recent = [
        f"- Enquiries: {ev['enquiries_30d']} received, **{ev['unread_enquiries']} unread** · seller replied {ev['seller_replies_30d']}×"
        + (f" · latest {_day(last['date'])}: {last['product']} from {last['buyer_company'] or 'a buyer'}, {last['buyer_city']}"
           f"{' (unread)' if last['unread'] else ''}" if last else ""),
    ]
    bc = ev["buyer_calls"]
    recent.append(f"- Buyer calls: {bc['total']} ({bc['connected']} connected, {bc['missed']} missed)"
                  + (f" · last {_day(bc['last'])} {bc['last_status'].lower()}" if bc["last"] else ""))
    bl = ev["buyleads"]
    recent.append(f"- Buyleads bought: {bl['count']} ({bl['credits']:,} credits)"
                  + (f" · last {_day(bl['last'])}" if bl["last"] else "")
                  + (f" · keywords: {', '.join(dict.fromkeys(k.lower() for k in bl['keywords']))}" if bl["keywords"] else ""))
    recent.append(f"- WhatsApp: {ev['whatsapp_30d']} messages in 30 days")

    conv = []
    for c in ev["vani_calls"][:4]:
        conv.append(f"- VANI {_day(c['date'])[:-6]}: {c['disposition']}"
                    + (" ✅" if c["meeting_fixed"] else "") + f" — {c['summary'][:140]}")
    ex = ev["executive_calls"]
    if ex["total"]:
        conv.append(f"- Executive calls: {ex['total']} ({ex['answered']} answered) · last {_day(ex['last'])}"
                    + (f", {ex['last_duration_sec'] // 60} min" if ex["last_duration_sec"] else ""))
    typed = [w for w in ev["whatsapp"] if w["seller_said"]]
    if typed:
        w = typed[0]
        conv.append(f"- WhatsApp {_day(w['date'])[:-6]}: seller wrote “{w['seller_said'][:90]}”")
    quoted = [q for q in ev["pns_calls"] if q["prices"]]
    if quoted:
        q = quoted[0]
        conv.append(f"- Phone quote {_day(q['date'])[:-6]}: {q['products']} at {q['prices']}")
    if not conv:
        conv.append("- No IndiaMART conversations in the last 180 days")

    flags = [
        f"- Do-not-call: {_yn(p['do_not_call'])} · frustration: {_yn(p['showed_frustration'])} · asked if bot: {_yn(p['asked_if_bot'])}"
        f" · already with executive: {_yn(p['already_with_executive'])}",
        f"- VANI history: {p['bot_answered']}/{p['bot_attempts']} calls answered, {p['meetings_fixed']} meeting fixed"
        + (f" · objections: {p['past_objections']}" if p["past_objections"] else ""),
    ]
    live = [f"- 🔄 {e.get('time', '')} via **{e.get('channel', 'event')}**: {e.get('summary', '')[:160]}"
            for e in reversed(ev["live_events"][-3:])]

    return {"who": "\n".join(who), "recent": "\n".join(recent), "conv": "\n".join(conv),
            "flags": "\n".join(flags), "live": "\n".join(live)}


# ---------------------------------------------------------------- insight (LLM)
INSIGHT_PROMPT = """You write the memory file an IndiaMART voice bot (VANI) reads before calling a seller.
Below is the seller's recent activity as JSON. Write ONLY a JSON object with these keys:
- "story": 2 sentences, English, what this seller has been doing and what matters right now. No fluff.
- "opener": the first line VANI should say after the seller confirms their name. Hinglish in Roman script,
  under 25 words, mentions the single most recent concrete thing (an unread enquiry, a fixed meeting, a quote).
- "next_action": one line, English, the most useful thing VANI can help with on this call.
- "avoid": one line, English, what VANI must not do or repeat, based on past calls (e.g. objections, hang-ups).
Rules:
- "live_events" are the NEWEST things that happened, on other channels (voice call, WhatsApp, chat, app),
  after the rest of the data. If the list is non-empty, the opener MUST continue from the newest live event
  (what the seller said or asked there), and the story must mention it. This is how VANI resumes a conversation.
- Judge the seller's mood from the MOST RECENT VANI call outcome, not older ones (a later "Meeting Fixed"
  outweighs earlier "Not Interested").
- Facts must come from the JSON only. Do not invent names, dates or numbers.

SELLER JSON:
"""


def llm_insight(ev: dict) -> tuple[dict, float, str]:
    """Returns (insight dict, seconds, source) where source is 'llm' or 'fallback'."""
    slim = {"live_events": ev["live_events"][-3:]}
    slim.update({k: v for k, v in ev.items() if k not in ("replies", "live_events")})
    slim["enquiries"] = ev["enquiries"][:6]
    slim["vani_latest_transcript"] = ev["vani_latest_transcript"][:8]
    t0 = time.perf_counter()
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(
            model=LLM_MODEL,
            temperature=0.2,
            reasoning_effort=None,  # MUST be explicit: default "thinking" eats all tokens and returns empty content
            max_tokens=800,
            messages=[{"role": "user", "content": INSIGHT_PROMPT + json.dumps(slim, ensure_ascii=False)}],
        )
        text = r.choices[0].message.content
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        for k in ("story", "opener", "next_action", "avoid"):
            data.setdefault(k, "")
        return data, time.perf_counter() - t0, "llm"
    except Exception as e:  # noqa: BLE001 — any failure -> deterministic fallback
        return _fallback_insight(ev, str(e)), time.perf_counter() - t0, "fallback"


def _fallback_insight(ev: dict, err: str) -> dict:
    p = ev["profile"]
    last = ev["enquiries"][0] if ev["enquiries"] else None
    opener = (f"{p['company']} ji, aapke paas {ev['unread_enquiries']} nayi enquiries unread hain"
              + (f", latest {last['product']} ke liye {last['buyer_city']} se" if last else "") + ". Dekhein kya?")
    return {
        "story": f"{p['company']} received {ev['enquiries_30d']} enquiries in 30 days with {ev['unread_enquiries']} unread.",
        "opener": opener,
        "next_action": "Read out the unread enquiries and help the seller reply.",
        "avoid": "Do not repeat the paid-services pitch if the seller declined before.",
        "_note": f"LLM unavailable: {err[:80]}",
    }


# ---------------------------------------------------------------- assemble
def render_md(ev: dict, insight: dict, insight_src: str) -> str:
    f = render_facts(ev)
    p = ev["profile"]
    w = ev["window"]
    return f"""# Seller memory — {p['company']} (GLID {ev['glid']})
_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST · data as of {ev['as_of']} · window {w['activity_days']}d activity / {w['conversation_days']}d conversations · insight: {insight_src}_

## Who
{f['who']}

## Story so far
{insight['story']}
{("\n## Latest across channels (live)\n" + f["live"] + "\n") if f["live"] else ""}
## Last {w['activity_days']} days
{f['recent']}

## Conversations with IndiaMART (last {w['conversation_days']} days)
{f['conv']}

## Flags
{f['flags']}

## For the next conversation
- **Opener (Hinglish):** {insight['opener']}
- **Next best action:** {insight['next_action']}
- **Avoid:** {insight['avoid']}
"""


def build_seller_md(glid: int, as_of: datetime | None = None, use_llm: bool = True) -> dict:
    t0 = time.perf_counter()
    ev = get_seller_events(glid, as_of)
    t_src = time.perf_counter() - t0
    if use_llm:
        insight, t_llm, src = llm_insight(ev)
    else:
        insight, t_llm, src = _fallback_insight(ev, "disabled"), 0.0, "rules"
    md = render_md(ev, insight, src)
    out = OUT_DIR / str(glid)
    out.mkdir(parents=True, exist_ok=True)
    (out / "seller.md").write_text(md)
    (out / "events.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False))
    return {"path": str(out / "seller.md"), "lines": md.count("\n"), "chars": len(md),
            "seconds_source": round(t_src, 2), "seconds_llm": round(t_llm, 2),
            "seconds_total": round(time.perf_counter() - t0, 2), "insight_source": src, "md": md}


if __name__ == "__main__":
    import sys
    g = int(sys.argv[1]) if len(sys.argv) > 1 else 95568576
    r = build_seller_md(g, use_llm="--no-llm" not in sys.argv)
    print(r["md"])
    print({k: v for k, v in r.items() if k != "md"})
