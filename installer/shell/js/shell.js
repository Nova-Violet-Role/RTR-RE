// RTR-RE installer — shell controller.
// Wires the screens, presets, bridge, audio, and scene together.

(() => {
  const $ = (sel) => document.querySelector(sel)
  const $$ = (sel) => [...document.querySelectorAll(sel)]

  let currentPreset = "quick"
  let selectedComponents = new Set()
  let plan = null

  // ---------- boot ----------
  function boot() {
    Bridge.init()
    Scene.init()

    const theme = currentTheme()
    $("#themeBadge").textContent = theme.label + " · " + theme.platform

    buildComponents()
    wireEvents()
    Audio.play("quick")
  }

  // ---------- screens ----------
  function show(id) {
    $$(".screen").forEach((s) => s.classList.remove("active"))
    $("#" + id).classList.add("active")
  }

  // ---------- components grid ----------
  function buildComponents() {
    const grid = $("#componentGrid")
    grid.innerHTML = ""
    for (const c of COMPONENTS) {
      const el = document.createElement("component")
      el.className = "component" + (c.required ? " selected" : "")
      el.dataset.id = c.id
      el.innerHTML =
        `<span class="dot"></span>` +
        `<div><div class="c-name">${c.name}${c.required ? " ·" : ""}</div>` +
        `<div class="c-desc">${c.desc}</div></div>`
      if (c.required) selectedComponents.add(c.id)
      el.addEventListener("click", () => toggleComponent(el, c))
      grid.appendChild(el)
    }
  }

  function toggleComponent(el, c) {
    if (c.required) return
    if (selectedComponents.has(c.id)) {
      selectedComponents.delete(c.id)
      el.classList.remove("selected")
    } else {
      selectedComponents.add(c.id)
      el.classList.add("selected")
    }
  }

  // ---------- plan ----------
  function buildPlan() {
    const payload = { preset: currentPreset }
    if (currentPreset === "custom") payload.components = [...selectedComponents]
    if (currentPreset === "hardcore") {
      payload.threads = parseInt($("#hcThreads").value, 10)
      payload.parking = parseInt($("#hcParking").value, 10)
      payload.presetName = $("#hcPreset").value
      payload.modality = $("#hcModality").value
    }
    return Bridge.plan(payload).then((res) => {
      plan = res
      const list = $("#planList")
      list.innerHTML = ""
      for (const [k, v] of res.steps || []) {
        const item = document.createElement("plan-item")
        item.className = "plan-item"
        item.innerHTML = `<span class="k">${k}</span><span class="v">${v}</span>`
        list.appendChild(item)
      }
    })
  }

  // ---------- execute ----------
  async function execute() {
    show("screen-progress")
    const fill = $("#streamFill")
    const readout = $("#progressReadout")
    const log = $("#progressLog")
    log.innerHTML = ""
    fill.style.width = "0%"
    readout.textContent = "0%"

    const steps = (plan && plan.steps) || []
    const total = Math.max(steps.length, 1)
    for (let i = 0; i < steps.length; i++) {
      const [k, v] = steps[i]
      const line = document.createElement("line")
      line.className = "line"
      line.textContent = `› ${k}: ${v}`
      log.appendChild(line)
      fill.style.width = Math.round(((i + 1) / total) * 100) + "%"
      readout.textContent = Math.round(((i + 1) / total) * 100) + "%"
      await new Promise((r) => setTimeout(r, 420))
    }

    // real execution
    try {
      const payload = { preset: currentPreset }
      if (currentPreset === "custom") payload.components = [...selectedComponents]
      if (currentPreset === "hardcore") {
        payload.threads = parseInt($("#hcThreads").value, 10)
        payload.parking = parseInt($("#hcParking").value, 10)
        payload.presetName = $("#hcPreset").value
        payload.modality = $("#hcModality").value
      }
      const res = await Bridge.execute(payload)
      const ok = document.createElement("line")
      ok.className = "line ok"
      ok.textContent = res.demo ? "✓ demo mode (no launcher)" : "✓ installed"
      log.appendChild(ok)
    } catch (e) {
      const err = document.createElement("line")
      err.className = "line"
      err.textContent = "✗ " + e.message
      log.appendChild(err)
    }

    fill.style.width = "100%"
    readout.textContent = "100%"
    await new Promise((r) => setTimeout(r, 700))
    show("screen-done")
  }

  // ---------- events ----------
  function wireEvents() {
    $$(".preset-card").forEach((card) => {
      card.addEventListener("click", () => {
        currentPreset = card.dataset.preset
        Audio.play(currentPreset)
        if (currentPreset === "custom") {
          show("screen-custom")
        } else if (currentPreset === "hardcore") {
          show("screen-hardcore")
        } else {
          buildPlan().then(() => show("screen-review"))
        }
      })
    })

    $$("[data-nav='back']").forEach((b) => {
      b.addEventListener("click", () => show("screen-presets"))
    })

    $("#customReview").addEventListener("click", () => {
      buildPlan().then(() => show("screen-review"))
    })

    $("#hcInstall").addEventListener("click", () => {
      buildPlan().then(() => show("screen-review"))
    })

    $("#executeBtn").addEventListener("click", execute)

    $("#closeBtn").addEventListener("click", () => {
      if (window.close) window.close()
    })

    // hardcore sliders
    $("#hcThreads").addEventListener("input", (e) => {
      $("#hcThreadsVal").textContent = e.target.value
      const rec = $("#hcRecommend")
      rec.textContent = e.target.value === "8"
        ? RECOMMEND.threads
        : TIPS.threads
    })
    $("#hcParking").addEventListener("input", (e) => {
      $("#hcParkingVal").textContent = e.target.value + "%"
    })

    // audio toggle
    $("#audioToggle").addEventListener("click", () => {
      const on = !Audio.isEnabled()
      Audio.setEnabled(on)
      $("#audioToggle").classList.toggle("muted", !on)
      if (on) Audio.play(currentPreset)
    })

    // easter egg
    $("#easterBtn").addEventListener("click", async () => {
      try { await Bridge.easterEgg() } catch (e) {}
      $("#easterCitation").textContent = EASTER_CITATION
      $("#easterReveal").hidden = false
    })
  }

  document.addEventListener("DOMContentLoaded", boot)
})()
