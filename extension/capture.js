// Content script: runs on every *.indiamart.com page (tab or iframe). Watches what the user does and sends one
// short English line per action to the VANI Context API through the service worker. Nothing is invented: every
// line is built from what is on the page (query, product title, supplier, button label).
(() => {
  if (window.__vaniCapture) return;
  window.__vaniCapture = true;

  const host = location.hostname;
  const isSeller = host.startsWith("seller.") || host.startsWith("my.");
  const who = isSeller ? "Seller" : "Buyer";
  const site = isSeller ? "seller.indiamart.com" : "indiamart.com";
  const clean = s => (s || "").replace(/\s+/g, " ").trim();
  // a real search query: 2+ chars, not a web address / hostname / email
  const isQuery = q => { q = clean(q); return q.length >= 2 && q.length <= 80 && !/^https?:|^www\.|\.[a-z]{2,4}(\/|$)|@/i.test(q); };
  const short = (s, n = 70) => { s = clean(s); return s.length > n ? s.slice(0, n - 1) + "…" : s; };

  // ---------- on-page badge so the audience sees the capture ----------
  const badge = document.createElement("div");
  badge.style.cssText = "position:fixed;z-index:2147483647;right:14px;bottom:14px;max-width:360px;background:#111214;color:#fff;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;padding:10px 14px;border-radius:999px;box-shadow:0 10px 30px rgba(0,0,0,.3);opacity:0;transition:opacity .25s;pointer-events:none";
  (document.body || document.documentElement).appendChild(badge);
  let badgeT = null;
  function show(text) { badge.textContent = text; badge.style.opacity = "1"; clearTimeout(badgeT); badgeT = setTimeout(() => (badge.style.opacity = "0"), 2600); }

  // ---------- send ----------
  const sent = new Set();
  function send(summary) {
    summary = clean(summary);
    if (!summary || sent.has(summary)) return;
    sent.add(summary);
    show("🧠 VANI noted: " + short(summary, 90));
    try {
      chrome.runtime.sendMessage({ type: "vani_event", summary, url: location.href }, resp => {
        if (chrome.runtime.lastError) return;
        if (resp && resp.ok) show(`🧠 memory updated in ${resp.freshness_seconds}s`);
        else if (resp && (resp.error || resp.detail)) show("⚠ " + (resp.error || resp.detail));
      });
    } catch (e) { /* extension reloaded; ignore */ }
    try { window.parent !== window && window.parent.postMessage({ vani: "event", summary }, "*"); } catch (e) {}
  }
  // tell the demo page (if we are inside its frame) where the user is
  try { window.parent !== window && window.parent.postMessage({ vani: "url", href: location.href, title: document.title }, "*"); } catch (e) {}

  // ---------- what page is this ----------
  const params = new URLSearchParams(location.search);
  const query = params.get("ss") || params.get("q") || params.get("search") || params.get("keyword");
  if (query && isQuery(query)) send(`${who} searched "${short(query, 50)}" on ${site}`);

  const h1 = () => short(document.querySelector("h1") && document.querySelector("h1").textContent, 80);
  function supplierOnPage() {
    const el = document.querySelector('[class*="company" i] a, [class*="cmpny" i], [class*="supplier" i] a, a[href*="/company/"], [itemprop="name"]');
    return el ? short(el.textContent, 50) : "";
  }
  function priceOnPage() {
    const el = [...document.querySelectorAll('[class*="price" i]')].find(e => /₹|Rs/.test(e.textContent));
    const m = el && el.textContent.match(/(₹|Rs\.?)\s?[\d,]+(\s?\/\s?\w+)?/);
    return m ? clean(m[0]) : "";
  }
  if (/\/proddetail\//.test(location.pathname) && h1()) {
    const bits = [h1(), supplierOnPage() && "by " + supplierOnPage(), priceOnPage()].filter(Boolean);
    setTimeout(() => send(`${who} opened the product page ${bits.join(", ")} on ${site}`), 800);
  }
  if (isSeller && /lead|enquir|inbox|message/i.test(location.pathname + location.search)) {
    setTimeout(() => send(`Seller opened Lead Manager on ${site}`), 800);
  }

  // ---------- clicks on the buttons that matter ----------
  const ACTIONS = /get (latest|best) price|contact supplier|call supplier|call now|view mobile|send enquiry|get quote|request callback|add to shortlist|shortlist|reply|call buyer|send reply|buy now|get price/i;
  function titleNear(el) {
    let n = el;
    for (let i = 0; i < 8 && n && n !== document.body; i++, n = n.parentElement) {
      const t = n.querySelector && n.querySelector('h1, h2, h3, [class*="title" i], [class*="prd-name" i], a[href*="/proddetail/"]');
      const txt = t && clean(t.textContent);
      if (txt && txt.length > 6) return short(txt, 70);
    }
    return h1() || short(document.title, 60);
  }
  document.addEventListener("click", e => {
    const el = e.target.closest("button, a, [role=button], input[type=submit], span, div");
    if (!el) return;
    const label = clean(el.innerText || el.value || el.getAttribute("aria-label") || "");
    if (!label || label.length > 40 || !ACTIONS.test(label)) return;
    const t = titleNear(el);
    send(`${who} clicked "${label}" for ${t} on ${site}`);
  }, true);

  // search box submits (home page / header search)
  document.addEventListener("submit", e => {
    const inp = e.target.querySelector && e.target.querySelector('input[type="search"], input[name="ss"], input[placeholder*="Search" i], input[type="text"]');
    const q = inp && clean(inp.value);
    if (q && isQuery(q)) send(`${who} searched "${short(q, 50)}" on ${site}`);
  }, true);
  document.addEventListener("keydown", e => {
    if (e.key !== "Enter") return;
    const inp = e.target;
    if (!(inp instanceof HTMLInputElement)) return;
    if (/search/i.test(inp.placeholder + " " + inp.name + " " + inp.id + " " + inp.className) && isQuery(inp.value)) send(`${who} searched "${short(inp.value, 50)}" on ${site}`);
  }, true);

  // ---------- dwell: product cards that stay in view ~1 s count as browsed, batched into one line ----------
  let queue = [], flush = null;
  const seen = new WeakSet();
  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      const el = en.target;
      if (en.isIntersecting && !seen.has(el)) {
        el.__t = setTimeout(() => {
          seen.add(el); const t = short(el.__title, 50);
          if (t && !queue.includes(t)) { queue.push(t); show("👁 " + t); clearTimeout(flush); flush = setTimeout(() => { const list = queue.splice(0, 6); queue = []; send(`${who} browsed on ${site}: ${list.join(", ")}`); }, 4000); }
        }, 1000);
      } else clearTimeout(el.__t);
    });
  }, { threshold: 0.6 });
  function observeCards() {
    document.querySelectorAll('a[href*="/proddetail/"]').forEach(a => {
      const card = a.closest('li, [class*="card" i], [class*="lst" i], [class*="prd" i], article, div') || a;
      if (card.__obs) return;
      const title = clean(a.getAttribute("title") || a.textContent);
      if (title.length < 8 || card.getBoundingClientRect().height < 80) return;
      card.__obs = true; card.__title = title; io.observe(card);
    });
  }
  observeCards();
  new MutationObserver(() => { clearTimeout(window.__vaniMo); window.__vaniMo = setTimeout(observeCards, 500); }).observe(document.documentElement, { childList: true, subtree: true });
})();
