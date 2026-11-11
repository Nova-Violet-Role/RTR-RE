// SPDX-FileCopyrightText: Nova-Violet Role ORG
// SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
// RTR-RE installer — WebGL 3D scene.
// The scene is DATA declared in the scene DTD module (rtrre-scene.mod)
// and embedded per theme in index.html as <script type="application/xml">.
// This renderer parses the XML (DOMParser — native, no network) and
// renders from the declared structure: the graphics are inferred from
// the DTD family member, not hardcoded.

const Scene = (() => {
  let canvas, gl
  let program
  let particles = []
  let corePts = []
  let floorPts = []
  let corePulse = 0
  let mouseX = 0, mouseY = 0
  let camYaw = 0, camPitch = -0.16
  let raf = null

  const VERT = `
    attribute vec3 aPos;
    attribute float aSize;
    attribute vec3 aColor;
    uniform mat4 uProj;
    uniform mat4 uView;
    varying vec3 vColor;
    void main() {
      vColor = aColor;
      vec4 p = uProj * uView * vec4(aPos, 1.0);
      gl_Position = p;
      gl_PointSize = aSize * (1.0 / -p.z) * 90.0;
    }
  `

  const FRAG = `
    precision mediump float;
    varying vec3 vColor;
    void main() {
      float d = length(gl_PointCoord - vec2(0.5));
      if (d > 0.5) discard;
      float a = smoothstep(0.5, 0.0, d);
      gl_FragColor = vec4(vColor, a);
    }
  `

  function compile(type, src) {
    const s = gl.createShader(type)
    gl.shaderSource(s, src)
    gl.compileShader(s)
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(s))
    }
    return s
  }

  // ---- parse the scene XML for the current theme ----
  function loadScene() {
    const theme = currentTheme().id
    const el = document.getElementById("scene-" + theme)
    if (!el) return null
    const doc = new DOMParser().parseFromString(el.textContent, "application/xml")
    if (doc.querySelector("parsererror")) return null
    const s = doc.documentElement
    const num = (e, attr, dflt) => {
      const n = e ? e.getAttribute(attr) : null
      return n === null ? dflt : parseFloat(n)
    }
    const col = (e, attr, dflt) => {
      const v = e ? e.getAttribute(attr) : null
      if (!v) return dflt
      return v.split(",").map((x) => parseFloat(x.trim()))
    }
    const cam = s.getElementsByTagName("camera")[0]
    const core = s.getElementsByTagName("core")[0]
    const floor = s.getElementsByTagName("floor")[0]
    const parts = s.getElementsByTagName("particles")[0]
    return {
      camera: {
        drift: num(cam, "drift", 0.0012),
        parallax: num(cam, "parallax", 0.0004),
        pitch: num(cam, "pitch", -0.16),
        distance: num(cam, "distance", 6.5),
      },
      core: {
        radius: num(core, "radius", 0.55),
        pulse: num(core, "pulse", 0.12),
        glow: num(core, "glow", 0.5),
        points: num(core, "points", 220),
      },
      floor: {
        reflect: num(floor, "reflect", 0.35),
        y: num(floor, "y", -0.6),
      },
      particles: {
        count: num(parts, "count", 900),
        spread: num(parts, "spread", 3.2),
        speed: num(parts, "speed", 0.6),
        sizeMin: num(parts, "size-min", 0.6),
        sizeMax: num(parts, "size-max", 2.2),
        color: col(parts, "color", [0, 0.9, 1]),
        color2: col(parts, "color2", [0.12, 0.44, 1]),
        colorMix: num(parts, "color-mix", 0.6),
      },
    }
  }

  function init() {
    canvas = document.getElementById("scene")
    gl = canvas.getContext("webgl", { antialias: true, alpha: false })
    if (!gl) return false

    const vs = compile(gl.VERTEX_SHADER, VERT)
    const fs = compile(gl.FRAGMENT_SHADER, FRAG)
    program = gl.createProgram()
    gl.attachShader(program, vs)
    gl.attachShader(program, fs)
    gl.linkProgram(program)
    gl.useProgram(program)

    const sc = loadScene()
    if (!sc) return false

    // particles from declared structure
    for (let i = 0; i < sc.particles.count; i++) {
      particles.push(makeParticle(sc))
    }
    // core point cluster from declared radius/pulse
    const r = sc.core.radius
    for (let i = 0; i < sc.core.points; i++) {
      const th = Math.random() * Math.PI * 2
      const ph = Math.acos(2 * Math.random() - 1)
      corePts.push(
        Math.cos(th) * Math.sin(ph) * r,
        Math.cos(ph) * r,
        Math.sin(th) * Math.sin(ph) * r,
      )
    }
    // floor mirror from declared reflectivity
    const fy = sc.floor.y
    for (const p of particles) {
      floorPts.push(p.x, fy - p.y, p.z)
    }

    camPitch = sc.camera.pitch
    resize()
    window.addEventListener("resize", resize)
    window.addEventListener("mousemove", (e) => {
      mouseX = (e.clientX / window.innerWidth) * 2 - 1
      mouseY = (e.clientY / window.innerHeight) * 2 - 1
    })
    loop(sc)
    return true
  }

  function makeParticle(sc) {
    const sp = sc.particles.spread
    return {
      x: (Math.random() - 0.5) * sp * 2,
      y: Math.random() * 4 - 1.5,
      z: (Math.random() - 0.5) * sp * 2,
      vx: (Math.random() - 0.5) * 0.004 * sc.particles.speed,
      vy: (Math.random() - 0.5) * 0.004 * sc.particles.speed,
      vz: (Math.random() - 0.5) * 0.004 * sc.particles.speed,
      size: sc.particles.sizeMin + Math.random() * (sc.particles.sizeMax - sc.particles.sizeMin),
      color: Math.random() < sc.particles.colorMix ? sc.particles.color : sc.particles.color2,
      phase: Math.random() * Math.PI * 2,
    }
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = window.innerWidth * dpr
    canvas.height = window.innerHeight * dpr
    gl.viewport(0, 0, canvas.width, canvas.height)
  }

  function loop(sc) {
    raf = requestAnimationFrame(() => loop(sc))
    const t = performance.now() / 1000
    corePulse = (Math.sin(t * 0.8) + 1) / 2

    camYaw += sc.camera.drift * 60 * 0.016 + mouseX * sc.camera.parallax
    camPitch += (mouseY * 0.12 - camPitch) * 0.03

    for (const p of particles) {
      p.x += p.vx
      p.y += p.vy
      p.z += p.vz
      p.x += Math.sin(t * 0.3 + p.phase) * 0.002
      p.y += Math.cos(t * 0.25 + p.phase) * 0.002
      if (p.x > 3.2) p.x = -3.2
      if (p.x < -3.2) p.x = 3.2
      if (p.y > 2.5) p.y = -1.5
      if (p.y < -1.5) p.y = 2.5
      if (p.z > 3.2) p.z = -3.2
      if (p.z < -3.2) p.z = 3.2
    }

    gl.clearColor(0.02, 0.03, 0.05, 1)
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE)
    gl.disable(gl.DEPTH_TEST)

    const proj = mat4Perspective(0.9, canvas.width / canvas.height, 0.1, 30)
    const view = mat4LookAt(0, 1.2, sc.camera.distance, 0, 0.2, 0, camYaw, camPitch)

    // core with pulse
    const core = []
    const cr = sc.core.radius + corePulse * sc.core.pulse
    for (let i = 0; i < corePts.length; i += 3) {
      core.push(corePts[i] * (cr / sc.core.radius), corePts[i + 1] * (cr / sc.core.radius), corePts[i + 2] * (cr / sc.core.radius))
    }

    drawPoints(particles, sc.particles.color, sc.particles.color2, proj, view, 1.0)
    drawRawPoints(core, sc.core.glow, proj, view, 2.2)
    drawRawPoints(floorPts, sc.particles.color, proj, view, 0.5, 0.25 * sc.floor.reflect)
  }

  function drawPoints(list, c1, c2, proj, view, alpha) {
    const n = list.length
    const pos = new Float32Array(n * 3)
    const size = new Float32Array(n)
    const col = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      const p = list[i]
      pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = p.z
      size[i] = p.size
      col[i * 3] = c1[0]; col[i * 3 + 1] = c1[1]; col[i * 3 + 2] = c1[2]
      if (p.color === c2) {
        col[i * 3] = c2[0]; col[i * 3 + 1] = c2[1]; col[i * 3 + 2] = c2[2]
      }
    }
    drawBuffers(pos, size, col, n, proj, view, alpha)
  }

  function drawRawPoints(flat, color, proj, view, sizeMul, alpha = 1) {
    const n = flat.length / 3
    const pos = new Float32Array(flat)
    const size = new Float32Array(n).fill(sizeMul)
    const col = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      col[i * 3] = color[0]; col[i * 3 + 1] = color[1]; col[i * 3 + 2] = color[2]
    }
    drawBuffers(pos, size, col, n, proj, view, alpha)
  }

  function drawBuffers(pos, size, col, n, proj, view, alpha) {
    const aPos = gl.getAttribLocation(program, "aPos")
    const aSize = gl.getAttribLocation(program, "aSize")
    const aColor = gl.getAttribLocation(program, "aColor")
    const uProj = gl.getUniformLocation(program, "uProj")
    const uView = gl.getUniformLocation(program, "uView")

    const bPos = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, bPos)
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW)
    gl.enableVertexAttribArray(aPos)
    gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0)

    const bSize = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, bSize)
    gl.bufferData(gl.ARRAY_BUFFER, size, gl.STATIC_DRAW)
    gl.enableVertexAttribArray(aSize)
    gl.vertexAttribPointer(aSize, 1, gl.FLOAT, false, 0, 0)

    const bCol = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, bCol)
    gl.bufferData(gl.ARRAY_BUFFER, col, gl.STATIC_DRAW)
    gl.enableVertexAttribArray(aColor)
    gl.vertexAttribPointer(aColor, 3, gl.FLOAT, false, 0, 0)

    gl.uniformMatrix4fv(uProj, false, proj)
    gl.uniformMatrix4fv(uView, false, view)
    gl.drawArrays(gl.POINTS, 0, n)

    gl.deleteBuffer(bPos); gl.deleteBuffer(bSize); gl.deleteBuffer(bCol)
  }

  function mat4Perspective(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2)
    const nf = 1 / (near - far)
    return new Float32Array([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) * nf, -1,
      0, 0, 2 * far * near * nf, 0,
    ])
  }

  function mat4LookAt(eyex, eyey, eyez, tx, ty, tz, yaw, pitch) {
    const cy = Math.cos(yaw), sy = Math.sin(yaw)
    const cp = Math.cos(pitch), sp = Math.sin(pitch)
    const fx = -sy * cp, fy = sp, fz = -cy * cp
    const rx = cy, ry = 0, rz = -sy
    const ux = ry * fz - rz * fy
    const uy = rz * fx - rx * fz
    const uz = rx * fy - ry * fx
    return new Float32Array([
      rx, ux, -fx, 0,
      ry, uy, -fy, 0,
      rz, uz, -fz, 0,
      -(rx * eyex + ry * eyey + rz * eyez),
      -(ux * eyex + uy * eyey + uz * eyez),
      fx * eyex + fy * eyey + fz * eyez,
      1,
    ])
  }

  return { init }
})()
