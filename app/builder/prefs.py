"""Per-user preferences that outlive a single call. Today: the language the user spoke last.

Stored in context_files/<glid>/prefs.json. Language names are Sarvam's (Hindi, English, Gujarati, ...),
so the agent can switch to them directly. Hinglish counts as Hindi (the Hindi voice speaks code-mixed).
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from app.sources.seller import ROOT

OUT_DIR = ROOT / "context_files"

LANGUAGES = ["Hindi", "English", "Bengali", "Gujarati", "Kannada", "Malayalam", "Marathi", "Odia", "Punjabi",
             "Tamil", "Telugu", "Assamese"]
DEFAULT_LANGUAGE = "Hindi"


def _path(glid: int):
    return OUT_DIR / str(glid) / "prefs.json"


def get_prefs(glid: int) -> dict:
    p = _path(glid)
    return json.loads(p.read_text()) if p.exists() else {}


def get_language(glid: int) -> str:
    return get_prefs(glid).get("language") or DEFAULT_LANGUAGE


def normalise_language(lang: str | None) -> str | None:
    """'hinglish' / 'hi-IN' / 'english ' -> Sarvam language name, or None if unknown/empty."""
    if not lang:
        return None
    s = str(lang).strip().lower()
    if s.startswith("hinglish") or s in ("hi", "hi-in"):
        return "Hindi"
    if s in ("en", "en-in"):
        return "English"
    for name in LANGUAGES:
        if s == name.lower():
            return name
    return None


def set_language(glid: int, lang: str | None) -> bool:
    """Save the user's last language. Returns True if it changed."""
    lang = normalise_language(lang)
    if not lang:
        return False
    prefs = get_prefs(glid)
    if prefs.get("language") == lang:
        return False
    prefs.update(language=lang, language_updated=datetime.now().isoformat(timespec="seconds"))
    _path(glid).parent.mkdir(parents=True, exist_ok=True)
    _path(glid).write_text(json.dumps(prefs, ensure_ascii=False))
    return True


GREETING_RULE = """- "greeting": the very first line VANI speaks, before anything else, written in {language}{script}.
  Under 18 words. It greets the user by name ({name_hint}, exactly as given, no "ji" added), asks how they are, and names the latest topic in a
  few words (e.g. the product or requirement). The latest topic is the subject of the FIRST item of
  "live_events_newest_first" when that list is non-empty (what the user just searched, opened, wrote or said);
  only when it is empty, use the newest requirement from the history. No prices, numbers, dates or account details.
  Ends with a question. Tanya, the speaker, is a woman: in Hindi or Hinglish she uses FEMININE forms for herself ('main bol rahi hoon', 'kar sakti hoon', 'bhej deti hoon', 'karungi'; Devanagari 'बोल रही हूँ', 'कर सकती हूँ'), never masculine ('bol raha hoon', 'kar sakta hoon'). The user is addressed only with neutral polite 'aap' forms; the user's gender is never guessed from the name."""


WEAK_EVENT = re.compile(r"(opened (the )?Lead Manager|opened the IndiaMART|called the IndiaMART helpline\s*(\(VANI\))?$|"
                        r"VANI called .* no answer|picked up$|opened the website|went to the home ?page)", re.I)


def latest_topic(live_events: list[dict]) -> str | None:
    """Newest live event whose summary carries a real topic (a product, enquiry, message). Clicks like
    'Seller opened Lead Manager' are skipped so the greeting does not say 'Lead Manager par baat karni thi' (10 Oct)."""
    for e in reversed(live_events or []):
        summ = (e.get("summary") or "").strip()
        if summ and not WEAK_EVENT.search(summ):
            return summ
    return None


def greeting_rule(language: str, name_hint: str, role: str = "buyer", latest: str | None = None) -> str:
    """`latest` = the newest live event line, if any; it is spelled out so the greeting names THAT topic."""
    example = ("नमस्ते Alfa Enterprises, आप कैसे हैं? आपको HP Pen Drive की enquiry आई थी, उसी के बारे में बात करनी थी, अभी समय है?"
               if role == "seller" else
               "नमस्ते Aarti, आप कैसे हैं? आपके RCC bollards के quotes के बारे में बात करनी थी, अभी समय है?")
    script = {
        "Hindi": (" (IMPORTANT: Devanagari script, NOT Roman, unlike the opener; product and brand names stay in English"
                  f" letters. Example: {example} Always the neutral आप कैसे हैं, never कैसी.)"),
        "English": " (simple Indian English)",
    }.get(language, f" ({language} script)")
    rule = GREETING_RULE.format(language=language, script=script, name_hint=name_hint)
    if latest:
        rule += f'\n  LATEST TOPIC FOR THE GREETING (the newest thing the user did, on another channel): "{latest[:160]}". The greeting names this topic, not an older one.'
    return rule


FEM_FIXES = [("बोल रहा हूँ", "बोल रही हूँ"), ("रहा हूँ", "रही हूँ"), ("सकता हूँ", "सकती हूँ"), ("करूँगा", "करूँगी"), ("करूंगा", "करूंगी"),
             ("देता हूँ", "देती हूँ"), ("चाहता हूँ", "चाहती हूँ"), ("bol raha hoon", "bol rahi hoon"), ("raha hoon", "rahi hoon"),
             ("sakta hoon", "sakti hoon"), ("karunga", "karungi"), ("deta hoon", "deti hoon"), ("chahta hoon", "chahti hoon")]


def feminine(text: str) -> str:
    """Tanya is a woman: any masculine first-person form the LLM slipped in is corrected (user rule, 10 Oct)."""
    for a, b in FEM_FIXES:
        text = text.replace(a, b)
    return text


def clean_greeting(greeting: str, name: str) -> str:
    """Code-level guard for the LLM greeting (seen in analytics: 'नमस्ते आरती ji, आप कैसी हैं?'):
    neutral 'कैसे हैं', no 'ji'/'जी' glued to the name, no double spaces."""
    g = (greeting or "").strip()
    g = g.replace("कैसी हैं", "कैसे हैं").replace("कैसी हो", "कैसे हैं")
    g = re.sub(r"\s+(ji|जी)\s*([,!?.])", r"\2", g)  # "आरती ji," -> "आरती,"
    g = re.sub(r"\s+(ji|जी)\s+", " ", g)
    return feminine(re.sub(r"\s{2,}", " ", g))


def fallback_greeting(name: str, language: str) -> str:
    if language == "English":
        return f"Hello {name}, how are you?"
    return f"नमस्ते {name}, आप कैसे हैं?"


def date_rule() -> str:
    """Tells the insight LLM what 'today' is, so past meetings/callbacks are not offered again as if upcoming."""
    today = datetime.now().strftime("%d %B %Y")
    return (f"- Today is {today}. Any meeting, callback, delivery or date mentioned in the data or the live events that falls\n"
            "  before today is in the PAST: it already happened or was missed. Never offer to fix, confirm or schedule it\n"
            "  again, and never present it as upcoming. The opener does NOT mention a past meeting or callback at all;\n"
            "  it is built on the freshest open item instead (unread enquiries, a new requirement, a recent quote). The\n"
            "  story may say the past meeting happened or was missed, in one short clause.")


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]


def stale_month(text: str) -> str | None:
    """A month name in `text` that is already over this year (e.g. 'August' in October), else None.
    Used to catch openers that bring up an old meeting or callback."""
    low = (text or "").lower()
    now = datetime.now().month
    for i, m in enumerate(_MONTHS, start=1):
        if i < now and (m in low or m[:3] + " " in low):
            return m.capitalize()
    return None


def stale_feedback(month: str) -> str:
    return (f"\n\nCORRECTION: your previous opener mentioned {month}, which is already over. Write the JSON again. "
            f"The opener must not mention {month} or any past meeting or callback; build it on the freshest open item.")
