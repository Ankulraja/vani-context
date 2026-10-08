"""Buyer data source: IndiaMART getContext JSON (Kibana export CSV) -> one clean dict for a GLID.

The CSV is an API log: column RESPONSE holds {"API_RESPONSE_JSON": "<json string>"} whose "data" is the
raw buyer context from exchange.intermesh.net/.../getContext. On Day 1 this file swaps to a live call
of that API; the output dict shape stays the same.

Lookback: activity 30 days before the snapshot; the API only ships ~last 90 days anyway.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.sources.seller import ROOT, live_events

BUYER_CSV = ROOT / "Dataset" / "Global_Context_Problem_Statement_Buyer Side.csv"
ACTIVITY_DAYS = 30

ACTIVITY_LABEL = {"ENQ": "enquiry sent", "C2C": "called seller", "Browse": "browsed", "Search": "searched",
                  "BL": "buy-lead posted", "Others": "other"}


@lru_cache(maxsize=1)
def _all_contexts() -> dict[int, tuple[dict, str]]:
    """glid -> (data, snapshot timestamp). Latest snapshot wins. Rows that failed to export are skipped."""
    df = pd.read_csv(BUYER_CSV, usecols=["GLUSR_ID", "REQUEST", "RESPONSE", "@timestamp"], low_memory=False)
    out: dict[int, tuple[dict, str]] = {}
    for _, r in df.sort_values("@timestamp").iterrows():
        try:
            d = json.loads(json.loads(r["RESPONSE"])["API_RESPONSE_JSON"])["data"]
            out[int(d["glid"])] = (d, str(r["@timestamp"]))
        except Exception:  # noqa: BLE001 — NaN / truncated JSON in the Kibana export
            continue
    return out


def buyer_glids() -> list[int]:
    return sorted(_all_contexts())


def _t(s: str | None) -> datetime | None:
    """'20260929180130' -> datetime"""
    try:
        return datetime.strptime(s, "%Y%m%d%H%M%S") if s else None
    except ValueError:
        return None


def _d(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _snapshot_time(ts: str, data: dict) -> datetime:
    up = ((data.get("ActualData") or {}).get("upload_metadata") or {}).get("upload_time")
    if up:
        try:
            return datetime.fromisoformat(up[:19])
        except ValueError:
            pass
    try:  # Kibana style: "Oct 1, 2026 @ 10:23:00.777"
        return datetime.strptime(ts.split(".")[0], "%b %d, %Y @ %H:%M:%S")
    except ValueError:
        return datetime(2026, 10, 1)


def _wa_text(chat: dict) -> str | None:
    try:
        mc = json.loads(chat.get("CHAT_CONTENT") or "{}").get("message_content") or {}
    except json.JSONDecodeError:
        return (chat.get("CHAT_CONTENT") or "")[:120] or None
    txt = mc.get("text") or ((mc.get("interactive") or {}).get("body") or {}).get("text") or mc.get("caption")
    return " ".join(str(txt).split())[:140] if txt else None


def get_buyer_events(glid: int) -> dict:
    ctx = _all_contexts()
    if glid not in ctx:
        raise KeyError(f"GLID {glid} not in buyer getContext export")
    data, ts = ctx[glid]
    as_of = _snapshot_time(ts, data)
    since = as_of - timedelta(days=ACTIVITY_DAYS)

    k = data.get("kycdetails") or {}
    a = data.get("activitydetails") or {}
    b = data.get("BLdetails") or {}
    c = data.get("connectdetails") or {}
    tk = data.get("ticketsdetails") or {}

    profile = {
        "name": (k.get("customer_name") or k.get("first_name") or "").strip() or None,
        "company": (k.get("company_name") or "").strip() or None,
        "city": (k.get("city") or "").strip() or None,
        "customer_type": (k.get("customer_type") or "").strip("- ") or "Free",
        "mobile_verified": k.get("input_mobile_verification_status") == "Verified",
        "email_verified": k.get("input_email_verification_status") == "Verified",
        "gst_verified": k.get("gst_status") == "Verified",
        "registered_since": (k.get("registered_since_with_indiamart") or "").strip() or None,
        "listing_status": k.get("glusr_usr_listing_status"),
        "preferred_cities": (data.get("ActualData") or {}).get("preferred_cities"),
    }

    # --- activity stream (30 d), newest first
    acts = []
    for x in a.get("BUYER_ACTIVITY") or []:
        dt = _t(x.get("ACTIVITY_TIME"))
        if not dt or dt < since or dt > as_of + timedelta(days=1):
            continue
        acts.append({"dt": dt, "date": _d(dt), "type": x.get("ACTIVITY_TYPE"),
                     "what": ACTIVITY_LABEL.get(x.get("ACTIVITY_TYPE"), x.get("ACTIVITY_TYPE")),
                     "category": None if x.get("CATEGORY_NAME") in (None, "-", "") else x["CATEGORY_NAME"],
                     "keyword": None if x.get("KEYWORD") in (None, "-", "") else x["KEYWORD"][:70],
                     "seller_glid": None if x.get("SELLER_GLUSR_ID") in (None, "0", "") else x["SELLER_GLUSR_ID"]})
    acts.sort(key=lambda e: e["dt"], reverse=True)
    counts = Counter(e["type"] for e in acts)
    cats = Counter(e["category"] for e in acts if e["category"]).most_common(4)
    sellers_contacted = {e["seller_glid"] for e in acts if e["type"] in ("ENQ", "C2C") and e["seller_glid"]}
    meaningful = [e for e in acts if e["type"] != "Others"]
    for e in acts:
        e.pop("dt")

    le = a.get("LAST_ENQUIRY") or {}
    ll = a.get("LAST_LEAD") or {}
    last_enquiry = {"title": le.get("TITLE") or None, "text": (le.get("DESCRIPTION") or "")[:140] or None} if le.get("TITLE") else None
    last_lead = {"title": ll.get("TITLE") or None, "date": (ll.get("DATE_R") or "")[:16] or None} if ll.get("TITLE") else None
    active_bls = [x.get("ETO_OFR_TITILE") for x in (b.get("active_bl_details") or []) if x.get("ETO_OFR_TITILE")]

    wa_raw = (a.get("LAST_WA9696_CHAT") or []) + (a.get("LAST_WA8181_CHAT") or [])
    whatsapp = []
    for w in sorted(wa_raw, key=lambda w: w.get("ENTRY_DATE", ""), reverse=True)[:6]:
        txt = _wa_text(w)
        if txt:
            whatsapp.append({"date": (w.get("ENTRY_DATE") or "")[:16], "from": "buyer" if w.get("MESSAGE_SENDER") != "API" else "indiamart", "text": txt})

    connects = [{"date": (x.get("call_answered_date") or "")[:16], "status": x.get("call_sts_update") or x.get("meet_sts_update") or "answered",
                 "summary": (x.get("call_answered_summary") or "")[:140] or None}
                for x in (c.get("connect_30D") or []) if x.get("call_answered_date")][:5]

    t7 = tk.get("last_7_days") or {}
    tickets = {"open_7d": int(t7.get("total_ticket_count") or 0), "negative_feedback_7d": int(t7.get("negative_feedback_count") or 0),
               "wip_type": (tk.get("wip_tickets") or {}).get("ticket_type") or None}

    return {
        "glid": glid,
        "role": "buyer",
        "as_of": as_of.strftime("%Y-%m-%d %H:%M"),
        "window": {"activity_days": ACTIVITY_DAYS},
        "profile": profile,
        "activity_counts": {ACTIVITY_LABEL.get(t, t): n for t, n in counts.items()},
        "top_categories": [{"category": cname, "events": n} for cname, n in cats],
        "sellers_contacted": len(sellers_contacted),
        "recent_activity": meaningful[:12],
        "last_enquiry": last_enquiry,
        "last_lead": last_lead,
        "active_buyleads": active_bls,
        "enquiries_30d": a.get("enq_last_30_days"),
        "enquiries_90d": a.get("enq_last_90_days"),
        "whatsapp": whatsapp,
        "indiamart_calls": connects,
        "tickets": tickets,
        "last_call_summary": (c.get("last_call_summary") or "")[:200] or None,
        "live_events": live_events(glid),
    }


if __name__ == "__main__":
    import sys
    g = int(sys.argv[1]) if len(sys.argv) > 1 else 274238067
    print(json.dumps(get_buyer_events(g), indent=2, ensure_ascii=False))
