"""Seller data source: Dataset CSVs -> one clean dict of events for a GLID.

This is the ONLY file that knows the CSV layout. On Day 1, swap the loaders here
for the real IndiaMART starter APIs; the builder and bot never touch raw data.

Lookback window (decision, see CLAUDE.md):
  - transactional activity (enquiries, replies, buyer calls, buyleads, WhatsApp): 30 days
  - conversations with IndiaMART (VANI bot calls, executive calls): 180 days
  - profile / KYC facts: all-time
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Dataset" / "Global Context - Seller Dataset"
EVENTS_DIR = ROOT / "context_files"  # live events appended by the API land here

DATASET_END = datetime(2026, 10, 2, 23, 59, 59)  # last day covered by the CSVs
ACTIVITY_DAYS = 30
CONVERSATION_DAYS = 180


# ---------------------------------------------------------------- loading
@lru_cache(maxsize=None)
def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, low_memory=False)


def _rows(name: str, key: str, glid: int, date_col: str, since: datetime, until: datetime) -> pd.DataFrame:
    df = _csv(name)
    df = df[df[key] == glid].copy()
    df["dt"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df[(df["dt"] >= since) & (df["dt"] <= until)]
    return df.sort_values("dt", ascending=False)


def _s(v, limit: int | None = None) -> str | None:
    """NaN -> None, else str, optionally trimmed."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).replace("\r", " ").replace("\n", " ").strip()
    return (t[:limit] + "…") if limit and len(t) > limit else t


def _d(dt) -> str | None:
    return None if pd.isna(dt) else dt.strftime("%Y-%m-%d %H:%M")


def _n(v, default=0):
    return default if v is None or (isinstance(v, float) and pd.isna(v)) else v


# ---------------------------------------------------------------- live events
def live_events(glid: int) -> list[dict]:
    """Events appended at runtime (POST /events) — newest activity not in the CSVs."""
    f = EVENTS_DIR / str(glid) / "events.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------- main API
def get_seller_events(glid: int, as_of: datetime | None = None) -> dict:
    as_of = as_of or DATASET_END
    act_since = as_of - timedelta(days=ACTIVITY_DAYS)
    conv_since = as_of - timedelta(days=CONVERSATION_DAYS)

    prof_df = _csv("gc_seller_profile.csv")
    hit = prof_df[prof_df["fk_glusr_usr_id"] == glid]
    if hit.empty:
        raise KeyError(f"GLID {glid} not in gc_seller_profile.csv")
    p = hit.iloc[0]

    profile = {
        "company": _s(p["company_name"]),
        "city": _s(p["seller_city"]),
        "state": _s(p["seller_state"]),
        "business_type": _s(p["business_type"]),
        "categories": [c for c in (_s(p["top_category_1"]), _s(p["top_category_2"]), _s(p["top_category_3"])) if c],
        "paid": bool(_n(p["is_paid"]) == 1),
        "gst_verified": bool(_n(p["gst_verified_flag"]) == 1),
        "mobile_verified": bool(_n(p["mobile_verified_flag"]) == 1),
        "email_verified": bool(_n(p["email_verified_flag"]) == 1),
        "product_count": int(_n(p["eng_product_count"])),
        "catalog_quality_score": _n(p["eng_cqs"], None),
        "do_not_call": bool(_n(p["do_not_call_requested"]) == 1),
        "showed_frustration": bool(_n(p["showed_frustration"]) == 1),
        "asked_if_bot": bool(_n(p["asked_if_talking_to_bot"]) == 1),
        "already_with_executive": bool(_n(p["already_in_touch_with_executive"]) == 1),
        "past_objections": _s(p["past_objections"]),
        "past_questions": _s(p["past_questions_asked"], 200),
        "bot_attempts": int(_n(p["bot_attempts"])),
        "bot_answered": int(_n(p["bot_answered"])),
        "meetings_fixed": int(_n(p["calls_meeting_fixed"])),
    }

    # --- enquiries (30d) + unread count
    enq = _rows("gc_enquiries_received.csv", "seller_glid", glid, "enquiry_date", act_since, as_of)
    enquiries = [{
        "date": _d(r.dt), "product": _s(r.product_name), "buyer_city": _s(r.buyer_city),
        "buyer_company": _s(r.buyer_company), "unread": int(_n(r.read_status)) == 0,
        "message": _s(r.message, 120),
    } for r in enq.head(15).itertuples()]
    unread = int((enq["read_status"].fillna(0) == 0).sum())

    # --- replies in threads (30d)
    rep = _rows("gc_enquiry_messages.csv", "seller_glid", glid, "reply_date", act_since, as_of)
    replies = [{"date": _d(r.dt), "from": _s(r.message_from), "text": _s(r.reply_text, 120)}
               for r in rep.head(8).itertuples()]
    seller_replies = int((rep["message_from"] == "seller").sum())

    # --- buyer phone calls (30d)
    bc = _rows("gc_buyer_calls_received.csv", "seller_glid", glid, "call_datetime", act_since, as_of)
    buyer_calls = {
        "total": int(len(bc)),
        "connected": int((bc["call_status"] == "Connected").sum()),
        "missed": int((bc["call_status"] != "Connected").sum()),
        "last": _d(bc["dt"].iloc[0]) if len(bc) else None,
        "last_status": _s(bc["call_status"].iloc[0]) if len(bc) else None,
    }

    # --- buyleads bought (30d)
    bl = _rows("gc_buyleads_bought.csv", "seller_glid", glid, "purchase_date", act_since, as_of)
    buyleads = {
        "count": int(len(bl)),
        "credits": int(_n(bl["credits_used"].sum())),
        "last": _d(bl["dt"].iloc[0]) if len(bl) else None,
        "keywords": [k.split("_")[0] for k in bl["keyword"].dropna().unique()[:3]],
    }

    # --- WhatsApp chatbot (180d, it is a conversation) — seller-typed turns first, then template pushes
    wa = _rows("gc_whatsapp_chatbot_conversations.csv", "glid", glid, "entry_date", conv_since, as_of)
    typed = wa[wa["user_message"].notna() & (wa["user_message"].astype(str).str.len() > 2)]
    pushed = wa[wa["user_message"].isna() & wa["intent"].notna()]
    wa_rows = pd.concat([typed.head(6), pushed.head(3)]).sort_values("dt", ascending=False)
    whatsapp = [{"date": _d(r.dt), "seller_said": _s(r.user_message, 120),
                 "bot_said": _s(r.bot_reply, 100), "intent": _s(r.intent)}
                for r in wa_rows.itertuples()]
    whatsapp_30d = int(len(wa[wa["dt"] >= act_since]))

    # --- VANI bot calls (180d) + latest transcript
    bot = _rows("gc_bot_calls.csv", "fk_glusr_usr_id", glid, "call_start_time", conv_since, as_of)
    vani_calls = [{"date": _d(r.dt), "disposition": _s(r.disposition_label),
                   "meeting_fixed": int(_n(r.meeting_fixed)) == 1,
                   "duration_sec": int(_n(r.lead_call_duration)), "summary": _s(r.lead_call_summary, 300),
                   "attempt_id": r.attempt_id}
                  for r in bot.head(6).itertuples()]
    transcript: list[str] = []
    transcript_date = None
    if vani_calls:
        turns = _csv("gc_bot_call_turns.csv")
        t = turns[turns["fk_glusr_usr_id"] == glid]
        if not t.empty:  # latest call that has a transcript
            by_call = {c["attempt_id"]: c["date"] for c in vani_calls}
            have = [a for a in by_call if a in set(t["attempt_id"])]
            if have:
                aid = have[0]
                transcript_date = by_call[aid]
                t = t[t["attempt_id"] == aid].sort_values("turn_no")
                transcript = [f"{r.speaker}: {_s(r.text)}" for r in t.itertuples()]
    for c in vani_calls:
        c.pop("attempt_id")

    # --- IndiaMART executive calls (180d)
    ex = _rows("gc_executive_calls.csv", "fk_glusr_usr_id", glid, "call_start_time", conv_since, as_of)
    executive_calls = {
        "total": int(len(ex)),
        "answered": int((ex["status"] == "Answered").sum()),
        "last": _d(ex["dt"].iloc[0]) if len(ex) else None,
        "last_duration_sec": int(_n(ex["call_duration"].iloc[0])) if len(ex) else None,
    }

    # --- PNS call extractions where this seller acted as SELLER (180d)
    px = _rows("gc_buyer_call_extractions.csv", "glid", glid, "call_date", conv_since, as_of)
    px = px[px["seller_role_on_call"] == "SELLER"]
    pns_calls = [{"date": _d(r.dt), "products": _s(r.products_discussed, 80), "prices": _s(r.prices_quoted, 60)}
                 for r in px.head(4).itertuples()]

    return {
        "glid": glid,
        "as_of": as_of.strftime("%Y-%m-%d %H:%M"),
        "window": {"activity_days": ACTIVITY_DAYS, "conversation_days": CONVERSATION_DAYS},
        "profile": profile,
        "enquiries": enquiries,
        "enquiries_30d": int(len(enq)),
        "unread_enquiries": unread,
        "replies": replies,
        "seller_replies_30d": seller_replies,
        "buyer_calls": buyer_calls,
        "buyleads": buyleads,
        "whatsapp": whatsapp,
        "whatsapp_30d": whatsapp_30d,
        "vani_calls": vani_calls,
        "vani_transcript_date": transcript_date,
        "vani_latest_transcript": transcript,
        "executive_calls": executive_calls,
        "pns_calls": pns_calls,
        "live_events": live_events(glid),
    }


if __name__ == "__main__":
    import sys
    g = int(sys.argv[1]) if len(sys.argv) > 1 else 95568576
    print(json.dumps(get_seller_events(g), indent=2, ensure_ascii=False))
