"""Per-user preferences that outlive a single call. Today: the language the user spoke last.

Stored in context_files/<glid>/prefs.json. Language names are Sarvam's (Hindi, English, Gujarati, ...),
so the agent can switch to them directly. Hinglish counts as Hindi (the Hindi voice speaks code-mixed).
"""
from __future__ import annotations

import json
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
  few words (e.g. the product or requirement). No prices, numbers, dates or account details. Ends with a question."""


def greeting_rule(language: str, name_hint: str) -> str:
    script = {
        "Hindi": (" (IMPORTANT: Devanagari script, NOT Roman, unlike the opener; product and brand names stay in English"
                  " letters. Example: नमस्ते Aarti, आप कैसे हैं? आपके RCC bollards के quotes के बारे में बात करनी थी, अभी समय है? Always the neutral आप कैसे हैं, never कैसी.)"),
        "English": " (simple Indian English)",
    }.get(language, f" ({language} script)")
    return GREETING_RULE.format(language=language, script=script, name_hint=name_hint)


def fallback_greeting(name: str, language: str) -> str:
    if language == "English":
        return f"Hello {name}, how are you?"
    return f"नमस्ते {name}, आप कैसे हैं?"
