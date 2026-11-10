# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""RTR-RE:Symbiose (short: RE:Symbiose) — bounded context budget planner.

Full name: Role-Type-Retrieval-RE:Symbiotized. Pure standard library, no
ONNX import: planning must stay cheap enough to run on every turn.

- TARGET_TOKENS (Target Context): verbatim tail preserved after compression.
- TRIGGER_TOKENS (Compact Target): total at which compression starts.

Current shipped RTR-RE default: Re-Symbiose-Mugen keeps verbatim until
a 400k Compressor trigger, reduces to a 200k Compressor target, and
the Keeper retains at most 200 messages. Symbiose-AH! uses 250k/100k/40,
Fusion-AH! uses 200k/100k/30 and Re-Symbiose uses 320k/128k/50. Those
trigger, target,
and retained-message values belong to RTR-RE, not to the shared RTR
retrieval profile. Registry values live beside this module in
``rtr_presets.json`` so Python and JavaScript read the same data;
its retrieval section (modality, ONNX threads, parking) is the shared
RTR section, while its context section is RTR-RE-only.
Evicted spans are NOT lost — evict_payload carries them verbatim
(PCDATA/CDATA exact, NDATA masked) for the RTR dual-ONNX
DTD index, so substance survives compression by retrieval (measured
exact recall after eviction, dummy turns 11-12). Deployments whose model
input cap sits below the trigger (e.g. 200k input) must scale both
numbers down through the env knobs; the planner refuses TARGET >=
TRIGGER by name.

Three offices: Keeper selects the window, Compressor compresses, RTR
manages retrieval. This planner never mutates messages.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

# Backward-compatible constants now describe the RTR-RE public default
# context preset, Re-Symbiose-Mugen, so existing imports describe RTR-RE.
TARGET_TOKENS = 200000
TRIGGER_TOKENS = 400000
MAX_KEEP_MESSAGES = 200
MAX_SUMMARY_CHARS = 20000
MAX_RESTORE_CHARS = 4000
PROTECTED_TOOLS = frozenset({"todowrite"})
# Cumulative-message protection threshold: below this many messages ever
# processed (including evicted), protected tools are always retained. Past
# it, protection becomes recency-aware — only protected messages inside the
# keep window stay hard-protected, so really old protected content yields to
# newer context (operator design, TODO-45).
PROTECTION_CUMULATIVE_THRESHOLD = 1000
PROTECTION_BUDGET_FRACTION = 0.25
NDATA_PLACEHOLDER = "[NDATA]"
SHED_MARKER = "\n[shed: oldest summary lines moved to RTR index]\n"

_NDATA_RE = re.compile(r"[A-Za-z0-9+/]{64,}={0,2}")
_CDATA_RE = re.compile(
    r"```|`[^`\n]+`|https?://[^\s)>\]]+|\b[0-9a-fA-F]{8,}\b|\b[\w.~\-]+(?:[\\/][\w.~\-]+)+\b"
)

PRESET_ENV = "OPENCODE_MEMORY_RTRRE_PRESET"
CPU_PROFILE_ENV = "OPENCODE_MEMORY_RTR_PRESET_PROFILE"
LEGACY_CPU_PROFILE_ENV = "OPENCODE_MEMORY_RTR_PROFILE"
THREADS_ENV = "OPENCODE_MEMORY_EMBED_THREADS"
PARKING_ENV = "OPENCODE_MEMORY_CPU_PARKING_PERCENT"
MODALITY_ENV = "OPENCODE_MEMORY_RETRIEVAL_MODALITY"
MODELS_ENV = "OPENCODE_MEMORY_EMBED_MODELS"

_PRESET_REGISTRY_NAME = "rtr_presets.json"
_PRESET_REGISTRY_CACHE: Dict[str, Any] | None = None


def _preset_registry() -> Dict[str, Any]:
    """Load the canonical preset registry exactly once.

    The file is data, never executable configuration. Missing or malformed
    registry data is a shipped-product defect and fails by name.
    """

    global _PRESET_REGISTRY_CACHE
    if _PRESET_REGISTRY_CACHE is not None:
        return _PRESET_REGISTRY_CACHE
    candidates = [
        Path(__file__).with_name(_PRESET_REGISTRY_NAME),
        Path(__file__).parent / "assets" / _PRESET_REGISTRY_NAME,
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"rtr preset registry {path} is not valid JSON: {exc}")
        if not isinstance(data, dict) or data.get("schema") not in {
            "rtr.preset-registry/v1",
            "rtr.preset-registry/v2",
        }:
            raise ValueError(f"rtr preset registry {path} has an unsupported schema")
        _PRESET_REGISTRY_CACHE = data
        return data
    raise ValueError(
        "rtr preset registry not found; looked in "
        + ", ".join(str(path) for path in candidates)
    )


def normalize_preset_name(raw: Any) -> str:
    """Normalize a user preset spelling to its machine id.

    The public spelling ends in ``AH!`` while file/env ids use ``ah``.
    Spaces and underscores are accepted as separators; the exclamation is
    optional in input but always present in the display name.
    """

    value = str(raw or "").strip().lower().replace("_", "-")
    value = re.sub(r"[\s-]+", "-", value).strip("-")
    if value.endswith("!"):
        value = value[:-1]
    return value


def _normalize_axis_name(raw: Any) -> str:
    return normalize_preset_name(raw)


def keeper_preset(raw: Any = "") -> Tuple[str, Dict[str, Any]]:
    registry = _preset_registry()
    name = normalize_preset_name(raw) or str(registry["defaultKeeperPreset"])
    name = str(registry.get("keeperAliases", {}).get(name, name))
    presets = registry.get("keeperPresets", {})
    if not isinstance(presets, Mapping) or name not in presets:
        known = ", ".join(sorted(presets)) if isinstance(presets, Mapping) else ""
        raise ValueError(f"{PRESET_ENV} unknown preset {raw!r}; known: {known}")
    return name, dict(presets[name])


def retrieval_modality(raw: Any = "") -> Tuple[str, Dict[str, Any]]:
    registry = _preset_registry()
    default = str(registry["cpuProfiles"][registry["defaultCpuProfile"]]["modality"])
    name = _normalize_axis_name(raw) or default
    modalities = registry.get("modalities", {})
    if not isinstance(modalities, Mapping) or name not in modalities:
        known = ", ".join(sorted(modalities)) if isinstance(modalities, Mapping) else ""
        raise ValueError(f"{MODALITY_ENV} unknown modality {raw!r}; known: {known}")
    return name, dict(modalities[name])


def _selected_cpu_profile(env: Mapping[str, str]) -> Tuple[str, Dict[str, Any], bool]:
    registry = _preset_registry()
    explicit = str(env.get(CPU_PROFILE_ENV, "") or "").strip()
    legacy = str(env.get(LEGACY_CPU_PROFILE_ENV, "") or "").strip()
    raw = explicit or legacy
    name = _normalize_axis_name(raw) or str(registry["defaultCpuProfile"])
    profile_name_env = CPU_PROFILE_ENV if explicit else LEGACY_CPU_PROFILE_ENV
    name = str(registry.get("cpuProfileAliases", {}).get(name, name))
    profiles = registry.get("cpuProfiles", {})
    if not isinstance(profiles, Mapping) or name not in profiles:
        known = ", ".join(sorted(profiles)) if isinstance(profiles, Mapping) else ""
        raise ValueError(
            f"{profile_name_env} unknown CPU preset profile {raw!r}; known: {known}"
        )
    return name, dict(profiles[name]), bool(explicit)


def _allowed_int(
    raw: Any,
    allowed: List[int],
    env_name: str,
    *,
    allow_per_model_threads: bool = False,
) -> int:
    value = str(raw).strip()
    if allow_per_model_threads and ":" in value:
        # The legacy per-model mapping remains useful for overseeded
        # engines, but each named value must still be an allowed T-mode.
        parsed: List[int] = []
        for part in value.split(","):
            if ":" not in part:
                raise ValueError(
                    f"{env_name} per-model mapping requires model:threads entries, got {part!r}"
                )
            _, number = part.split(":", 1)
            try:
                parsed.append(int(number.strip()))
            except ValueError:
                raise ValueError(
                    f"{env_name} must name an integer thread mode, got {number!r}"
                )
        invalid = [number for number in parsed if number not in allowed]
        if invalid:
            raise ValueError(f"{env_name} must be one of {allowed}, got {invalid}")
        return parsed[0]
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{env_name} must be an integer, got {raw!r}")
    if number not in allowed:
        raise ValueError(f"{env_name} must be one of {allowed}, got {number}")
    return number


def effective_threads_for_model(
    selected_threads: int,
    parking_percent: int,
    *,
    model_count: int,
    logical_processors: int | None = None,
) -> int:
    """Smallest of the selected T-mode and the parking-derived budget."""

    processors = logical_processors or os.cpu_count() or 1
    models = max(1, int(model_count))
    parked_budget = int(processors * int(parking_percent) / 100)
    per_model_budget = max(1, parked_budget // models)
    return max(1, min(int(selected_threads), per_model_budget))


def resolve_retrieval_profile(
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Resolve the three shared RTR axes: modality, threads, parking.

    This is the retrieval-only profile. It carries no Compressor
    trigger, no Compressor target, and no Keeper retained-message
    count; those live in the RTR-RE context composition. Model lists
    stay data only; ``memory_engine`` owns loading them.
    """

    src = os.environ if env is None else env
    registry = _preset_registry()
    cpu_profile_name, cpu_profile, cpu_explicit = _selected_cpu_profile(src)

    modality_raw = str(src.get(MODALITY_ENV, "") or "").strip()
    models_raw = str(src.get(MODELS_ENV, "") or "").strip()
    modality_name, modality = retrieval_modality(
        modality_raw or str(cpu_profile["modality"])
    )
    modality_source = "env" if modality_raw else f"cpu-profile:{cpu_profile_name}"
    if models_raw:
        models = [model.strip() for model in models_raw.split(",") if model.strip()]
        if not models:
            raise ValueError(f"{MODELS_ENV} must name at least one model")
        modality_source = "custom-models"
    elif modality_name == "custom":
        models = [
            "Snowflake/snowflake-arctic-embed-m",
            "BAAI/bge-base-en-v1.5",
        ]
    else:
        models = [str(model) for model in modality.get("models", [])]

    thread_modes = [int(value) for value in registry["threadModes"]]
    threads_raw = str(src.get(THREADS_ENV, "") or "").strip()
    selected_threads = (
        _allowed_int(
            threads_raw,
            thread_modes,
            THREADS_ENV,
            allow_per_model_threads=True,
        )
        if threads_raw
        else int(cpu_profile["threadsPerModel"])
    )
    threads_source = "env" if threads_raw else f"cpu-profile:{cpu_profile_name}"

    parking_values = [int(value) for value in registry["parkingPercents"]]
    parking_raw = str(src.get(PARKING_ENV, "") or "").strip()
    parking_percent = (
        _allowed_int(parking_raw, parking_values, PARKING_ENV)
        if parking_raw
        else int(cpu_profile["parkingPercent"])
    )
    parking_source = "env" if parking_raw else f"cpu-profile:{cpu_profile_name}"

    effective_threads = effective_threads_for_model(
        selected_threads,
        parking_percent,
        model_count=len(models),
    )
    compute_preset = f"{modality_name}/t{selected_threads}/p{parking_percent}"
    profile_code = compute_preset
    profile_label = (
        f"{modality['displayName']} · T{selected_threads} · P{parking_percent}"
    )
    logical_processors = os.cpu_count() or 1
    return {
        "registry_schema": str(registry["schema"]),
        "cpu_profile": cpu_profile_name,
        "cpu_profile_display": str(cpu_profile["displayName"]),
        "compute_preset": compute_preset,
        "modality": modality_name,
        "modality_display": str(modality["displayName"]),
        "models": models,
        "hybrid": bool(modality["hybrid"]),
        "expansion": bool(modality["expansion"]),
        "threads_per_model": selected_threads,
        "effective_threads_per_model": effective_threads,
        "parking_percent": parking_percent,
        "logical_processors": logical_processors,
        "parking_budget_threads": int(logical_processors * parking_percent / 100),
        "planned_threads_per_engine": effective_threads * len(models),
        "profile_code": profile_code,
        "profile_label": profile_label,
        "sources": {
            "cpu_profile": "env" if cpu_explicit else f"cpu-profile:{cpu_profile_name}",
            "modality": modality_source,
            "threads_per_model": threads_source,
            "parking_percent": parking_source,
        },
    }


def resolve_context_profile(
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Resolve the RTR-RE context composition on top of retrieval.

    RTR-RE owns three context values: the Compressor trigger that fires
    compression, the Compressor target tail that stays verbatim, and the
    Keeper retained-message count. Naming a keeper preset picks all
    three at once; each stays independently settable afterwards.
    """

    src = os.environ if env is None else env
    retrieval = resolve_retrieval_profile(src)
    preset_raw = str(src.get(PRESET_ENV, "") or "").strip()
    preset_name, preset = keeper_preset(preset_raw)
    keeper = {
        "trigger_tokens": int(preset["triggerTokens"]),
        "target_tokens": int(preset["targetTokens"]),
        "max_keep_messages": int(preset["maxKeepMessages"]),
    }
    profile_code = f"{preset_name}/{retrieval['compute_preset']}"
    profile_label = f"{preset['displayName']} · {retrieval['profile_label']}"
    sources = dict(retrieval["sources"])
    sources["preset"] = "env" if preset_raw else "registry-default"
    return {
        **retrieval,
        "preset": preset_name,
        "preset_display": str(preset["displayName"]),
        "keeper": keeper,
        "profile_code": profile_code,
        "profile_label": profile_label,
        "sources": sources,
    }


def resolve_preset_profile(env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    """Backward-compatible alias for the RTR-RE context composition.

    Existing callers resolve preset plus retrieval together; keep that
    spelling working while new code names either the retrieval profile
    or the context composition explicitly.
    """

    return resolve_context_profile(env)


def preset_registry_snapshot() -> Dict[str, Any]:
    """JSON-safe registry copy for status and parity instruments."""

    return json.loads(json.dumps(_preset_registry()))


_KNOBS = {
    "trigger_tokens": ("OPENCODE_MEMORY_RTRRE_TRIGGER", TRIGGER_TOKENS),
    "target_tokens": ("OPENCODE_MEMORY_RTRRE_TARGET", TARGET_TOKENS),
    "max_keep_messages": ("OPENCODE_MEMORY_RTRRE_MAX_KEEP", MAX_KEEP_MESSAGES),
    "max_summary_chars": ("OPENCODE_MEMORY_RTRRE_MAX_SUMMARY", MAX_SUMMARY_CHARS),
    "max_restore_chars": ("OPENCODE_MEMORY_RTRRE_MAX_RESTORE", MAX_RESTORE_CHARS),
}


def symbiose_config(env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    """Effective RE:Symbiose bounds: env override or plan default.

    Every knob refuses loudly by name on a non-integer or non-positive
    value, and TARGET at or above TRIGGER is refused: a mistuned factor
    must fail at planning time, never silently disable compression.
    """
    src = os.environ if env is None else env
    profile = resolve_preset_profile(src)
    defaults = {
        "trigger_tokens": int(profile["keeper"]["trigger_tokens"]),
        "target_tokens": int(profile["keeper"]["target_tokens"]),
        "max_keep_messages": int(profile["keeper"]["max_keep_messages"]),
        "max_summary_chars": MAX_SUMMARY_CHARS,
        "max_restore_chars": MAX_RESTORE_CHARS,
    }
    out: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for key, (env_name, _legacy_default) in _KNOBS.items():
        raw = str(src.get(env_name, "") or "").strip()
        if not raw:
            out[key] = defaults[key]
            sources[key] = (
                f"preset:{profile['preset']}"
                if key in defaults and key in profile["keeper"]
                else "default"
            )
            continue
        try:
            val = int(raw)
        except ValueError:
            raise ValueError(f"{env_name} must be an integer, got {raw!r}")
        if val <= 0:
            raise ValueError(f"{env_name} must be positive, got {val}")
        out[key] = val
        sources[key] = "env"
    if out["target_tokens"] >= out["trigger_tokens"]:
        raise ValueError(
            "OPENCODE_MEMORY_RTRRE_TARGET must be below TRIGGER "
            f"({out['target_tokens']} >= {out['trigger_tokens']})"
        )
    out["sources"] = sources
    for key in (
        "preset",
        "preset_display",
        "cpu_profile",
        "cpu_profile_display",
        "compute_preset",
        "modality",
        "modality_display",
        "models",
        "hybrid",
        "expansion",
        "threads_per_model",
        "effective_threads_per_model",
        "parking_percent",
        "logical_processors",
        "parking_budget_threads",
        "planned_threads_per_engine",
        "profile_code",
        "profile_label",
    ):
        out[key] = profile[key]
    return out


def _iter_parts(m: Dict[str, Any]):
    """Part dicts from OpenCode parts[] or an Anthropic content list."""
    for key in ("parts", "content"):
        val = m.get(key)
        if isinstance(val, list):
            for part in val:
                if isinstance(part, dict):
                    yield part


def _role_of(m: Dict[str, Any]) -> str:
    """Flat role first (API shapes), nested info.role second (hook V2)."""
    role = m.get("role")
    if isinstance(role, str) and role:
        return role
    info = m.get("info")
    if isinstance(info, dict):
        role = info.get("role")
        if isinstance(role, str) and role:
            return role
    return "unknown"


def _tool_of(m: Dict[str, Any]) -> str:
    """Flat tool first, then the first tool part's name (hook V2 ToolPart.tool)."""
    tool = m.get("tool")
    if isinstance(tool, str) and tool:
        return tool
    for part in _iter_parts(m):
        if part.get("type") == "tool":
            name = part.get("tool")
            if isinstance(name, str) and name:
                return name
    return ""


def _has_tool_part(m: Dict[str, Any]) -> bool:
    return any(part.get("type") == "tool" for part in _iter_parts(m))


def _visible_text(m: Dict[str, Any]) -> str:
    """Top-level text/content (flat shapes) plus text-part text (hook V2)."""
    chunks: List[str] = []
    for key in ("text", "content"):
        val = m.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val)
    for part in _iter_parts(m):
        if part.get("type") == "text":
            val = part.get("text")
            if isinstance(val, str) and val.strip():
                chunks.append(val)
    return "\n".join(chunks)


def _part_texts(part: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("text", "reasoning", "content"):
        val = part.get(key)
        if isinstance(val, str) and val:
            out.append(val)
    if part.get("type") == "tool":
        tool = part.get("tool")
        if isinstance(tool, str) and tool:
            out.append(tool)
        state = part.get("state")
        if isinstance(state, dict):
            out.append(str(state.get("input", "")))
            output = state.get("output")
            if isinstance(output, str) and output:
                out.append(output)
    if part.get("type") == "file":
        for key in ("filename", "url"):
            val = part.get(key)
            if isinstance(val, str) and val:
                out.append(val)
    if part.get("type") == "patch":
        files = part.get("files")
        if isinstance(files, list):
            out.append(" ".join(str(f) for f in files))
    return out


def _has_thinking(m: Dict[str, Any]) -> bool:
    for part in _iter_parts(m):
        if isinstance(part.get("reasoning"), str) and part["reasoning"].strip():
            return True
        if str(part.get("type") or "") in ("reasoning", "thinking"):
            if _part_texts(part):
                return True
    return False


def span_lane(m: Dict[str, Any]) -> str:
    """Read lane: what entered the agent. Written lane: what it produced.

    Think lane: thinking-only messages (reasoning parts, no visible text).
    Mirrors the keeper's spanLane; roles and tools read flat-first, V2-second.
    """
    # Flat "tool" counts like a tool part (RRD-120): protection already
    # reads flat-first via _tool_of; the lane must agree, else flat
    # tool-bearing assistant messages sink as "written" instead of "read".
    if _role_of(m) == "assistant" and not _has_tool_part(m) and not _tool_of(m):
        if not _visible_text(m).strip() and _has_thinking(m):
            return "think"
        return "written"
    return "read"


def span_dtype(text: str) -> str:
    if _NDATA_RE.search(text or ""):
        return "NDATA"
    if _CDATA_RE.search(text or ""):
        return "CDATA"
    return "PCDATA"


def estimate_tokens(text: str) -> int:
    """Conservative char-based estimate (4 chars/token, min 1 for non-empty)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def mask_ndata(text: str) -> str:
    return _NDATA_RE.sub(NDATA_PLACEHOLDER, text or "")


def _text_of(m: Dict[str, Any]) -> str:
    """Visible text of a message: top-level text/content plus part texts.

    OpenCode/Anthropic-shaped messages carry thinking and tool text in
    parts[] (or a content list). Thinking counts: parts the extractor
    ignored would sink as empty spans and skip trigger accounting.
    """
    chunks: List[str] = []
    for key in ("text", "content"):
        val = m.get(key)
        if isinstance(val, str) and val:
            chunks.append(val)
    for part in _iter_parts(m):
        chunks.extend(_part_texts(part))
    if chunks:
        return "\n".join(chunks)
    fallback = m.get("text") or m.get("content") or ""
    return fallback if isinstance(fallback, str) else str(fallback)


def _tokens_of(m: Dict[str, Any]) -> int:
    raw = m.get("tokens")
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw)
    return estimate_tokens(_text_of(m))


def _is_protected(m: Dict[str, Any]) -> bool:
    return str(_tool_of(m) or "") in PROTECTED_TOOLS


def plan_compression(
    messages: List[Dict[str, Any]],
    trigger_tokens: int = TRIGGER_TOKENS,
    target_tokens: int = TARGET_TOKENS,
    max_keep_messages: int = MAX_KEEP_MESSAGES,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Decide keep/evict indices under the plan bounds.

    Keeps newest-first until TARGET or the message cap binds, then walks
    the cut back so a tool result never survives without its call.
    Protected messages and the last user message are always kept (they
    count outside the tail walk but inside keep_tokens reporting), so
    TARGET is a soft target: keep_tokens can exceed it by exactly the
    protected/tool-pair additions, reported in the returned plan.

    config["live_tokens"] (RRD-108) is the window already live outside
    this ticket (keeper kept-count): the gate compares live + ticket
    against TRIGGER and the walk keeps within max(0, TARGET - live),
    so saturated windows get floor-only ticket keeps. Absent means 0.

    Protection is recency-aware past PROTECTION_CUMULATIVE_THRESHOLD
    cumulative messages: below the threshold every protected message is
    retained; at or above it, only protected messages inside the keep
    window (the newest max_keep_messages positions) stay hard-protected,
    so really old protected content becomes evictable to make space for
    newer context. The cumulative count is the number of messages ever
    processed, including evicted ones — it grows across sessions and can
    never stay pinned to the live window size.
    """
    if config:
        trigger_tokens = int(config.get("trigger_tokens", trigger_tokens))
        target_tokens = int(config.get("target_tokens", target_tokens))
        max_keep_messages = int(config.get("max_keep_messages", max_keep_messages))
    cumulative_messages = int(config.get("cumulative_messages", 0)) if config else 0
    live_tokens = max(0, int(config.get("live_tokens", 0))) if config else 0
    ticket_target = max(0, target_tokens - live_tokens)
    n = len(messages)
    total = sum(_tokens_of(m) for m in messages)
    if total + live_tokens <= trigger_tokens or n == 0:
        return {
            "compress": False,
            "total_tokens": total,
            "keep_tokens": total,
            "keep": list(range(n)),
            "evict": [],
            "evict_payload": [],
            "loop_bound": "none",
            "overrun_tokens": 0,
            "overrun_by": "none",
            "live_tokens": live_tokens,
        }

    last_user = max(
        (i for i, m in enumerate(messages) if _role_of(m) == "user"),
        default=None,
    )
    keep: set = set()
    kept_tokens = 0
    loop_bound = "exhausted"
    # Newest-first tail walk.
    for i in range(n - 1, -1, -1):
        if len(keep) >= max_keep_messages:
            loop_bound = "maxKeep"
            break
        t = _tokens_of(messages[i])
        if keep and kept_tokens + t > ticket_target:
            loop_bound = "target"
            break
        keep.add(i)
        kept_tokens += t
    # Tool-pair safety: a kept tool result pulls its preceding call in.
    # Fixpoint, not one snapshot step: batched results can chain several
    # tool messages behind one call, and every link must survive together.
    changed = True
    fix_toks = 0
    while changed:
        changed = False
        for i in sorted(keep):
            m = messages[i]
            if m.get("tool_call") or _role_of(m) == "tool":
                if i > 0 and (i - 1) not in keep:
                    keep.add(i - 1)
                    kept_tokens += _tokens_of(messages[i - 1])
                    fix_toks += _tokens_of(messages[i - 1])
                    changed = True
    # Hard protections ride outside the budget walk by design (survey D3:
    # todowrite plans are the sole record and must never evict). Past
    # PROTECTION_CUMULATIVE_THRESHOLD cumulative messages, protection is
    # recency-aware: only protected messages inside the keep window (the
    # newest max_keep_messages positions) are hard-protected, so really old
    # protected content becomes evictable to make space for newer context.
    protect_all = cumulative_messages < PROTECTION_CUMULATIVE_THRESHOLD
    recency_start = max(0, n - max_keep_messages)
    prot_toks = 0
    # Protection budget backstop (RRD-105/115): in recency-gated mode the
    # gap-span pulls are newest-first within 25% of target (oldest shed
    # first); the newest protected is always kept as the working-set
    # floor. protectAll (young session, nothing archived) stays unbounded.
    prot_candidates = []
    for i, m in enumerate(messages):
        if not _is_protected(m):
            continue
        if i in keep:
            continue
        if protect_all or i >= recency_start:
            prot_candidates.append(i)
    prot_candidates.sort(reverse=True)
    prot_budget = (
        float("inf") if protect_all else int(target_tokens * PROTECTION_BUDGET_FRACTION)
    )
    for i in prot_candidates:
        if prot_toks > 0 and prot_toks + _tokens_of(messages[i]) > prot_budget:
            break
        keep.add(i)
        kept_tokens += _tokens_of(messages[i])
        prot_toks += _tokens_of(messages[i])
    last_toks = 0
    if last_user is not None and last_user not in keep:
        keep.add(last_user)
        kept_tokens += _tokens_of(messages[last_user])
        last_toks += _tokens_of(messages[last_user])

    evict = [i for i in range(n) if i not in keep]
    payload = [
        {
            "index": i,
            "role": _role_of(messages[i]),
            "lane": span_lane(messages[i]),
            "dtype": span_dtype(_text_of(messages[i])),
            "text": mask_ndata(_text_of(messages[i])),
        }
        for i in evict
    ]
    overrun_tokens = fix_toks + prot_toks + last_toks
    contributors = [
        "fixpoint" if fix_toks > 0 else None,
        "protection" if prot_toks > 0 else None,
        "lastUser" if last_toks > 0 else None,
    ]
    contributors = [c for c in contributors if c]
    return {
        "compress": bool(evict),
        "total_tokens": total,
        "keep_tokens": kept_tokens,
        "keep": sorted(keep),
        "evict": evict,
        "evict_payload": payload,
        "loop_bound": loop_bound,
        "overrun_tokens": overrun_tokens,
        "overrun_by": "+".join(contributors) if contributors else "none",
        "live_tokens": live_tokens,
    }


def enforce_summary_budget(
    summary: str, max_chars: int = MAX_SUMMARY_CHARS
) -> Tuple[str, int]:
    """Cap a rolling summary, shedding oldest lines first.

    Returns (summary, shed_chars). At/under cap: unchanged, shed 0.
    Over cap: newest lines kept up to cap (marker included in the cap),
    so the result never exceeds max_chars.
    """
    s = summary or ""
    if len(s) <= max_chars:
        return s, 0
    budget = max_chars - len(SHED_MARKER)
    if budget <= 0:
        return s[-max_chars:], len(s) - max_chars
    kept: List[str] = []
    used = 0
    for line in reversed(s.split("\n")):
        cost = len(line) + 1
        if kept and used + cost > budget:
            break
        if not kept and cost > budget:
            kept.append(line[-budget:])
            used = budget
            break
        kept.append(line)
        used += cost
    body = "\n".join(reversed(kept))
    out = SHED_MARKER.lstrip("\n") + body
    if len(out) > max_chars:
        out = out[-max_chars:]
        body = out
    return out, max(0, len(s) - len(body))


def bounded_restore(text: str, max_chars: int = MAX_RESTORE_CHARS) -> str:
    """Cap restored memory injected into a fresh session."""
    t = text or ""
    return t[:max_chars] if len(t) > max_chars else t
