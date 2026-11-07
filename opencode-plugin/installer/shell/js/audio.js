// RTR-RE installer — audio.
// Plays the arcade remix of "Obsession" (See-Saw / Yuki Kajiura) with
// preset-adaptive tempo/intensity. Uses HTMLAudioElement (works on
// file://) with playbackRate for live tempo adaptation.
//
// Remix variants (produced offline, see tools/make_obsession_remix.sh):
//   assets/audio/obsession-quick.mp3      (normal / slightly upbeat)
//   assets/audio/obsession-custom.mp3     (moderately faster)
//   assets/audio/obsession-hardcore.mp3   (significantly faster)

const Audio = (() => {
  let el = null
  let currentPreset = null
  let enabled = true

  const TEMPO = {
    quick: { rate: 1.0, volume: 1.0 },
    custom: { rate: 1.12, volume: 1.08 },
    hardcore: { rate: 1.28, volume: 1.16 },
  }

  function ensureEl() {
    if (!el) {
      el = new Audio()
      el.loop = true
      el.preload = "auto"
    }
    return el
  }

  function play(preset) {
    if (!enabled) return
    const a = ensureEl()
    const url = "assets/audio/obsession-" + preset + ".mp3"
    if (preset === currentPreset && !a.paused) return
    currentPreset = preset
    const t = TEMPO[preset] || TEMPO.quick
    a.src = url
    a.playbackRate = t.rate
    a.volume = t.volume
    a.play().catch(() => {
      // asset missing or autoplay blocked: stay silent, never break the UI
    })
  }

  function stop() {
    if (el) {
      el.pause()
      currentPreset = null
    }
  }

  function setEnabled(on) {
    enabled = on
    if (!on) stop()
    else if (currentPreset) play(currentPreset)
  }

  function isEnabled() { return enabled }

  return { play, stop, setEnabled, isEnabled }
})()
