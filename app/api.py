"""VANI Context API — what the Sarvam Voice Agent (and anything else) calls.

  GET  /context/{glid}            -> {"name", "company", "opener", "context", "updated_at", ...}
                                     (used by the agent's on_start tool; fields map to agent variables)
  GET  /context/{glid}/seller.md  -> the raw markdown file (reusable outside the bot)
  POST /events/{glid}             -> append a new event (e.g. call summary from on_end), regenerate
                                     seller.md, return freshness seconds
  GET  /health

Run:  uvicorn app.api:app --reload --port 8000
Then expose with ngrok so Sarvam can reach it:  ngrok http 8000
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.builder.buyer_md import build_buyer_md
from app.sources.seller import ROOT
from app.builder.seller_md import OUT_DIR, build_seller_md
from app.sources.buyer import _all_contexts as _buyer_contexts
from app.sources.seller import _csv as _seller_csv

app = FastAPI(title="VANI Context API", version="0.1")


# ------------------------------------------------------------------ helpers
def role_of(glid: int) -> str:
    """'seller' if the GLID is in the seller profile CSV, 'buyer' if in the buyer getContext export."""
    prof = _seller_csv("gc_seller_profile.csv")
    if (prof["fk_glusr_usr_id"] == glid).any():
        return "seller"
    if glid in _buyer_contexts():
        return "buyer"
    raise HTTPException(status_code=404, detail=f"GLID {glid} not found in seller or buyer data")


PHONE_MAP = ROOT / "data" / "phone_to_glid.json"


def glid_from_phone(phone: str) -> int:
    """Caller number -> GLID. Dataset has no numbers, so a small JSON map stands in for the IndiaMART
    user-lookup API. Matches on the last 10 digits so +91 / 0 prefixes do not matter."""
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if len(digits) < 10:
        raise HTTPException(status_code=400, detail=f"phone {phone!r} too short")
    table = json.loads(PHONE_MAP.read_text()) if PHONE_MAP.exists() else {}
    for k, v in table.items():
        if k.startswith("_"):
            continue
        if "".join(ch for ch in k if ch.isdigit())[-10:] == digits[-10:]:
            return int(v)
    raise HTTPException(status_code=404, detail=f"no GLID mapped for phone ending {digits[-4:]}")


def build_context(glid: int) -> dict:
    return build_seller_md(glid) if role_of(glid) == "seller" else build_buyer_md(glid)


def _md_path(glid: int) -> Path:
    return OUT_DIR / str(glid) / f"{role_of(glid)}.md"


def _parse_md(md: str) -> dict:
    """Pull the few fields the agent needs as separate variables out of the markdown."""
    out = {"opener": "", "next_action": "", "avoid": "", "story": ""}
    for line in md.splitlines():
        if line.startswith("- **Opener (Hinglish):**"):
            out["opener"] = line.split("**", 2)[2].strip()
        elif line.startswith("- **Next best action:**"):
            out["next_action"] = line.split("**", 2)[2].strip()
        elif line.startswith("- **Avoid:**"):
            out["avoid"] = line.split("**", 2)[2].strip()
    if "## Story so far" in md:
        out["story"] = md.split("## Story so far", 1)[1].split("##", 1)[0].strip()
    return out


def _ensure_built(glid: int, rebuild: bool = False) -> dict:
    p = _md_path(glid)
    if rebuild or not p.exists():
        try:
            return build_context(glid)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    md = p.read_text()
    return {"path": str(p), "md": md, "seconds_total": 0.0, "insight_source": "cached"}


# ------------------------------------------------------------------ routes
@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat(timespec="seconds")}


@app.get("/context/{glid}")
def get_context(glid: int, rebuild: bool = False):
    """Everything the agent needs before it speaks. Flat keys so Sarvam's
    'save reply into variables' can map them 1:1 to agent variables."""
    r = _ensure_built(glid, rebuild)
    md = r["md"]
    events = json.loads((OUT_DIR / str(glid) / "events.json").read_text())
    fields = _parse_md(md)
    role = role_of(glid)
    prof = events["profile"]
    name = prof.get("name") or prof.get("company") or f"GLID {glid}"  # sellers have no person name; the company works as the address
    company = prof.get("company") or name
    return {
        "glid": glid,
        "role": role,
        "name": name,
        "company": company,
        "city": prof.get("city"),
        "opener": fields["opener"],
        "next_action": fields["next_action"],
        "avoid": fields["avoid"],
        "story": fields["story"],
        "unread_enquiries": events.get("unread_enquiries", 0),
        "context": md,  # full seller.md / buyer.md goes into the agent's prompt as {{user_context}}
        "updated_at": datetime.fromtimestamp(_md_path(glid).stat().st_mtime).isoformat(timespec="seconds"),
        "build_seconds": r["seconds_total"],
        "insight_source": r["insight_source"],
    }


@app.get("/context")
def get_context_q(glid: int | None = None, phone: str | None = None, rebuild: bool = False):
    """Same as /context/{glid} but with ?glid= or ?phone= — easier to bind to agent variables in Sarvam tools.
    Inbound calls only know the caller's number, so ?phone= resolves it to a GLID first."""
    if glid is None and phone:
        glid = glid_from_phone(phone)
    if glid is None:
        raise HTTPException(status_code=400, detail="pass glid or phone")
    return get_context(glid, rebuild)


@app.get("/context/{glid}/seller.md", response_class=PlainTextResponse)
@app.get("/context/{glid}/buyer.md", response_class=PlainTextResponse)
@app.get("/context/{glid}/md", response_class=PlainTextResponse)
def get_context_md(glid: int):
    return _ensure_built(glid)["md"]


class Event(BaseModel):
    channel: str = Field(..., examples=["voice", "whatsapp", "chat", "app"])
    summary: str = Field(..., examples=["Seller asked to call back after Diwali about the Barmer pen drive enquiry"])
    time: str | None = None  # ISO; defaults to now
    meta: dict = Field(default_factory=dict)  # disposition, interaction_id, etc.


# ------------------------------------------------------------------ Sarvam call-end webhook
def _summarise_transcript(turns: list[dict]) -> str:
    """2-line summary of a Sarvam transcript via sarvam-105b (reasoning OFF). Falls back to last user line."""
    lines = [f"{t.get('role', '?')}: {t.get('indic_text') or t.get('en_text', '')}" for t in turns if t]
    if not lines:
        return ""
    try:
        import os
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(
            model="sarvam-105b", temperature=0.2, reasoning_effort=None, max_tokens=200,
            messages=[{"role": "user", "content":
                       "Summarise this IndiaMART call between VANI (agent) and a seller (user) in 2 short English "
                       "sentences: what was agreed, any price/quantity/time mentioned, and what the seller wants next. "
                       "Facts only.\n\n" + "\n".join(lines)[-4000:]}],
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:  # noqa: BLE001
        users = [l for l in lines if l.startswith("user:")]
        return ("Seller said: " + users[-1][5:].strip()) if users else lines[-1]


@app.post("/webhook/sarvam")
def sarvam_webhook(payload: dict):
    """Sarvam POSTs here after every call (campaign / inbound deployment / instant outbound).
    Shape: sarvam://schemas/webhook-payload. We read glid + call_summary from the agent variables,
    else summarise interaction_transcript, then append the event and rebuild the memory file."""
    fav = payload.get("final_agent_variables") or {}
    oav = payload.get("output_agent_variables") or {}
    iav = payload.get("initial_agent_variables") or {}
    glid = fav.get("glid") or oav.get("glid") or iav.get("glid") or payload.get("user_identifier")
    try:
        glid = int(str(glid))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"no usable glid in payload (got {glid!r})")
    summary = (oav.get("call_summary") or fav.get("call_summary") or "").strip()
    source = "call_summary"
    if not summary:
        summary = _summarise_transcript(payload.get("interaction_transcript") or [])
        source = "transcript_llm"
    if not summary:
        return {"ok": False, "glid": glid, "skipped": "no summary and no transcript"}
    ev = Event(channel="voice", summary=summary, time=None, meta={
        "interaction_id": payload.get("interaction_id"), "duration": payload.get("duration"),
        "connectivity": payload.get("connectivity_status"), "summary_source": source,
    })
    r = post_event(glid, ev)
    r["summary_source"] = source
    return r


@app.get("/events/{glid}")
def list_events(glid: int):
    """Live events appended so far (newest last)."""
    f = OUT_DIR / str(glid) / "events.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]


class CallRequest(BaseModel):
    glid: int
    phone: str


@app.post("/call")
def call_me(req: CallRequest):
    """Ask Sarvam to place an outbound call to `phone` with this GLID's memory (Instant Outbound API).
    Needs a Sarvam phone number (connection) + API key — set SARVAM_AGENT_API_KEY, SARVAM_CONNECTION_ID,
    SARVAM_AGENT_NUMBER in .env once the workspace has a number (event day). Until then returns 503."""
    key, conn, agent_no = os.getenv("SARVAM_AGENT_API_KEY"), os.getenv("SARVAM_CONNECTION_ID"), os.getenv("SARVAM_AGENT_NUMBER")
    app_id = os.getenv("SARVAM_APP_ID", "VANI-IndiaM-b67b20da-8a1b")
    if not (key and conn and agent_no):
        raise HTTPException(status_code=503, detail="Outbound not configured yet: workspace has no Sarvam phone number. "
                            "Set SARVAM_AGENT_API_KEY / SARVAM_CONNECTION_ID / SARVAM_AGENT_NUMBER in .env.")
    import httpx
    body = {
        "app_config": {"app_id": app_id, "app_version": int(os.getenv("SARVAM_APP_VERSION", "2")),
                       "connection_config": {"connection_id": conn, "agent_phone_number": agent_no},
                       "agent_variables": {"glid": str(req.glid)}},
        "user_config": {"user_phone_number": req.phone},
        "webhook_config": {"url": os.getenv("PUBLIC_URL", "").rstrip("/") + "/webhook/sarvam", "metadata": {"glid": req.glid}},
    }
    r = httpx.post("https://apps.sarvam.ai/api/outbounds/v1/calls", headers={"X-API-Key": key}, json=body, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Sarvam said {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": f"Sarvam is calling {req.phone} with memory of GLID {req.glid}", "sarvam": r.json()}


class EventWithGlid(Event):
    glid: int


@app.post("/events")
def post_event_q(ev: EventWithGlid):
    """Same as /events/{glid} but glid in the body — for the agent's on_end tool."""
    return post_event(ev.glid, Event(**ev.model_dump(exclude={"glid"})))


@app.post("/events/{glid}")
def post_event(glid: int, ev: Event):
    """Append one new event and regenerate the memory file. Returns how long freshness took."""
    t0 = time.perf_counter()
    if not ev.summary.strip():  # e.g. on_end fired before the call summary was extracted
        return {"ok": False, "glid": glid, "skipped": "empty summary", "freshness_seconds": 0.0}
    d = OUT_DIR / str(glid)
    d.mkdir(parents=True, exist_ok=True)
    rec = ev.model_dump()
    rec["time"] = rec["time"] or datetime.now().strftime("%Y-%m-%d %H:%M")
    with (d / "events.jsonl").open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        r = build_context(glid)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "ok": True,
        "glid": glid,
        "event": rec,
        "freshness_seconds": round(time.perf_counter() - t0, 2),
        "insight_source": r["insight_source"],
        "opener": _parse_md(r["md"])["opener"],
    }


# ------------------------------------------------------------------ demo web page (must be last: catches "/")
app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="web")
