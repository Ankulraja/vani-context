"""Builder: buyer events dict -> compact buyer.md  (same two-layer design as seller_md.py)

Output: context_files/<glid>/buyer.md
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from app.builder.insight import llm_insight
from app.builder.prefs import clean_greeting, fallback_greeting, get_language, greeting_rule
from app.builder.seller_md import OUT_DIR, _day, _yn, recent_calls_line
from app.sources.buyer import get_buyer_events


def render_facts(ev: dict) -> dict[str, str]:
    p = ev["profile"]
    who_name = p["name"] or f"GLID {ev['glid']}"
    who = [
        f"- {who_name}" + (f", {p['company']}" if p["company"] else "") + f", {p['city'] or '-'} · {p['customer_type']} buyer"
        + (f" · on IndiaMART {p['registered_since']}" if p["registered_since"] and not p["registered_since"].startswith("0 Y 0 M") else " · new user")
        + f" · mobile {_yn(p['mobile_verified'])}, email {_yn(p['email_verified'])}, GST {_yn(p['gst_verified'])}",
    ]
    if ev["top_categories"]:
        who.append("- Looking for: " + ", ".join(f"{c['category']} ({c['events']})" for c in ev["top_categories"]))

    ac = ev["activity_counts"]
    recent = [
        "- Activity: " + (", ".join(f"{n} {what}" for what, n in sorted(ac.items(), key=lambda x: -x[1]) if what != "other") or "none")
        + f" · {ev['sellers_contacted']} sellers contacted",
    ]
    for e in ev["recent_activity"][:6]:
        bits = [b for b in (e["keyword"] or e["category"], f"seller {e['seller_glid']}" if e["seller_glid"] and e["type"] in ("ENQ", "C2C") else None) if b]
        recent.append(f"- {_day(e['date'])}: {e['what']} — {' · '.join(bits) or '-'}")
    if ev["active_buyleads"]:
        recent.append("- Active buy-lead: " + "; ".join(ev["active_buyleads"][:3]))
    elif ev["last_lead"]:
        recent.append(f"- Last buy-lead: {ev['last_lead']['title']} ({ev['last_lead']['date']})")
    if ev["last_enquiry"]:
        recent.append(f"- Last enquiry: {ev['last_enquiry']['title'][:80]}")

    conv = []
    for w in ev["whatsapp"][:4]:
        conv.append(f"- WhatsApp {w['date'][5:]} ({w['from']}): {w['text'][:110]}")
    for cl in ev["indiamart_calls"][:3]:
        conv.append(f"- IndiaMART call {cl['date'][5:]}: {cl['status']}" + (f" — {cl['summary']}" if cl["summary"] else ""))
    if ev["last_call_summary"]:
        conv.append(f"- Last call summary: {ev['last_call_summary']}")
    if not conv:
        conv.append("- No IndiaMART conversations in the window")

    t = ev["tickets"]
    flags = [f"- Open tickets (7 d): {t['open_7d']} · negative feedback: {t['negative_feedback_7d']}"
             + (f" · WIP ticket: {t['wip_type']}" if t["wip_type"] else "")]
    live = [f"- 🔄 {e.get('time', '')} via **{e.get('channel', 'event')}**: {e.get('summary', '')[:160]}"
            for e in reversed(ev["live_events"][-3:])]
    if recent_calls_line(ev["live_events"]):
        flags.append(recent_calls_line(ev["live_events"]))
    return {"who": "\n".join(who), "recent": "\n".join(recent), "conv": "\n".join(conv),
            "flags": "\n".join(flags), "live": "\n".join(live)}


def _fallback_insight(ev: dict) -> dict:
    name = ev["profile"]["name"] or "ji"
    last = ev["recent_activity"][0] if ev["recent_activity"] else None
    what = (last["keyword"] or last["category"]) if last else None
    opener = (f"{name} ji, aapne {what} ke liye IndiaMART pe {last['what']} tha. Kya aapko abhi bhi chahiye?"
              if last else f"{name} ji, IndiaMART pe aapki recent requirement ke baare mein baat karni thi.")
    return {"story": f"The buyer has {len(ev['recent_activity'])} recent actions on IndiaMART.",
            "opener": opener, "next_action": "Ask whether the latest requirement is still open and connect a seller.",
            "avoid": "Do not ask for details already in the memory.",
            "greeting": fallback_greeting(name.split()[0], get_language(ev["glid"]))}


def render_md(ev: dict, insight: dict, src: str) -> str:
    f = render_facts(ev)
    p = ev["profile"]
    return f"""# Buyer memory — {p['name'] or 'Buyer'} (GLID {ev['glid']})
_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST · data as of {ev['as_of']} · window {ev['window']['activity_days']}d · source: getContext API · insight: {src}_

## Who
{f['who']}

## Story so far
{insight['story']}
{("\n## Latest across channels (live)\n" + f["live"] + "\n") if f["live"] else ""}
## Last {ev['window']['activity_days']} days
{f['recent']}

## Conversations with IndiaMART
{f['conv']}

## Flags
{f['flags']}

## For the next conversation
- **Language (spoke last):** {get_language(ev['glid'])}
- **Greeting:** {insight.get('greeting', '')}
- **Opener (Hinglish):** {insight['opener']}
- **Next best action:** {insight['next_action']}
- **Avoid:** {insight['avoid']}
"""


def build_buyer_md(glid: int, use_llm: bool = True) -> dict:
    t0 = time.perf_counter()
    ev = get_buyer_events(glid)
    t_src = time.perf_counter() - t0
    insight, t_llm, src = {}, 0.0, "rules"
    if use_llm:
        slim = {"live_events_newest_first": list(reversed(ev["live_events"][-3:]))}
        slim.update({k: v for k, v in ev.items() if k != "live_events"})
        insight, t_llm, src = llm_insight(slim, "buyer", extra=(
            "- A WhatsApp message from indiamart saying 'You just spoke with X' means the buyer phoned seller X at that "
            "time; count those as calls with sellers. 'X responded to your enquiry' means seller X replied.\n"
            "- Address the buyer by first name + ' ji'."),
            greeting_rule=greeting_rule(get_language(glid), (ev["profile"]["name"] or "ji").split()[0],
                                        latest=(ev["live_events"][-1]["summary"] if ev["live_events"] else None)))
    if not insight:
        insight = _fallback_insight(ev)
        src = "rules" if src == "rules" else src
    insight["greeting"] = clean_greeting(insight.get("greeting") or _fallback_insight(ev)["greeting"], ev["profile"]["name"] or "")
    insight["opener"] = insight.get("opener") or _fallback_insight(ev)["opener"]
    md = render_md(ev, insight, src)
    out = OUT_DIR / str(glid)
    out.mkdir(parents=True, exist_ok=True)
    (out / "buyer.md").write_text(md)
    (out / "events.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False))
    return {"path": str(out / "buyer.md"), "lines": md.count("\n"), "chars": len(md),
            "seconds_source": round(t_src, 2), "seconds_llm": round(t_llm, 2),
            "seconds_total": round(time.perf_counter() - t0, 2), "insight_source": src, "md": md}


if __name__ == "__main__":
    import sys
    g = int(sys.argv[1]) if len(sys.argv) > 1 else 274238067
    r = build_buyer_md(g, use_llm="--no-llm" not in sys.argv)
    print(r["md"])
    print({k: v for k, v in r.items() if k != "md"})
