// Service worker: receives captured actions from the content script and posts them to the VANI Context API.
// The extension has host permission for localhost:8000, so this fetch is not blocked by CORS.
const API = "http://localhost:8000";

async function activeGlid() {
  try {
    const r = await fetch(`${API}/active`);
    const d = await r.json();
    return d.glid || null;
  } catch (e) {
    return null;
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.type !== "vani_event") return;
  (async () => {
    const glid = msg.glid || (await activeGlid());
    if (!glid) { sendResponse({ ok: false, error: "no active GLID — open the demo page and pick a user" }); return; }
    try {
      const r = await fetch(`${API}/events/${glid}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: "web", summary: msg.summary, meta: { url: msg.url || "", source: "chrome-extension" } }),
      });
      const d = await r.json();
      sendResponse({ ok: !!d.ok, glid, freshness_seconds: d.freshness_seconds, opener: d.opener, detail: d.detail || d.skipped });
    } catch (e) {
      sendResponse({ ok: false, error: String(e) });
    }
  })();
  return true; // keep the channel open for the async response
});
