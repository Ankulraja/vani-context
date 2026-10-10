"""Call card: the short memory VANI gets at the start of a call (~10 lines instead of the full ~35-line file).

Built by rules from the full .md + events.json, so it costs no extra LLM time. What it keeps:
who, the story, the 2 newest cross-channel events, open items, warnings, and the next-step fields.
Everything else stays in the full file and is fetched mid-call by the get_more_history tool.
"""
from __future__ import annotations


def _section(md: str, title: str) -> list[str]:
    """Lines under '## <title>' (prefix match) up to the next '## '."""
    out, on = [], False
    for line in md.splitlines():
        if line.startswith("## "):
            on = line[3:].startswith(title)
            continue
        if on and line.strip():
            out.append(line)
    return out


def _field(md: str, label: str) -> str:
    for line in md.splitlines():
        if line.startswith(f"- **{label}"):
            return line.split("**", 2)[2].strip()
    return ""


def build_call_card(md: str, ev: dict, role: str, glid: int, language: str) -> str:
    name = ev["profile"].get("name") or ev["profile"].get("company") or f"GLID {glid}"
    lines = [f"MEMORY CARD: {name} (GLID {glid}, {role}). Spoke {language} last time."]
    lines += _section(md, "Who")
    lines += ["Story: " + " ".join(_section(md, "Story so far"))]
    live = _section(md, "Latest across channels")[:2]
    if live:
        lines += ["Latest across channels:"] + [l.replace("🔄 ", "").replace("**", "") for l in live]

    open_items = []
    if role == "seller":
        if ev.get("unread_enquiries"):
            open_items.append(f"{ev['unread_enquiries']} unread enquiries")
        if ev.get("enquiries"):
            e = ev["enquiries"][0]
            open_items.append(f"latest enquiry {e['date'][:10]}: {e['product']} from {e.get('buyer_city') or 'a buyer'}")
        quoted = [q for q in ev.get("pns_calls", []) if q.get("prices")]
        if quoted:
            open_items.append(f"last phone quote: {quoted[0]['products']} at {quoted[0]['prices']}")
        # Health check + root cause, so the agent answers complaints from the WHOLE picture, not the latest enquiry (user rule, 10 Oct):
        # "I am not getting good enquiries" -> "24 enquiries are unread and none answered; any problem, or shall I reply for you?"
        e30, unread, rep = ev.get("enquiries_30d") or 0, ev.get("unread_enquiries") or 0, ev.get("seller_replies_30d") or 0
        bc, bl = ev.get("buyer_calls") or {}, ev.get("buyleads") or {}
        lines.append(f"Health check (last 30 days): {e30} enquiries received, {unread} unread, {rep} replies sent by the seller; "
                     f"buyer calls {bc.get('total', 0)} ({bc.get('missed', 0)} missed); buyleads bought {bl.get('count', 0)}"
                     + (f" for {bl.get('credits')} credits" if bl.get('credits') else "") + f"; WhatsApp messages {ev.get('whatsapp_30d', 0)}.")
        diag = []
        if e30 and rep == 0:
            diag.append(f"the seller has not replied to any of the {e30} enquiries ({unread} still unread)")
        elif unread >= 3:
            diag.append(f"{unread} enquiries are still unread")
        if bl.get("count") and rep == 0:
            diag.append(f"buyleads are being bought ({bl['count']}) but buyers get no reply")
        if bc.get("missed"):
            diag.append(f"{bc['missed']} buyer calls were missed")
        if (ev["profile"].get("product_count") or 0) < 5:
            diag.append("very few products are listed")
        if diag:
            lines.append("If the seller complains about enquiries, leads or buyers, the likely cause from the data is: " + "; ".join(diag)
                         + ". Say this first with the number, ask whether something is stopping them, and offer to reply to those buyers on their behalf.")
        p = ev["profile"]
        warn = [w for w, on in (("do-not-call requested", p.get("do_not_call")), ("showed frustration before", p.get("showed_frustration")),
                                ("already working with an IndiaMART executive", p.get("already_with_executive"))) if on]
    else:
        if ev.get("active_buyleads"):
            open_items.append("active buy-lead: " + "; ".join(ev["active_buyleads"][:2]))
        if ev.get("last_enquiry"):
            open_items.append("last enquiry: " + ev["last_enquiry"]["title"][:80])
        c = ev.get("activity_counts") or {}
        if c or ev.get("sellers_contacted"):
            lines.append("Activity (last 30 days): " + ", ".join(f"{v} {k}" for k, v in c.items() if v)
                         + (f"; sellers contacted: {sc if isinstance(sc, int) else len(sc)}" if (sc := ev.get("sellers_contacted")) else "") + ".")
        t = ev.get("tickets", {})
        warn = [w for w, on in (("open support ticket", t.get("open_7d")), ("negative feedback recently", t.get("negative_feedback_7d"))) if on]
    if open_items:
        lines.append("Open items: " + " · ".join(open_items))
    if warn:
        lines.append("Warnings: " + ", ".join(warn))
    lines.append("Next best action: " + _field(md, "Next best action:"))
    lines.append("Avoid: " + _field(md, "Avoid:"))
    lines.append("Older history is NOT in this card: call tool:get_more_history for anything else.")
    return "\n".join(lines)
