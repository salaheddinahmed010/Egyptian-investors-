// Vercel Serverless Function: POST /api/ai   (GET /api/ai = health check)
// Env vars (Vercel > Settings > Environment Variables): GROQ_API_KEY, GEMINI_API_KEY
const GROQ_SEARCH = ["groq/compound", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"];
const GROQ_PLAIN = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"];
const GEM_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"];
const hits = new Map();

const clean = (t) => String(t || "").replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
const scrub = (s) => String(s).replace(/(AIza|AQ\.|gsk_)[\w.\-]+/g, "[key]").slice(0, 220);

async function tf(url, opts, ms) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  try { return await fetch(url, { ...opts, signal: c.signal }); }
  finally { clearTimeout(t); }
}

async function groq(key, model, sys, msgs, tokens) {
  const b = { model, temperature: 0.3, max_tokens: tokens, messages: [{ role: "system", content: sys }, ...msgs] };
  if (/gpt-oss/.test(model)) b.reasoning_effort = "low";
  const r = await tf("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + key },
    body: JSON.stringify(b),
  }, 25000);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`groq/${model} [${r.status}] ${(j.error && j.error.message) || ""}`);
  const t = clean(j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content);
  if (!t) throw new Error(`groq/${model} [empty]`);
  return t;
}

async function gem(key, model, sys, msgs, tokens, search) {
  const vertex = key.startsWith("AQ."); // Vertex AI express-mode key
  const url = vertex
    ? `https://aiplatform.googleapis.com/v1/publishers/google/models/${model}:generateContent?key=${encodeURIComponent(key)}`
    : `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
  const headers = { "Content-Type": "application/json" };
  if (!vertex) headers["x-goog-api-key"] = key;
  const body = {
    systemInstruction: { parts: [{ text: sys }] },
    contents: msgs.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })),
    generationConfig: { temperature: 0.3, maxOutputTokens: tokens },
  };
  if (search) body.tools = [{ google_search: {} }];
  const r = await tf(url, { method: "POST", headers, body: JSON.stringify(body) }, search ? 25000 : 20000);
  const j = await r.json().catch(() => ({}));
  const tag = `gemini/${model}${search ? "+search" : ""}`;
  if (!r.ok) throw new Error(`${tag} [${r.status}] ${(j.error && j.error.message) || ""}`);
  const ps = (j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts) || [];
  const t = clean(ps.map((p) => p.text || "").join(""));
  if (!t) throw new Error(`${tag} [empty]`);
  return t;
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const GROQ = process.env.GROQ_API_KEY || "";
  const GEM = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || "";

  if (req.method === "GET") return res.status(200).json({ ok: true, groq: !!GROQ, gemini: !!GEM });
  if (req.method !== "POST") return res.status(405).json({ error: "method not allowed" });

  // only our own site may use this endpoint
  const origin = String(req.headers.origin || req.headers.referer || "");
  const extra = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const okOrigin = !origin || /egyptianinvestorstelegram|localhost|127\.0\.0\.1/.test(origin) || extra.some((x) => origin.includes(x));
  if (!okOrigin) return res.status(403).json({ error: "forbidden origin" });

  // light per-IP rate limit (best effort, per instance)
  const ip = String(req.headers["x-forwarded-for"] || "ip").split(",")[0].trim();
  const now = Date.now();
  const arr = (hits.get(ip) || []).filter((t) => now - t < 60000);
  if (arr.length >= 20) return res.status(429).json({ error: "too many requests" });
  arr.push(now); hits.set(ip, arr);

  let b = req.body;
  if (typeof b === "string") { try { b = JSON.parse(b); } catch (e) { b = null; } }
  if (!b) return res.status(400).json({ error: "bad body" });

  const sys = String(b.sys || "").slice(0, 12000);
  const msgs = (Array.isArray(b.messages) ? b.messages : []).slice(-12)
    .map((m) => ({ role: m.role === "assistant" ? "assistant" : "user", content: String(m.content || "").slice(0, 6000) }))
    .filter((m) => m.content);
  if (!sys || !msgs.length || msgs[msgs.length - 1].role !== "user") return res.status(400).json({ error: "bad input" });
  const tokens = Math.min(Math.max(parseInt(b.tokens, 10) || 2000, 200), 8000);
  const nosearch = !!b.nosearch;

  if (!GROQ && !GEM) return res.status(500).json({ error: "no API keys configured on server", diag: ["Add GROQ_API_KEY / GEMINI_API_KEY in Vercel env vars, then redeploy"] });

  const order = b.prefer === "gemini" ? ["gemini", "groq"] : ["groq", "gemini"];
  const diag = [];
  const t0 = Date.now();

  for (const p of order) {
    if (p === "groq" && GROQ) {
      for (const m of nosearch ? GROQ_PLAIN : GROQ_SEARCH) {
        if (Date.now() - t0 > 52000) break;
        try { return res.status(200).json({ text: await groq(GROQ, m, sys, msgs, tokens), provider: "groq", model: m }); }
        catch (e) { diag.push(scrub(e.message)); }
      }
    }
    if (p === "gemini" && GEM) {
      for (const m of GEM_MODELS) {
        if (Date.now() - t0 > 52000) break;
        for (const s of nosearch ? [false] : [true, false]) {
          try { return res.status(200).json({ text: await gem(GEM, m, sys, msgs, tokens, s), provider: "gemini", model: m }); }
          catch (e) { diag.push(scrub(e.name === "AbortError" ? `gemini/${m} [timeout]` : e.message)); }
        }
      }
    }
  }
  return res.status(502).json({ error: "all providers failed", diag });
};
