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
import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from app.builder.buyer_md import build_buyer_md
from app.builder.call_card import build_call_card
from app.builder.prefs import get_language, set_language
from app.sources.seller import ROOT
from app.builder.seller_md import OUT_DIR, build_seller_md
from app.sources.buyer import _all_contexts as _buyer_contexts
from app.sources.seller import _csv as _seller_csv

load_dotenv(ROOT / ".env")

app = FastAPI(title="VANI Context API", version="0.1")


@app.exception_handler(RequestValidationError)
async def _log_validation(request: Request, exc: RequestValidationError):
    """A 422 from a Sarvam tool is otherwise invisible: log the raw body so the tool's body shape can be fixed."""
    body = (await request.body())[:600]
    entry = {"time": datetime.now().isoformat(timespec="seconds"), "method": request.method, "path": request.url.path,
             "content_type": request.headers.get("content-type"), "body": body.decode("utf-8", "replace"), "errors": [str(e) for e in exc.errors()[:3]]}
    _LAST_422.append(entry); del _LAST_422[:-10]
    print(f"[422] {entry}", flush=True)
    return JSONResponse(status_code=422, content={"detail": exc.errors()[:3], "spoken": "Details could not be sent right now; they have been noted."})


_LAST_422: list[dict] = []


@app.get("/debug/422")
def last_422():
    """Last rejected request bodies (to see exactly what a Sarvam tool sends)."""
    return _LAST_422

# The demo page frames the real indiamart.com and a Chrome extension there posts events to us from another origin.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    out = {"opener": "", "next_action": "", "avoid": "", "story": "", "greeting": ""}
    for line in md.splitlines():
        if line.startswith("- **Greeting:**"):
            out["greeting"] = line.split("**", 2)[2].strip()
        elif line.startswith("- **Opener (Hinglish):**"):
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
        "language": get_language(glid),  # language the user spoke last -> agent variable preferred_language
        "greeting": fields["greeting"],  # personalised first line, in that language -> agent variable greeting
        "call_card": build_call_card(md, events, role, glid, get_language(glid)),  # short memory -> {{user_context}}
        "context": md,  # full seller.md / buyer.md (web page, other teams; agent reads parts via /history)
        "updated_at": datetime.fromtimestamp(_md_path(glid).stat().st_mtime).isoformat(timespec="seconds"),
        "build_seconds": r["seconds_total"],
        "insight_source": r["insight_source"],
    }


def resolve_uid(uid: str) -> int | None:
    """Sarvam 'User Identifier': a GLID (web widget user-id) or a caller phone number (inbound call).
    Returns a GLID or None if it is neither."""
    digits = "".join(ch for ch in str(uid) if ch.isdigit())
    if not digits:
        return None
    if len(digits) <= 9 or (len(digits) == 10 and not str(uid).startswith("+")):
        try:
            g = int(digits)
            role_of(g)
            return g
        except HTTPException:
            pass
    try:
        return glid_from_phone(digits)
    except HTTPException:
        return None


# ------------------------------------------------------------------ demo: "active GLID" from the web page
# Sarvam leaves the tool's {{user_identifier}} empty, so the widget's user-id never reaches us. Demo workaround:
# the web page POSTs the GLID it has selected; an agent call without a usable uid gets that GLID.
# One active user at a time — fine for a demo, not for production.
ACTIVE_FILE = OUT_DIR / "_active.json"


class CallIntent(BaseModel):
    """Why the NEXT call happens, set by the demo page just before it rings / dials.
    outbound = IndiaMART (VANI) calls the user about a flag (enquiry, WhatsApp help request, dashboard action);
    inbound  = the user calls IndiaMART: about one product (Call Now on a card) or the general helpline (dialer)."""
    direction: str = Field(..., pattern="^(inbound|outbound)$")
    source: str | None = None       # enquiry | whatsapp | dashboard | product | dialer
    reason: str | None = None       # one English line for the agent and the greeting writer
    label: str | None = None        # short human label shown on the phone
    product: dict | None = None     # product card (title, company, city, price_text, ...) when the call is about one


class Active(BaseModel):
    glid: int
    call: CallIntent | None = None


CALL_LINES_PROMPT = """You write the first words of a phone call between Tanya (IndiaMART's voice assistant; she introduces herself only as "Tanya from IndiaMART", never as VANI) and a {role} named {name}.
{situation}
Latest things in the {role}'s memory (newest first):
{latest}

Write ONLY a JSON object with two keys:
- "greeting": Tanya's very first sentence(s), in {language}{script}, under 30 words, entirely in that language (Hindi means Devanagari Hindi sentences with only product/brand names in English, never full English sentences). It starts by greeting {name} BY NAME (e.g. "नमस्ते {name}, …"). {greeting_rule}
- "opener": the next thing Tanya says after the {role} responds, Hinglish in Roman script, under 25 words: {opener_rule}
Vocabulary: a buyer SENDS enquiries ("aapne enquiry bheji thi", "aapne X dekha tha"); a seller RECEIVES them from buyers ("aapko X ki enquiry aayi thi", "buyer ne pucha hai"). Never say that a seller sent or made an enquiry.
Tanya, the speaker, is a woman: in Hindi or Hinglish she uses FEMININE forms for herself ("main bol rahi hoon", "kar sakti hoon", "bhej deti hoon", "karungi"; Devanagari "बोल रही हूँ", "कर सकती हूँ"), never masculine ("bol raha hoon", "kar sakta hoon"). The user is addressed only with neutral polite "aap" forms; the user's gender is never guessed from the name.
Facts only from the lines above. No prices unless given above. Never invent names, dates or numbers."""


def _call_lines(glid: int, role: str, name: str, intent: CallIntent) -> dict:
    """greeting + opener + a call-card line for one specific call. LLM with a template fallback."""
    language = get_language(glid)
    name = name.split()[0] if role == "buyer" and name else name   # a person is greeted by first name, a seller by company name
    p = intent.product or {}
    ptxt = ""
    if p:
        ptxt = f"{p.get('title', '')}" + (f" from {p.get('company')}" if p.get("company") else "") + (f", {p.get('city')}" if p.get("city") else "") + (f" ({p.get('price_text')})" if p.get("price") else "")
    who = "buyer" if role == "buyer" else "seller"
    if intent.direction == "outbound":
        situation = f"Tanya is CALLING the {who} (outbound call from IndiaMART). Reason: {intent.reason or 'a recent activity that may need help'}."
        greeting_rule = f"Tanya says who is calling (Tanya from IndiaMART), names the reason in a few words, and asks if this is a good time."
        opener_rule = "offer concrete help with exactly that reason (e.g. share quotes, connect to the seller, fix the issue) and ask one question."
        card = f"THIS CALL: Tanya (IndiaMART) called the {who} because: {intent.reason}. Stay on that topic; help with it first."
        g_fb = f"नमस्ते {name}, मैं IndiaMART से Tanya बोल रही हूँ। {('आपकी ' + ptxt + ' की enquiry') if ptxt else 'आपकी हाल की request'} के बारे में call किया है, अभी बात कर सकते हैं?"
        o_fb = (f"Aapne abhi {ptxt or 'ek request'} ke liye enquiry bheji thi, main best quotes dilwane mein help kar sakti hoon. Quantity kitni chahiye?" if who == "buyer"
                else f"Aapko abhi {ptxt or 'ek buyer'} ki enquiry aayi hai, kya main buyer ko aapka reply ya rate bhej doon?")
    elif intent.source == "product" and p:
        situation = f"The {who} has CALLED IndiaMART (inbound) by pressing Call Now on this product: {ptxt}."
        greeting_rule = "Tanya welcomes the caller to IndiaMART, says it can see they are calling about that product (name it), and asks what they want to know."
        opener_rule = "stay on that product: ask quantity / delivery city, or offer to get the best price from that supplier."
        card = f"THIS CALL: the {who} called IndiaMART about this product: {ptxt}. Keep the whole call about this product and its supplier."
        g_fb = f"नमस्ते {name}, IndiaMART में आपका स्वागत है। आप {p.get('title', '')} के बारे में call कर रहे हैं, बताइए क्या जानना है?"
        o_fb = f"{p.get('title', '')} ke liye aapko kitni quantity chahiye, aur delivery kahan honi hai?"
    elif who == "seller":
        # A seller who dials the helpline gets a plain customer-care welcome (name + Tanya + "what help is needed").
        # Their latest RECEIVED enquiry is offered only in the opener, after they say why they called (user rule, 10 Oct).
        situation = "The seller has CALLED the IndiaMART helpline (inbound, no specific topic chosen)."
        greeting_rule = ("Tanya says she is Tanya from the IndiaMART helpline and asks what help is needed today. "
                         "The greeting does NOT mention any enquiry, buyer, product or past activity.")
        opener_rule = ("if the lines above show an enquiry the seller RECEIVED, offer it in seller words ('aapko X ki enquiry aayi thi, "
                       "buyer ko reply bhej doon?'); otherwise ask one short question about what they need today.")
        card = ("THIS CALL: the seller called the IndiaMART helpline. First ask what they need help with; only after they answer, "
                "offer the latest enquiry they RECEIVED (seller vocabulary: 'aapko enquiry aayi thi'). Never say the seller sent an enquiry.")
        g_fb = f"नमस्ते {name}, मैं Tanya, IndiaMART helpline से। बताइए, आज किस चीज़ में help चाहिए?"
        o_fb = "Aapko jo latest enquiry aayi hai, kya main us buyer ko aapka reply bhej doon?"
    else:
        situation = f"The {who} has CALLED the IndiaMART helpline (inbound, no specific topic chosen)."
        greeting_rule = "Tanya welcomes the caller to the IndiaMART helpline, recalls their most recent activity in a few words (from the lines above), and asks whether they need help with that or something else."
        opener_rule = "ask one short question to find out what they need help with today."
        card = f"THIS CALL: the {who} called the IndiaMART helpline. First recall their latest activity in one line, then ask what they need help with."
        g_fb = f"नमस्ते {name}, IndiaMART helpline में आपका स्वागत है। बताइए, आज किस चीज़ में help चाहिए?"
        o_fb = "Aap kis product ya enquiry ke baare mein baat karna chahte hain?"
    latest = [f"- {e.get('time', '')} via {e.get('channel', '')}: {e.get('summary', '')}" for e in list_events(glid)[-4:][::-1]] or ["- (nothing yet)"]
    script = (" (Devanagari script, product and brand names in English letters; polite gender-neutral forms only: 'आप कर रहे हैं', "
              "'चाहेंगे', 'कैसे हैं' - never guess the person's gender from the name)") if language == "Hindi" else ""
    out = {"greeting": g_fb, "opener": o_fb, "card_line": card, "source": "fallback"}
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(model="sarvam-105b", temperature=0.2, reasoning_effort=None, max_tokens=300,
                                    messages=[{"role": "user", "content": CALL_LINES_PROMPT.format(
                                        role=who, name=name, situation=situation, latest="\n".join(latest), language=language, script=script,
                                        greeting_rule=greeting_rule, opener_rule=opener_rule)}])
        text = (r.choices[0].message.content or "").strip()
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        if data.get("greeting"):
            out.update(greeting=data["greeting"].strip(), opener=(data.get("opener") or o_fb).strip(), source="llm")
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:80]
    from app.builder.prefs import feminine
    out["greeting"] = feminine(_ensure_name(out["greeting"], name, language))
    out["opener"] = feminine(out["opener"])
    return out


def _ensure_name(greeting: str, name: str, language: str) -> str:
    """The first line must greet the user by name when the name is known (user rule). If the LLM left it out,
    the name is put right after the opening word."""
    first = (name or "").split()[0] if name else ""
    if not first or first.lower() in ("ji", "glid") or first.lower() in greeting.lower():
        return greeting
    hello = "Hello" if language == "English" else "नमस्ते"
    body = re.sub(r"^(नमस्ते|नमस्कार|namaste|hello|hi|hey)[,!।]?\s*", "", greeting.strip(), flags=re.I)
    return f"{hello} {first}, {body[0].lower() + body[1:] if language == 'English' and body else body}"


@app.post("/active")
def set_active(a: Active):
    role = role_of(a.glid)  # 404 for unknown GLIDs
    data = {"glid": a.glid, "set_at": datetime.now().isoformat(timespec="seconds")}
    if a.call:
        t0 = time.perf_counter()
        ctx = get_context(a.glid)
        lines = _call_lines(a.glid, role, ctx["name"], a.call)
        data["call"] = a.call.model_dump() | lines | {"set_at": data["set_at"], "seconds": round(time.perf_counter() - t0, 2)}
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(json.dumps(data, ensure_ascii=False))
    return data


@app.delete("/active/call")
def clear_call_intent():
    data = get_active()
    data.pop("call", None)
    ACTIVE_FILE.write_text(json.dumps(data, ensure_ascii=False))
    return data


@app.get("/active")
def get_active():
    return json.loads(ACTIVE_FILE.read_text()) if ACTIVE_FILE.exists() else {"glid": None}


@app.get("/context")
def get_context_q(glid: int | None = None, phone: str | None = None, uid: str | None = None, rebuild: bool = False):
    """Same as /context/{glid} but with ?glid= / ?phone= / ?uid= — easy to bind to agent variables in Sarvam tools.
    Priority: uid (Sarvam User Identifier: widget user-id = GLID, or inbound caller number) → active GLID set by
    the web page (only when the uid param is present but unusable, i.e. an agent call) → phone → glid.
    A uid that resolves to nothing falls back to glid (the agent's default), so a demo never dies."""
    if uid and not str(uid).startswith("user_"):  # widget default is user_<timestamp> = anonymous
        g = resolve_uid(uid)
        if g is not None:
            glid = g
            uid = None  # resolved, skip the active-GLID fallback below
    intent = None
    if uid is not None and get_active().get("glid"):  # agent call (sends uid=) with no usable uid -> page's GLID
        active = get_active()
        glid = active["glid"]
        intent = active.get("call")
    if glid is None and phone:
        glid = glid_from_phone(phone)
    if glid is None:
        raise HTTPException(status_code=400, detail="pass glid, phone or uid")
    res = get_context(glid, rebuild)
    if intent and intent.get("greeting"):  # this call has a known reason: VANI opens on it, and the card says what kind of call it is
        res = res | {"greeting": intent["greeting"], "opener": intent["opener"], "call_intent": intent,
                     "call_card": intent["card_line"] + "\n" + res["call_card"]}
        data = get_active(); data.pop("call", None); data["last_call"] = intent; ACTIVE_FILE.write_text(json.dumps(data, ensure_ascii=False))  # one call only; kept as last_call for mid-call tools
    return res


# ------------------------------------------------------------------ mid-call: older history on demand
HISTORY_PROMPT = """You help VANI, IndiaMART's voice agent, answer a question during a live call with a {role}.
Use ONLY the memory file and raw data below. Answer in {language}{script}, in 1 or 2 short spoken sentences
(under 40 words), no markdown, no lists. Speak TO the {role} as "aap" (second person), never "the {role}". Say prices and dates the way a person says them. If the answer is not
in the data, say that this detail is not available right now and offer to note it. Never invent facts.
Think from the {role}'s side over the WHOLE memory file, not only the latest item: when the question is a complaint or a
"why" (no good enquiries, leads not working, buyers not responding), find the cause in the numbers (unread or unanswered
enquiries, missed buyer calls, buyleads bought without replies, few products) and say it first with the number, then ask
one question or offer one concrete action (for a seller: reply to those buyers on their behalf; for a buyer: more sellers).
If the question is about what the {role} just did or sent (WhatsApp, website, enquiry, "just now"), answer from
LIVE EVENTS (newest first; today is {today}) and the WHATSAPP CHAT below: say what they did or wrote, then one
short follow-up question about it.

QUESTION: {question}

LIVE EVENTS (newest first):
{live}

WHATSAPP CHAT (latest turns):
{wa}

MEMORY FILE:
{md}

RAW DATA (JSON, trimmed):
{raw}
"""


@app.get("/history")
def get_history(glid: int, question: str = ""):
    """Run tool for the agent: answers a question about the user's older history (not in the call card).
    Returns a short spoken answer in the user's language; the agent reads `answer` out."""
    t0 = time.perf_counter()
    md = _ensure_built(glid)["md"]
    role, language = role_of(glid), get_language(glid)
    ev = json.loads((OUT_DIR / str(glid) / "events.json").read_text())
    first = ["vani_calls", "vani_latest_transcript", "executive_calls", "whatsapp", "pns_calls", "indiamart_calls",
             "recent_activity", "enquiries", "buyleads", "buyer_calls", "active_buyleads", "last_enquiry", "last_lead"]
    ordered = {k: ev[k] for k in first if k in ev} | {k: v for k, v in ev.items() if k not in first and k != "replies"}
    raw = json.dumps(ordered, ensure_ascii=False)[:12000]
    script = " (Devanagari script, product and brand names in English letters)" if language == "Hindi" else ""
    live_rows = list_events(glid)[-5:][::-1]  # read fresh: includes anything posted during the call
    live = "\n".join(f"- {e.get('time', '')} via {e.get('channel', '')}: {e.get('summary', '')}" for e in live_rows) or "(none)"
    wa = "\n".join(f"{'USER' if t['from'] == 'user' else 'BOT'}: {t['text']}" for t in _wa_thread(glid)[-6:]) or "(none)"
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(
            model="sarvam-105b", temperature=0.2, reasoning_effort=None, max_tokens=250,
            messages=[{"role": "user", "content": HISTORY_PROMPT.format(
                role=role, language=language, script=script, question=question or "summarise the older history", md=md, raw=raw,
                live=live, wa=wa, today=datetime.now().strftime("%d %B %Y %H:%M"))}])
        answer = (r.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001
        answer = ""
        print("history LLM failed:", e)
    if not answer:  # fallback: the story line from the file
        answer = _parse_md(md)["story"] or "Is detail ki jaankari abhi available nahi hai."
    return {"glid": glid, "question": question, "answer": answer, "seconds": round(time.perf_counter() - t0, 2)}


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
    language: str | None = None  # language the user spoke last on this channel (Sarvam name, e.g. Hindi / English)
    outcome: str | None = None  # voice only: agent's call_outcome (resumed_and_helped / callback_fixed / ... / no_conversation)
    callback_time: str | None = None  # voice only: "tomorrow 11 AM" if the user asked for a callback


# Calls where nothing really happened. Their summaries ("the user gave an unclear response") must not become the
# newest memory, otherwise the next opener continues from a non-conversation.
SKIP_OUTCOMES = {"no_conversation", "wrong_person"}


# ------------------------------------------------------------------ Sarvam call-end webhook
def _summarise_transcript(turns: list[dict], role: str = "seller") -> str:
    """2-line summary of a Sarvam transcript via sarvam-105b (reasoning OFF). Falls back to last user line."""
    lines = [f"{t.get('role', '?')}: {t.get('indic_text') or t.get('en_text', '')}" for t in turns if t]
    if not lines:
        return ""
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(
            model="sarvam-105b", temperature=0.2, reasoning_effort=None, max_tokens=200,
            messages=[{"role": "user", "content":
                       f"Summarise this IndiaMART call between VANI (agent) and a {role} (user) in 2 short English "
                       f"sentences: what was agreed, any price/quantity/time mentioned, and what the {role} wants next. "
                       "Facts only.\n\n" + "\n".join(lines)[-4000:]}],
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:  # noqa: BLE001
        users = [l for l in lines if l.startswith("user:")]
        return (f"{role.capitalize()} said: " + users[-1][5:].strip()) if users else lines[-1]


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
        summary = _summarise_transcript(payload.get("interaction_transcript") or [], role_of(glid))
        source = "transcript_llm"
    if not summary:
        return {"ok": False, "glid": glid, "skipped": "no summary and no transcript"}
    ev = Event(channel="voice", summary=summary, time=None, meta={
        "interaction_id": payload.get("interaction_id"), "duration": payload.get("duration"),
        "connectivity": payload.get("connectivity_status"), "summary_source": source,
    }, language=oav.get("user_language") or fav.get("user_language"),
        outcome=oav.get("call_outcome") or fav.get("call_outcome"),
        callback_time=oav.get("callback_time") or fav.get("callback_time"))
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


@app.delete("/events/{glid}")
def reset_events(glid: int):
    """Demo reset: drop the live events of this GLID and rebuild the memory from the dataset only."""
    for name in ("events.jsonl", "whatsapp_thread.json"):
        f = OUT_DIR / str(glid) / name
        if f.exists():
            f.unlink()
    r = build_context(glid)
    return {"ok": True, "glid": glid, "opener": _parse_md(r["md"])["opener"]}


# ------------------------------------------------------------------ demo page (/demo): website items + WhatsApp
@app.get("/search")
def live_search(q: str, limit: int = 12):
    """Real indiamart.com search results for the emulated website panel (parsed from the mobile site's
    embedded JSON). Nothing invented: real listings, real suppliers, real prices."""
    from app.sources.im_search import search_indiamart
    if not q.strip():
        raise HTTPException(status_code=400, detail="empty query")
    try:
        return search_indiamart(q, limit=limit)
    except Exception as e:  # noqa: BLE001 — network / parse failure: the page shows a note, nothing crashes
        raise HTTPException(status_code=502, detail=f"indiamart.com search unavailable: {str(e)[:120]}") from e


# Curated demo users: the strongest buyers and sellers in the organiser dataset (scored on 10 Oct by recent
# enquiries, unread count, VANI calls, WhatsApp turns, buyer calls and buy-leads). Any other GLID in the dataset works too.
DEMO_USERS = [
    {"glid": 274238067, "role": "buyer", "name": "Aarti Singh", "city": "Gharaunda", "hint": "RCC bollards, active buy-lead, WhatsApp replies"},
    {"glid": 59681744, "role": "buyer", "name": "Ramesh", "city": "Mumbai", "hint": "paper bags & hand bells, 22 enquiries, 5 IndiaMART calls"},
    {"glid": 274154429, "role": "buyer", "name": "Shinehomz", "city": "Surat", "hint": "25 enquiries, 25 seller calls, corner protectors"},
    {"glid": 99718542, "role": "buyer", "name": "Akshay Chavan", "city": "Raigad", "hint": "scrub pads, dhoopbatti raw material, 22 enquiries"},
    {"glid": 43279328, "role": "buyer", "name": "Prem Kumar", "city": "Patna", "hint": "cotton mattresses, 2 active buy-leads"},
    {"glid": 95568576, "role": "seller", "name": "Alfa Enterprises", "city": "New Delhi", "hint": "pen drives; 66 enquiries, meeting fixed, 90 buy-leads"},
    {"glid": 253633098, "role": "seller", "name": "Govind Enterprise", "city": "Kolkata", "hint": "corrugated boxes; 33 unread, chatty on WhatsApp"},
    {"glid": 35178044, "role": "seller", "name": "DK Bean Bags", "city": "New Delhi", "hint": "bean bags; 47 unread enquiries, meeting fixed"},
    {"glid": 87677035, "role": "seller", "name": "Anuradha Oil Mill", "city": "Kanpur", "hint": "oil; memory built live on first call"},
    {"glid": 93557756, "role": "seller", "name": "Visionary Style", "city": "Surat", "hint": "hard case: called 22 times, said stop, met the executive"},
]


@app.get("/users")
def demo_users():
    return DEMO_USERS


@app.get("/lookup/{glid}")
def lookup(glid: int):
    """Cheap check used by the start page: is this GLID in the dataset, and who is it? (does not build the memory)"""
    role = role_of(glid)  # 404 if unknown
    if role == "seller":
        prof = _seller_csv("gc_seller_profile.csv")
        r = prof[prof["fk_glusr_usr_id"] == glid].iloc[0]
        return {"glid": glid, "role": role, "name": str(r["company_name"]), "city": str(r["seller_city"])}
    from app.sources.buyer import get_buyer_events
    ev = get_buyer_events(glid)
    return {"glid": glid, "role": role, "name": ev["profile"].get("name") or f"GLID {glid}", "city": ev["profile"].get("city") or ""}


@app.get("/", response_class=HTMLResponse)
def start_page():
    """Entry page: enter a GLID or pick a demo user, then open /demo#<glid>."""
    return (ROOT / "web" / "start.html").read_text()


@app.get("/home-feed")
def home_feed_route():
    """Real www.indiamart.com home sections (trending tiles, industry rows) for the emulated home page."""
    from app.sources.im_home import home_feed
    try:
        return home_feed()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"indiamart.com home unavailable: {str(e)[:120]}") from e


@app.get("/site/{glid}")
def site_items(glid: int):
    """What the emulated IndiaMART website shows this user. Buyer: the categories they searched (indiamart.com).
    Seller: the enquiries they received (seller panel / Lead Manager). All from the dataset, nothing invented."""
    _ensure_built(glid)
    ev = json.loads((OUT_DIR / str(glid) / "events.json").read_text())
    role = role_of(glid)
    prof = ev["profile"]
    if role == "buyer":
        items = [{"kind": "category", "title": c["category"], "sub": f"{c['events']} recent actions",
                  "meta": "Get quotes from verified suppliers"} for c in ev.get("top_categories", [])]
        seen = {i["title"].lower() for i in items}
        for a in ev.get("recent_activity", []):
            kw = (a.get("keyword") or "").strip()
            if kw and kw.lower() not in seen and len(items) < 8:
                seen.add(kw.lower())
                items.append({"kind": "product", "title": kw, "sub": f"{a['what']} · {a['date'][:10]}",
                              "meta": f"seller {a.get('seller_glid') or '—'}"})
        return {"glid": glid, "role": role, "name": prof.get("name"), "city": prof.get("city"),
                "site": "indiamart.com", "items": items, "buyleads": ev.get("active_buyleads", [])}
    items = [{"kind": "enquiry", "title": e["product"], "sub": f"{e.get('buyer_company') or 'Buyer'}, {e.get('buyer_city') or ''}",
              "meta": e["date"][:16], "unread": bool(e.get("unread")), "message": (e.get("message") or "")[:140]}
             for e in ev.get("enquiries", [])[:8]]
    return {"glid": glid, "role": role, "name": prof.get("company"), "city": prof.get("city"), "site": "seller.indiamart.com",
            "items": items, "products": prof.get("categories", []), "unread": ev.get("unread_enquiries", 0)}


class WhatsAppMsg(BaseModel):
    text: str
    language: str | None = None
    image: str | None = None    # product photo sent with the message (demo: WhatsApp card from the website)
    product: str | None = None  # product name, kept with the thread for display


WA_REPLY_PROMPT = """You are IndiaMART's WhatsApp assistant chatting with a {role} ({name}). You have their memory card and the
recent chat. Write the NEXT reply only.

How to reply:
- Same language and script as their last message (Hinglish in Latin letters if they wrote Hinglish). 1 or 2 short
  WhatsApp lines, under 35 words, no markdown, no lists, no greeting if the chat has already started.
- The reply is ABOUT THEIR LAST MESSAGE. First acknowledge exactly what they said or asked, repeating the key
  words (product, quantity, question). Answer a question directly. Do NOT bring up items from the memory card
  unless they relate to this message or the user asks about them.
- Then ask ONE useful next question or offer ONE concrete next step, so the conversation moves forward:
  someone who wants to buy something (even a seller writing "I want X"): quantity, delivery city, budget or specs,
  then "shall I connect you to verified sellers?";
  a seller talking about their own enquiries: which buyer to reply to, their rate or stock, "shall I send it?".
- Once quantity and city are known, do not ask for them again; confirm and offer the next step.
- If they ask when something will happen, give a concrete answer: sellers' quotes come on this chat within a few
  hours; nothing is pending on them except the details you still need. NEVER say that VANI or anyone will call
  them later, and never say "noted, we will follow up".
- If they agree to a next step ("haan", "connect karo", "bhej do"), confirm it is done in one line and say what
  comes next (e.g. "verified sellers ko bhej diya, unke quotes isi chat par aayenge"; no made-up counts). Do not ask
  again for something they already gave or declined.
- Output ONLY the message text to send, nothing else: no reasoning, no labels, no quotes.
- Never invent prices, names, dates or sellers. Address them by name at most once.
- The topic of the chat is whatever the {role} is talking about in the RECENT CHAT below (e.g. a product they want).
  Keep that topic; details like quantity or city they give belong to THAT topic, not to products in the background.

RECENT CHAT (oldest first):
{thread}
{role_upper}: {text}

BACKGROUND (memory card, only for when the chat touches it):
{card}

ASSISTANT:"""


HELP_FLAG = re.compile(r"\b(help|issue|problem|complain\w*|refund|urgent|wrong|not (?:received|working|delivered|reply\w*)|call me|call back|callback|"
                       r"madad|dikkat|samasya|shikayat|baat karni|baat karo|phone karo|call karo|galat|nahi (?:mila|aaya|aayi|pahuncha))\b", re.I)

HELP_NEGATED = re.compile(r"\b(?:koi|no|nahi|nhi|without)\s+(?:dikkat|problem|issue|samasya|help)\b|\b(?:dikkat|problem|issue|samasya)\s+(?:nahi|nhi|nai|nahin)\b", re.I)


def needs_help(text: str) -> bool:
    """WhatsApp text that asks for help / reports a problem -> VANI calls back. 'koi dikkat nahi' is not a request."""
    return bool(HELP_FLAG.search(text)) and not HELP_NEGATED.search(text)


def _wa_thread_path(glid: int) -> Path:
    return OUT_DIR / str(glid) / "whatsapp_thread.json"


def _wa_thread(glid: int) -> list[dict]:
    p = _wa_thread_path(glid)
    return json.loads(p.read_text()) if p.exists() else []


# NOTE: declared before /whatsapp/{glid}, otherwise FastAPI matches 'send' as a GLID and answers 422.
class WaSend(BaseModel):
    glid: int
    request: str = Field(..., examples=["seller contact details for the Card Pen Drive", "the quotes I asked for"])


WA_SEND_PROMPT = """Tanya (IndiaMART's voice assistant; she signs as "Tanya from IndiaMART") is on a call with a {role} named {name} and promised to send something on WhatsApp.
Tanya, the speaker, is a woman: in Hindi or Hinglish she uses FEMININE forms for herself ("main bol rahi hoon", "kar sakti hoon", "bhej deti hoon", "karungi"; Devanagari "बोल रही हूँ", "कर सकती हूँ"), never masculine ("bol raha hoon", "kar sakta hoon"). The user is addressed only with neutral polite "aap" forms; the user's gender is never guessed from the name.
What Tanya was asked to send: {request}

Data available (facts only; never invent a name, number, price or link):
PRODUCTS / SUPPLIERS the {role} is dealing with right now (newest first){live_note}:
{products}
RECENT ENQUIRIES (for a seller: buyers who enquired):
{enquiries}
MEMORY CARD:
{card}

Write ONLY a JSON object with two keys:
- "message": the WhatsApp message Tanya sends, {lang_rule}. Start with one short line saying this is what was discussed on the call,
  then the details as short lines (one fact per line, use emoji bullets sparingly: 📦 product, 💰 price, 🏢 supplier/buyer, 📍 city,
  ⭐ rating, 🔗 link). Include every relevant link given above. Under 110 words. End with one short line offering the next step.
  If the data does not contain what was asked, send what is available and say the rest will follow.
- "spoken": one sentence Tanya says on the call right after sending, in {spoken_lang}, under 18 words, confirming it is sent on WhatsApp.
"""


@app.post("/whatsapp/send")
def whatsapp_send(m: WaSend):
    """Called by the agent's run tool `send_whatsapp` mid-call: VANI composes a WhatsApp message from the user's memory
    (products viewed / called about, enquiries, links) and it lands in the WhatsApp thread + the memory as a live event."""
    glid = m.glid
    role = role_of(glid)
    ctx = get_context(glid)
    language = get_language(glid)
    # products this user touched recently (events with a product card), newest first, plus the product of the current call
    seen, products = set(), []
    active = get_active()
    cand = []
    lc = active.get("last_call") or active.get("call") or {}
    if lc.get("product"):
        cand.append(lc["product"])
    for e in reversed(list_events(glid)):
        p = (e.get("meta") or {}).get("product")
        if p:
            cand.append(p)
    for p in cand:
        k = p.get("display_id") or p.get("title")
        if k and k not in seen:
            seen.add(k); products.append(p)
        if len(products) == 4:
            break
    # The request may name a product the user only TALKED about (never clicked): then no card exists in memory.
    # Ask the LLM which product is meant; if no known card matches it, fetch real listings from indiamart.com now.
    live_note = ""
    try:
        from sarvamai import SarvamAI
        from app.sources.im_search import search_indiamart
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(model="sarvam-105b", temperature=0.0, reasoning_effort=None, max_tokens=30,
                                    messages=[{"role": "user", "content": "From this request, give ONLY the product to search on IndiaMART "
                                               "(2-5 words, English, e.g. '7.5 KVA diesel generator'), or NONE if no product is named.\n"
                                               f"Request: {m.request}\nRecent memory lines: " + " | ".join(e.get("summary", "")[:80] for e in list_events(glid)[-4:])}])
        want = (r.choices[0].message.content or "").strip().strip('"').splitlines()[0]
        words = [w for w in re.findall(r"[a-z0-9]{3,}", want.lower()) if w not in ("the", "and", "for", "with")]
        known = " ".join((p.get("title") or "").lower() for p in products)
        if want.upper() != "NONE" and words and not any(w in known for w in words):
            res = search_indiamart(want, limit=3)
            if res["items"]:
                products = res["items"][:3] + products
                live_note = f" (LIVE LISTINGS for '{want}' found on indiamart.com just now are listed FIRST; use them for this request)"
    except Exception as e:  # noqa: BLE001
        live_note = ""
    ptxt = "\n".join(
        f"- {p.get('title')} | price {p.get('price_text') or 'on request'} | supplier {p.get('company') or '-'}, {p.get('city') or '-'}"
        + (f" | rating {p.get('rating')} ({p.get('rating_count')} reviews)" if p.get("rating") else "")
        + (f" | GST verified" if p.get("gst_verified") else "") + (f" | product link {p.get('url')}" if p.get("url") else "")
        + (f" | supplier page {str(p.get('supplier_url')).split('?')[0]}" if p.get("supplier_url") else "") for p in products) or "- (none)"
    ev = json.loads((OUT_DIR / str(glid) / "events.json").read_text())
    enq = "\n".join(f"- {e.get('date')}: {e.get('product')} from {e.get('buyer_company') or 'a buyer'}, {e.get('buyer_city') or ''}"
                     + (f' | "{e.get("message")}"' if e.get("message") else "") for e in (ev.get("enquiries") or [])[:5]) or "- (none)"
    lang_rule = ("in Hinglish written in Roman letters (the way Indian business people type on WhatsApp)" if language == "Hindi"
                 else f"in simple {language}")
    spoken_lang = ("Hindi in Devanagari script with product names in English letters" if language == "Hindi" else language)
    message, spoken = "", ""
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        r = client.chat.completions(model="sarvam-105b", temperature=0.2, reasoning_effort=None, max_tokens=500,
                                    messages=[{"role": "user", "content": WA_SEND_PROMPT.format(
                                        role=role, name=ctx["name"], request=m.request, products=ptxt, enquiries=enq,
                                        card=ctx["call_card"], lang_rule=lang_rule, spoken_lang=spoken_lang, live_note=live_note)}])
        text = (r.choices[0].message.content or "").strip()
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        message, spoken = (data.get("message") or "").strip(), (data.get("spoken") or "").strip()
    except Exception as e:  # noqa: BLE001
        message = ""
    if not message:  # deterministic fallback from the first product
        p = products[0] if products else None
        message = (f"Namaste {ctx['name']}, call par jo baat hui uski details:\n📦 {p.get('title')}\n💰 {p.get('price_text') or 'price on request'}\n"
                   f"🏢 {p.get('company') or '-'}, {p.get('city') or ''}" + (f"\n🔗 {p.get('url')}" if p.get("url") else "") + "\nKoi aur help chahiye to yahin reply karein."
                   if p else f"Namaste {ctx['name']}, call par jo baat hui, uski details hum jald hi yahin bhej denge.")
        spoken = spoken or ("मैंने details WhatsApp पर भेज दी हैं, देख लीजिए।" if language == "Hindi" else "I have sent the details on WhatsApp.")
    image = products[0].get("image") if products and products[0].get("image") else None
    turn = {"from": "bot", "text": message, "via": "call", "time": datetime.now().strftime("%Y-%m-%d %H:%M")} | ({"image": image, "product": products[0].get("title")} if image else {})
    thread = _wa_thread(glid) + [turn]
    _wa_thread_path(glid).parent.mkdir(parents=True, exist_ok=True)
    _wa_thread_path(glid).write_text(json.dumps(thread[-20:], ensure_ascii=False))
    first = message.splitlines()[0][:120]
    r = post_event(glid, Event(channel="whatsapp", summary=f"VANI sent on WhatsApp during the call: {first}", meta={"kind": "vani_whatsapp", "request": m.request}))
    return {"ok": True, "glid": glid, "sent": True, "message": message, "spoken": spoken, "image": image,
            "freshness_seconds": r.get("freshness_seconds")}


@app.post("/whatsapp/{glid}")
def whatsapp_message(glid: int, m: WhatsAppMsg):
    """Emulated WhatsApp: the user's message becomes a live event (memory rebuilt), then the bot answers from the fresh
    memory and the recent chat thread. Returns the reply, the new opener/greeting and freshness seconds."""
    role = role_of(glid)
    who = "Buyer" if role == "buyer" else "Seller"
    text = m.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty message")
    r = post_event(glid, Event(channel="whatsapp", summary=f"{who} wrote on WhatsApp: {text}", language=m.language))
    ctx = get_context(glid)
    thread = _wa_thread(glid)[-8:]
    thread_txt = "\n".join(f"{who.upper() if t['from'] == 'user' else 'ASSISTANT'}: {t['text']}" for t in thread) or "(start of chat)"
    # The memory card is shown to the bot on the first message, and later only when the message touches it
    # (enquiries, buyers, rates, or a product named in the card); otherwise the model kept pitching old enquiries.
    card = ctx["call_card"]
    card_words = {w for w in re.findall(r"[a-z]{5,}", card.lower())}
    msg_words = set(re.findall(r"[a-z]{5,}", text.lower()))
    touches = bool(re.search(r"enquir|buyer|lead|rate|quote|memory|pehle|earlier|last time|yaad", text, re.I)) or bool(card_words & msg_words - {"indiamart", "whatsapp", "chahiye", "please"})
    if not touches:  # only who they are; the model otherwise pitches old enquiries instead of answering
        card = card.splitlines()[0] + "\n(rest of the memory not needed for this message; stay on the chat topic)"
    reply = ""
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
        c = client.chat.completions(model="sarvam-105b", temperature=0.2, reasoning_effort=None, max_tokens=140,
                                    messages=[{"role": "user", "content": WA_REPLY_PROMPT.format(
                                        role=role, role_upper=who.upper(), name=ctx["name"], text=text, card=card, thread=thread_txt)}])
        reply = (c.choices[0].message.content or "").strip()
        paras = [p.strip() for p in re.split(r"\n\s*\n", reply) if p.strip()]
        reply = paras[-1] if paras else reply  # the model sometimes thinks aloud first; the message is the last paragraph
        reply = re.sub(r"^(ASSISTANT|Assistant|Reply)\s*:\s*", "", reply).strip().strip('"“”')
    except Exception as e:  # noqa: BLE001
        print("whatsapp reply LLM failed:", e)
    if not reply:
        reply = ("Samajh gaya. Aapko kitni quantity chahiye aur kis city mein delivery?" if role == "buyer"
                 else "Samajh gaya. Kis buyer ko reply bhejna hai, aur aapka rate kya rahega?")
    user_turn = {"from": "user", "text": text} | ({"image": m.image, "product": m.product} if m.image else {})
    thread = _wa_thread(glid) + [user_turn, {"from": "bot", "text": reply}]
    _wa_thread_path(glid).parent.mkdir(parents=True, exist_ok=True)
    _wa_thread_path(glid).write_text(json.dumps(thread[-20:], ensure_ascii=False))
    needs_call = needs_help(text)
    return {"ok": True, "glid": glid, "reply": reply, "needs_call": needs_call, "freshness_seconds": r["freshness_seconds"],
            "opener": ctx["opener"], "greeting": ctx["greeting"], "event": r["event"]}


@app.get("/whatsapp/{glid}")
def whatsapp_thread(glid: int):
    """The emulated WhatsApp chat so far (user + bot turns), for re-rendering the phone."""
    return _wa_thread(glid)


class CallRequest(BaseModel):
    glid: int
    phone: str


@app.post("/call")
def call_me(req: CallRequest):
    """Ask Sarvam to place an outbound call to `phone` with this GLID's memory (Instant Outbound API).
    Needs a Sarvam phone number (connection) + API key — set SARVAM_AGENT_API_KEY, SARVAM_CONNECTION_ID,
    SARVAM_AGENT_NUMBER in .env once the workspace has a number (event day). Until then returns 503."""
    key, conn, agent_no = os.getenv("SARVAM_AGENT_API_KEY"), os.getenv("SARVAM_CONNECTION_ID"), os.getenv("SARVAM_AGENT_NUMBER")
    app_id = (os.getenv("SARVAM_APP_ID_SELLER", "VANI-IndiaM-61f2af95-c5b7") if role_of(req.glid) == "seller"
              else os.getenv("SARVAM_APP_ID", "VANI-IndiaM-b67b20da-8a1b"))  # one agent per role
    if not (key and conn and agent_no):
        raise HTTPException(status_code=503, detail="Outbound not configured yet: workspace has no Sarvam phone number. "
                            "Set SARVAM_AGENT_API_KEY / SARVAM_CONNECTION_ID / SARVAM_AGENT_NUMBER in .env.")
    import httpx
    body = {
        "app_config": {"app_id": app_id, "app_version": int(os.getenv("SARVAM_APP_VERSION", "10")),  # latest committed
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
    lang_changed = set_language(glid, ev.language)
    skip = None
    if not ev.summary.strip():  # e.g. on_end fired before the call summary was extracted
        skip = "empty summary"
    elif (ev.outcome or "").strip() in SKIP_OUTCOMES:  # call dropped / wrong person: nothing worth remembering
        skip = f"outcome {ev.outcome}"
    d = OUT_DIR / str(glid)
    if not skip and ev.channel == "web":  # same website line twice (page reload / redirect) within 10 min = one action
        f = d / "events.jsonl"
        last = [json.loads(l) for l in f.read_text().splitlines()[-3:] if l.strip()] if f.exists() else []
        for prev in last:
            if prev.get("summary") == ev.summary.strip():
                try:
                    age = (datetime.now() - datetime.strptime(prev.get("time", ""), "%Y-%m-%d %H:%M")).total_seconds()
                except ValueError:
                    age = 0
                if age < 600:
                    skip = "duplicate web event"
    if skip:
        if lang_changed:  # still regenerate, so the next greeting is in the new language
            build_context(glid)
        return {"ok": False, "glid": glid, "skipped": skip, "language_saved": lang_changed,
                "freshness_seconds": round(time.perf_counter() - t0, 2)}
    d = OUT_DIR / str(glid)
    d.mkdir(parents=True, exist_ok=True)
    rec = ev.model_dump(exclude_none=True)
    rec["time"] = rec.get("time") or datetime.now().strftime("%Y-%m-%d %H:%M")
    if ev.callback_time and ev.callback_time.strip():  # make the agreed callback explicit in the memory line
        rec["summary"] = rec["summary"].rstrip(". ") + f". Callback agreed: {ev.callback_time.strip()}."
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


# ------------------------------------------------------------------ demo web pages (mount must be last: catches "/")
@app.get("/demo")
def demo_page():
    """Simplified showroom demo: phone (WhatsApp + VANI call) · desktop (IndiaMART website) · live memory file."""
    from fastapi.responses import FileResponse
    return FileResponse(str(ROOT / "web" / "demo.html"))


@app.get("/config.js")
def config_js():
    """Widget config for the demo pages, built from .env (no key lives in the repo any more).
    Needs SARVAM_EMBED_KEY (embed-scoped, NOT the server key); the ids have the two VANI agents as defaults."""
    cfg = {
        "apiKey": os.getenv("SARVAM_EMBED_KEY", ""),
        "orgId": os.getenv("SARVAM_ORG_ID", "01a11128-bd2a-794c-a92a-5f518eacaba5"),
        "workspaceId": os.getenv("SARVAM_WORKSPACE_ID", "01a11128-bd2f-7b40-9f2d-a2a3b2edf5d7"),
        "appId": os.getenv("SARVAM_APP_ID", "VANI-IndiaM-b67b20da-8a1b"),            # buyer agent
        "appIdSeller": os.getenv("SARVAM_APP_ID_SELLER", "VANI-IndiaM-61f2af95-c5b7"),  # seller agent
    }
    body = "window.SARVAM_EMBED = " + json.dumps(cfg) + ";\n"
    from fastapi.responses import Response
    return Response(body, media_type="application/javascript", headers={"Cache-Control": "no-store"})


app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="web")
