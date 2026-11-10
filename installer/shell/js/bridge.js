// RTR-RE installer — bridge client.
// The shell loads from file:// (no http:// in the address bar). The
// launcher runs a loopback API (127.0.0.1, random port, token, CORS)
// that only the hidden bridge calls use. If no launcher is present
// (plain file:// preview), the bridge falls back to demo mode.

const Bridge = (() => {
  let base = null
  let token = null
  let demo = false

  function init() {
    const q = new URLSearchParams(location.search)
    const b = q.get("bridge")
    if (b) {
      base = b.replace(/\/$/, "")
      token = q.get("token") || ""
      demo = false
    } else {
      demo = true
    }
  }

  async function request(path, body) {
    if (demo) return demoResponse(path, body)
    try {
      const res = await fetch(base + path, {
        method: body ? "POST" : "GET",
        headers: {
          "Content-Type": "application/json",
          "X-RTR-Token": token,
        },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!res.ok) throw new Error(`bridge ${path} -> ${res.status}`)
      return res.json()
    } catch (e) {
      // fall back to demo so the UI never hangs
      return demoResponse(path, body)
    }
  }

  function demoResponse(path, body) {
    if (path === "/api/plan") {
      const preset = body?.preset || "quick"
      const steps = {
        quick: [
          ["preset", "re-symbiose-mugen (400k/200k/200)"],
          ["engine", "rtr-full · dual-ONNX"],
          ["profile", "local-system · T8/P80"],
          ["plugin", "keeper + ctrl+p palette"],
          ["memory", ".opencode/memory/ (DTD-shaped)"],
        ],
        custom: [
          ["components", (body?.components || []).join(", ")],
          ["engine", "rtr-full · dual-ONNX"],
          ["profile", "local-system · T8/P80"],
          ["plugin", "keeper + ctrl+p palette"],
          ["memory", ".opencode/memory/ (DTD-shaped)"],
        ],
        hardcore: [
          ["preset", body?.presetName || "re-symbiose-mugen"],
          ["threads", String(body?.threads ?? 8)],
          ["parking", String(body?.parking ?? 40) + "%"],
          ["modality", body?.modality || "rtr-full"],
          ["engine", "rtr-full · dual-ONNX"],
          ["plugin", "keeper + ctrl+p palette"],
          ["memory", ".opencode/memory/ (DTD-shaped)"],
        ],
      }[preset] || []
      return { steps }
    }
    if (path === "/api/execute") {
      return { ok: true, demo: true }
    }
    if (path === "/api/status") {
      return { ok: true, demo: true, theme: currentTheme().id }
    }
    if (path === "/api/easter-egg") {
      return { ok: true, demo: true }
    }
    return { ok: true }
  }

  return {
    init,
    plan: (payload) => request("/api/plan", payload),
    execute: (payload) => request("/api/execute", payload),
    status: () => request("/api/status"),
    easterEgg: () => request("/api/easter-egg"),
    isDemo: () => demo,
  }
})()
