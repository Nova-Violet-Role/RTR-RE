# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import os
import sys
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import weakref
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Tuple

try:
    import msvcrt  # Windows advisory file locking
except ImportError:  # pragma: no cover - non-Windows
    msvcrt = None  # type: ignore
try:
    import fcntl  # posix advisory file locking
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore

# Force CPU execution to minimize resource footprint
os.environ["CUDA_VISIBLE_DEVICES"] = ""
# Tokenizer parallelism defaults off (footprint); an explicit env wins
# so deployments can measure and choose (TODO-17 A/B).
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import chromadb
from fastembed import TextEmbedding

try:
    from . import context_budget as _cb
except ImportError:  # flat dev layout (tests put execution/ on sys.path)
    import context_budget as _cb

# Setup paths. Every state path can be isolated by environment so dummy,
# bench and test processes never have to touch the live registry/lexikon.
USER_HOME = Path.home()
_DEFAULT_MEMORY_DIR = USER_HOME / ".config" / "opencode" / "memory"


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else default


MEMORY_DIR = _path_from_env("OPENCODE_MEMORY_DIR", _DEFAULT_MEMORY_DIR)
_BASE_DB_DIR = MEMORY_DIR / ".local_vector_db"


def _db_dir() -> Path:
    """Vector DB home.

    OPENCODE_MEMORY_DB_DIR env override wins (bench isolation); otherwise
    the live module-global DB_DIR (monkeypatchable by tests) wins.
    """
    raw = os.environ.get("OPENCODE_MEMORY_DB_DIR", "").strip()
    if raw:
        p = Path(raw)
        p.mkdir(parents=True, exist_ok=True)
        return p
    return globals().get("DB_DIR", _BASE_DB_DIR)


DB_DIR = _BASE_DB_DIR
REGISTRY_FILE = _path_from_env(
    "OPENCODE_MEMORY_REGISTRY_FILE", MEMORY_DIR / "wiki_registry.json"
)
EXTRA_ROOTS_FILE = _path_from_env(
    "OPENCODE_MEMORY_EXTRA_ROOTS_FILE", MEMORY_DIR / "extra_roots.json"
)
# PROJECTS_DIR is defined after PROJECT_ROOTS below: it is the creation
# default = first configured discovery root, never a hardcoded home path
# (dummy3 measured a sink leaking into ~/projects from an isolated run).
WRITER_LOCK_NAME = ".writer.lock"
# Holder PID lives here, NOT in the lock file: Windows LockFile blocks
# reads of the locked byte (EBUSY), so losers could never report who
# holds the lock. This sidecar is never locked.
WRITER_PID_NAME = ".writer.pid"


def _acquire_writer_lock(db_dir: Path) -> Tuple[Any, Any]:
    """Best-effort cross-process exclusive writer lock (non-blocking).

    Returns (file_handle_or_None, holder_pid_or_None). The OS releases the
    lock when the holder process dies, so a crash can never wedge writers
    out permanently. Lock losers run read-only: search/restore/stats keep
    working, while commit/index/materialize/graph refuse with a clean
    message instead of corrupting the index as a second writer.
    """
    lock_path = db_dir / WRITER_LOCK_NAME
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+b")
    except Exception:
        return None, None
    # Fixed region: append-mode opens at EOF, so seek byte 0 first —
    # otherwise two holders with different file sizes lock different
    # bytes and the exclusion silently stops working.
    try:
        fh.seek(0)
        if msvcrt is not None:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        elif fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            return fh, os.getpid()
    except Exception:
        try:
            fh.close()
        except Exception:
            pass
        holder = None
        for probe in (db_dir / WRITER_PID_NAME, lock_path):
            try:
                holder = (
                    int((probe.read_text().strip().split() or ["0"])[0] or 0) or None
                )
                if holder is not None:
                    break
            except Exception:
                continue
        return None, holder
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()).encode("utf-8"))
        fh.flush()
    except Exception:
        pass
    try:
        (db_dir / WRITER_PID_NAME).write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass
    return fh, os.getpid()


def _quarantine_corrupt_index(reason: str) -> Any:
    """Move live vector segments aside timestamped and reset the registry.

    Best-effort self-heal for a corrupt HNSW index: quarantined segments can
    never wedge another worker, and with the registry reset the next index
    (even incremental) re-embeds everything clean. Returns a status dict.
    """
    try:
        dbd = _db_dir()
    except Exception as e:
        return {"status": "error", "message": f"quarantine failed: {e}"}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = dbd.parent / f".local_vector_db.corrupt-{stamp}"
    moved = []
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for child in sorted(dbd.iterdir()):
            if child.name == WRITER_LOCK_NAME:
                continue
            try:
                child.rename(dest / child.name)
                moved.append(child.name)
            except Exception:
                pass
    except Exception as e:
        return {"status": "error", "message": f"quarantine failed: {e}"}
    try:
        REGISTRY_FILE.write_text("{}", encoding="utf-8")
    except Exception:
        pass
    print(
        f"Quarantined corrupt index ({reason}): moved {moved} to {dest}",
        file=sys.stderr,
    )
    return {"status": "ok", "moved": moved, "dest": str(dest)}


MIN_FULL_REINDEX_HEADROOM_BYTES = 8 * 1024**3
MAX_WORKER_COMMIT_BYTES = 24 * 1024**3


def _own_commit_bytes() -> Any:
    """This worker's own pagefile-backed commit in bytes, or None when unknown."""
    try:
        import ctypes

        class _PMC(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return int(pmc.PagefileUsage)
    except Exception:
        pass
    return None


def _worker_refusal(op: str) -> Any:
    """Clean refusal message when this worker already holds absurd commit, else None."""
    own = _own_commit_bytes()
    if own is None:
        return None
    if own > MAX_WORKER_COMMIT_BYTES:
        return (
            f"{op} refused: this worker already holds {own / 1024**3:.1f} GB commit "
            f"(cap {MAX_WORKER_COMMIT_BYTES / 1024**3:.0f} GB). Restart the server instead of "
            "piling on — refusing now beats a 1455 kill mid-run."
        )
    return None


def _commit_charge_bytes() -> Any:
    """Available commit charge (RAM + pagefile) in bytes, or None when unknown."""
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullAvailPageFile)
    except Exception:
        pass
    return None


def _full_reindex_refusal() -> Any:
    """Clean refusal message when commit charge is too low for a full reindex, else None."""
    avail = _commit_charge_bytes()
    if avail is None:
        return None
    if avail < MIN_FULL_REINDEX_HEADROOM_BYTES:
        return (
            f"full reindex refused: only {avail / 1024**3:.1f} GB commit charge available "
            f"(need {MIN_FULL_REINDEX_HEADROOM_BYTES / 1024**3:.0f} GB). Close work or shed servers and retry — "
            "refusing now beats a 1455 kill mid-reindex."
        )
    return None


# --- Helping-Hand extensions: multi-root projects + multi-model embeddings ---
# Env knobs (set from opencode.jsonc `environment` — uvx passes them through):
#   OPENCODE_MEMORY_PROJECTS_DIR  os.pathsep-separated discovery roots (default: ~/projects)
#   OPENCODE_MEMORY_EMBED_MODELS   comma-separated fastembed model names (default: dual ensemble)
#   OPENCODE_MEMORY_EMBED_THREADS  onnxruntime threads per model, e.g. 8 (default: unset = auto)
DEFAULT_EMBED_MODELS = [
    "Snowflake/snowflake-arctic-embed-m",
    "BAAI/bge-base-en-v1.5",
]


QUERY_PROMPTS = {
    # Offline fallback map of model-card query prompts. The source of truth
    # is each model's own config_sentence_transformers.json (fetched and
    # cached per model), so a model update that changes its prompt is
    # followed automatically. This map only boots a first run without
    # network. Without a prompt, instruction-trained models embed queries
    # out-of-distribution (measured: arctic-m R@1 0.0309 -> 0.3299 on
    # dtd-commands).
    "snowflake_snowflake_arctic_embed_m": (
        "Represent this sentence for searching relevant passages: "
    ),
}


def _fastembed_cache_dir() -> Path:
    raw = os.environ.get("FASTEMBED_CACHE_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "fastembed_cache"


def _fetch_query_prompt(model_name: str) -> str:
    """Fetch the model card's query prompt from Hugging Face (short timeout)."""
    url = f"https://huggingface.co/{model_name}/raw/main/config_sentence_transformers.json"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            cfg = json.loads(resp.read().decode("utf-8"))
        prompts = cfg.get("prompts") or {}
        return prompts.get("query", "")
    except Exception:
        return ""


_QUERY_PROMPT_MEMO: Dict[str, str] = {}


def query_prompt_for(model_name: str) -> str:
    """Query prompt for a model, or "" when none is declared.

    Resolution order: env override (experiments) -> in-process memo ->
    per-model derived cache (fetched from the model's own config and stored
    beside the fastembed cache) -> shipped offline fallback map.
    """
    override = os.environ.get("OPENCODE_MEMORY_QUERY_PROMPT_OVERRIDE", "")
    for pair in override.split(";"):
        if "=" in pair:
            slug, _, prompt = pair.partition("=")
            if model_slug(slug) == model_slug(model_name):
                return prompt
    slug = model_slug(model_name)
    if slug in _QUERY_PROMPT_MEMO:
        return _QUERY_PROMPT_MEMO[slug]
    cache_file = _fastembed_cache_dir() / "query_prompts" / f"{slug}.json"
    try:
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("model") == slug and isinstance(data.get("prompt"), str):
                return data["prompt"]
    except Exception:
        pass
    prompt = _fetch_query_prompt(model_name)
    if prompt:
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"model": slug, "prompt": prompt}, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        _QUERY_PROMPT_MEMO[slug] = prompt
        return prompt
    prompt = QUERY_PROMPTS.get(slug, "")
    _QUERY_PROMPT_MEMO[slug] = prompt
    return prompt


def configured_embed_models() -> List[str]:
    raw = os.environ.get("OPENCODE_MEMORY_EMBED_MODELS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    if models:
        return models
    try:
        return list(_cb.resolve_retrieval_profile()["models"])
    except Exception:  # noqa: BLE001 — registry failure falls back to defaults
        return list(DEFAULT_EMBED_MODELS)


def configured_embed_threads() -> Any:
    raw = os.environ.get("OPENCODE_MEMORY_EMBED_THREADS", "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except Exception:
        return None


def configured_rrf_k() -> float:
    """RRF rank-dampening constant (standard default 60)."""
    raw = os.environ.get("OPENCODE_MEMORY_RRF_K", "").strip()
    if not raw:
        return 60.0
    try:
        k = float(raw)
        return k if k > 0 else 60.0
    except Exception:
        return 60.0


def _compute_run_consensus(run_ranks: List[Dict[str, int]]) -> List[float]:
    """Per-run agreement weight for RRF fusion (TODO-31).

    A run whose top pick appears nowhere in any peer's top-10 is likely a
    confidently-wrong model (measured: arctic-m on dtd-commands votes
    confidently wrong and drags the fusion below its best member). Such a
    run halves its vote; a run whose top pick is corroborated somewhere in
    the vote window keeps full weight. The top-10 window spares runs that
    are differently right (correct doc ranked deeper by peers). Single-run
    fusions keep weight 1.0.
    """
    n = len(run_ranks)
    if n <= 1:
        return [1.0] * n
    top10s = [set(list(r.keys())[:10]) for r in run_ranks]
    out: List[float] = []
    for i, s in enumerate(top10s):
        peers = [top10s[j] for j in range(n) if j != i]
        top1 = next(iter(run_ranks[i]), None)
        corroborated = any(top1 in p for p in peers) if top1 is not None else False
        out.append(1.0 if corroborated else 0.5)
    return out


def hybrid_lane_weights(bm25_scores: List[float]) -> tuple[float, float]:
    """(w_dense, w_bm25) for the hybrid mix; the pair always sums to 0.75.

    Lane decisiveness is the standout of the top lexical match above its
    runner-up among positive scores: a lone standout (exact-term hit) takes
    the lead over dense, while a generic field of similar matches keeps
    the default dense lead. The pre-2026-10-27 statistic (top minus median
    over all candidates, on max-normalized BM25) measured ~0.90 on both
    shapes: the top is 1.0 by construction and the median sits in the
    zero/weak mass, so the shift saturated and BM25 led on nearly every
    query (NT-G1C probe: grade-3 doc buried at rank 12 by dense-unvoted
    generic-term matches). A single positive score is a standout by
    definition; no positive scores keep the defaults.
    """
    w_dense, w_bm25 = 0.45, 0.30
    positives = sorted((s for s in bm25_scores if s > 0), reverse=True)
    if not positives:
        return w_dense, w_bm25
    if len(positives) == 1:
        gap = 1.0
    else:
        gap = (positives[0] - positives[1]) / positives[0]
    shift = 0.30 * min(1.0, max(0.0, gap))
    return w_dense - shift, w_bm25 + shift


def _empty_index_stats(message: str) -> Dict[str, Any]:
    """The one refusal shape every index_all guard returns."""
    return {
        "status": "error",
        "message": message,
        "scanned": 0,
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
    }


def configured_rtr_profile() -> str:
    """RTR compute profile: balanced (4+4 threads) or performance (8+8)."""
    raw = os.environ.get("OPENCODE_MEMORY_RTR_PROFILE", "").strip().lower()
    return raw if raw in ("balanced", "performance") else "balanced"


def resolve_threads_for(model_name: str) -> int:
    """Per-model onnxruntime threads.

    Explicit mapping wins: OPENCODE_MEMORY_EMBED_THREADS="4" (all models)
    or "arctic:4,bge:8" (substring match on the model slug).
    Otherwise the legacy RTR_PROFILE env decides (balanced 4+4,
    performance 8+8), then the shared registry CPU profile decides via
    its effective per-model threads (parking-aware). The Optimizer's
    resolved profile is the single source of truth for the default.
    """
    raw = os.environ.get("OPENCODE_MEMORY_EMBED_THREADS", "").strip()
    if raw:
        if ":" in raw:
            slug = model_slug(model_name)
            for part in raw.split(","):
                if ":" not in part:
                    continue
                key, val = part.split(":", 1)
                key = key.strip().lower()
                if key and key in slug:
                    try:
                        n = int(val.strip())
                        if n > 0:
                            return n
                    except Exception:
                        pass
        try:
            n = int(raw)
            if n > 0:
                return n
        except Exception:
            pass
    legacy_raw = os.environ.get("OPENCODE_MEMORY_RTR_PROFILE", "").strip().lower()
    if legacy_raw in ("balanced", "performance"):
        return 4 if legacy_raw == "balanced" else 8
    try:
        return int(_cb.resolve_retrieval_profile()["effective_threads_per_model"])
    except Exception:  # noqa: BLE001 — registry failure falls back to 4
        return 4


def model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def collection_name_for(model_name: str) -> str:
    return f"opencode_memory_{model_slug(model_name)}"


def _project_roots_from_env() -> List[Path]:
    raw = os.environ.get("OPENCODE_MEMORY_PROJECTS_DIR", "")
    if raw.strip():
        roots = [Path(p.strip()) for p in raw.split(os.pathsep) if p.strip()]
        if roots:
            return roots
    return [USER_HOME / "projects"]


PROJECT_ROOTS: List[Path] = _project_roots_from_env()
PROJECTS_DIR: Path = PROJECT_ROOTS[0]


def _load_extra_roots() -> List[Path]:
    try:
        if EXTRA_ROOTS_FILE.exists():
            data = json.loads(EXTRA_ROOTS_FILE.read_text(encoding="utf-8"))
            return [Path(p) for p in data if isinstance(p, str) and p.strip()]
    except Exception:
        pass
    return []


def register_extra_root(project_dir: Path) -> None:
    """Persist an out-of-roots project dir so future discovery/index runs cover it."""
    try:
        d = Path(project_dir)
        if not d.exists():
            return
        known = _load_extra_roots()
        if any(os.path.normcase(str(d)) == os.path.normcase(str(k)) for k in known):
            return
        known.append(d)
        _atomic_write_json(EXTRA_ROOTS_FILE, [str(k) for k in known])
    except Exception as e:
        print(f"Could not persist extra root {project_dir}: {e}", file=sys.stderr)


def _contains(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _is_abs_ref(s: str) -> bool:
    if not s:
        return False
    p = Path(s)
    if p.is_absolute():
        return True
    if len(s) > 2 and s[1] == ":":
        return True
    if os.sep in s or (os.altsep and os.altsep in s):
        return True
    return False


def resolve_project_dir(project: str) -> Path:
    """Resolve a project reference to a directory.

    - Absolute path (or containing separators/drive) -> used directly; auto-registered
      for discovery when it lives outside the configured roots.
    - Bare name -> first existing <root>/<name> across roots + registered extras,
      else <first-root>/<name> (for creation).
    Same-name collisions across roots: bare names resolve first-match (documented);
    absolute paths always resolve exactly.
    """
    s = str(project or "").strip()
    if _is_abs_ref(s):
        d = Path(s)
        if d.exists() and not any(_contains(r, d) for r in PROJECT_ROOTS):
            register_extra_root(d)
        return d
    for root in PROJECT_ROOTS:
        if Path(root).name == s:
            # The ref names a discovery root itself (workspace-as-ref,
            # e.g. an agent passing its workspace folder name): resolve
            # to the root, never to a nested PROJECTS_DIR/<name> guess.
            return Path(root)
    for base in list(PROJECT_ROOTS) + _load_extra_roots():
        cand = base / s
        if cand.exists():
            return cand
    for extra in _load_extra_roots():
        if extra.name == s and extra.exists():
            return extra
    return PROJECTS_DIR / s


def iter_discovery_scopes() -> List[Tuple[Path, Any]]:
    """Yield (base_dir, fixed_key) scopes, exact projects before parents.

    Extra roots are exact project directories. Their parent-based shape
    kept index-time relative paths project-prefixed, but sibling extras
    under one parent overlapped at query time: the first fixed parent
    scope claimed every later sibling. Emit each extra as its own most
    specific base first, then its legacy parent scope, so exact project
    identity always wins while existing parent-relative paths still map.
    """
    scopes: List[Tuple[Path, Any]] = []
    extras = [extra for extra in _load_extra_roots() if extra.exists()]
    scopes.extend((extra, extra.name) for extra in extras)
    scopes.extend((r, None) for r in PROJECT_ROOTS)
    scopes.extend((extra.parent, extra.name) for extra in extras)
    return scopes


def describe_indexed_path(path_str: str) -> Tuple[str, str, str]:
    """Map an indexed file path -> (project_key, rel_path, root). Root-aware."""
    try:
        ap = Path(path_str)
    except Exception:
        return ("unknown", str(path_str), "")
    for base, fixed in iter_discovery_scopes():
        try:
            rel = ap.relative_to(base)
        except Exception:
            continue
        if not rel.parts:
            continue
        key = fixed if fixed else rel.parts[0]
        return (key, str(rel), str(base))
    parts = ap.parts
    if "directives" in parts:
        i = parts.index("directives")
        if i > 0:
            return (parts[i - 1], str(ap), "")
    return (ap.parent.name if len(parts) > 1 else "unknown", str(ap), "")


def project_filter_key(project: str) -> str | None:
    """Map a search/list filter arg to the metadata key used at index time.

    None means "every project in scope": returned when the ref names a
    discovery root itself (bare root name or the root path), because a
    root holds many project keys and no single equality filter can name
    it. Measured dummy3 T1: memory_index accepted the root name as a
    project ref while search filtered project=<root name> and silently
    returned zero results for indexed facts — same ref, two meanings.
    """
    s = str(project or "").strip()
    if not s:
        return s
    if _is_abs_ref(s):
        p = Path(s)
        for base, fixed in iter_discovery_scopes():
            try:
                rel = p.relative_to(base)
            except Exception:
                continue
            if not rel.parts:
                return fixed
            return fixed if fixed else rel.parts[0]
        return p.name
    if any(Path(r).name == s for r in PROJECT_ROOTS):
        return None
    return s


# --- RTR Pillar 2: DTD-typed spans (PCDATA / CDATA / NDATA) ---
# PCDATA: parsed prose — full hybrid lane. CDATA: opaque tokens (code, ids,
# hashes, paths, URLs) — exact-match lane. NDATA: non-text (base64 blobs) —
# masked before embedding, metadata-only. Classification is structural
# (regex), done once at index: pre-classified, lightweight, no model cost.
DTYPE_PCDATA = "PCDATA"
DTYPE_CDATA = "CDATA"
DTYPE_NDATA = "NDATA"
NDATA_PLACEHOLDER = "[NDATA]"
EXACT_LANE_WEIGHT = 0.15

_NDATA_RES = [re.compile(r"[A-Za-z0-9+/]{64,}={0,2}")]
_CDATA_RES = [
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"`[^`\n]+`"),
    re.compile(r"https?://[^\s)>\]]+"),
    re.compile(r"\b[0-9a-fA-F]{8,}\b"),
    re.compile(r"\b[\w.~\-]+(?:[\\/][\w.~\-]+)+\b"),
]
# DTD-faithful: every NDATA span carries its NOTATION (unparsed entities are
# never expanded inline — only referenced). CDATA spans carry their sub-kind.
_NOTATION_RES = [
    ("base64", re.compile(r"[A-Za-z0-9+/]{64,}={0,2}")),
    ("url", re.compile(r"https?://[^\s)>\]]+")),
    ("hex", re.compile(r"\b[0-9a-fA-F]{8,}\b")),
    ("path", re.compile(r"\b[\w.~\-]+(?:[\\/][\w.~\-]+)+\b")),
    ("code", re.compile(r"```.*?```", re.DOTALL)),
    ("code", re.compile(r"`[^`\n]+`")),
]


def notations_of(text: str) -> List[str]:
    """NOTATION names present in the text (empty for pure PCDATA)."""
    found = []
    for name, rx in _NOTATION_RES:
        try:
            if rx.search(text) and name not in found:
                found.append(name)
        except Exception:
            pass
    return found


_DTYPE_RANK = {DTYPE_NDATA: 2, DTYPE_CDATA: 1, DTYPE_PCDATA: 0}


def classify_spans(text: str) -> List[Tuple[str, str]]:
    """Segment text into (span, dtype) with NDATA > CDATA > PCDATA priority."""
    hits = []
    for rx in _NDATA_RES:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), DTYPE_NDATA))
    for rx in _CDATA_RES:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), DTYPE_CDATA))
    hits.sort(key=lambda h: (h[0], -_DTYPE_RANK[h[2]]))
    out = []
    pos = 0
    for s, e, t in hits:
        if s < pos or e <= pos:
            continue
        if s > pos:
            out.append((text[pos:s], DTYPE_PCDATA))
        out.append((text[s:e], t))
        pos = e
    if pos < len(text):
        out.append((text[pos:], DTYPE_PCDATA))
    return [(span, t) for span, t in out if span]


def mask_ndata(text: str) -> str:
    """Replace NDATA spans with a placeholder (chunk boundaries/ids unchanged)."""
    return "".join(
        (NDATA_PLACEHOLDER if t == DTYPE_NDATA else span)
        for span, t in classify_spans(text)
    )


def dtype_histogram(text: str) -> str:
    counts = {DTYPE_PCDATA: 0, DTYPE_CDATA: 0, DTYPE_NDATA: 0}
    total = 0
    for span, t in classify_spans(text):
        counts[t] += len(span)
        total += len(span)
    if total == 0:
        return f"{DTYPE_PCDATA}:1.00"
    return ",".join(
        f"{k}:{counts[k] / total:.2f}" for k in (DTYPE_PCDATA, DTYPE_CDATA, DTYPE_NDATA)
    )


_DTD_DECL_START = re.compile(r"<!([A-Za-z]+)\b")
_ELEM_FRAG_RE = re.compile(r"<!ELEMENT\s+[^\s>]+\s+(.*?)>", re.S)
_ATTR_ITEM_RE = re.compile(
    r'\s+([^\s>]+)\s+(?:CDATA|ID|IDREF|IDREFS|NMTOKEN|NMTOKENS|ENTITY|ENTITIES|NOTATION|\([^)]*\))\s+(?:#REQUIRED|#IMPLIED|#FIXED|"[^"]*"|\'[^\']*\'|[^\s>]+)'
)
_DTD_SUFFIXES = (".dtd", ".mod", ".ent")
_NOISE_DIRS = (
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".local_vector_db",
    "dist",
    "build",
)


def _dtd_attr_owners(content: str) -> Dict[str, str]:
    """Attribute name -> first owning element, scoped to ATTLIST declarations.

    Mirrors the extractor's attribute_owners (eval/dtd_extractor.py) so
    the engine and the instrument speak the same vocabulary (TODO-37).
    Quote-aware scanning is inherited from _scan_dtd_declarations, so an
    ATTLIST inside an entity body is never treated as a declaration.
    """
    owners: Dict[str, str] = {}
    for kind, elem, decl in _scan_dtd_declarations(content):
        if kind != "ATTLIST" or not elem:
            continue
        for name in _ATTR_ITEM_RE.findall(decl):
            owners.setdefault(name, elem)
    return owners


def _content_model_fragments(decls) -> List[str]:
    """Distinctive content-model fragments from ELEMENT declarations.

    Matches the extractor's fragment extraction (eval/dtd_extractor.py) so
    the inventory header and the T9 query derivation speak the same
    vocabulary (TODO-33).
    """
    out: List[str] = []
    seen = set()
    for kind, _name, decl in decls:
        if kind != "ELEMENT":
            continue
        m = _ELEM_FRAG_RE.search(decl)
        if m is None:
            continue
        frag = " ".join(m.group(1).split())
        if len(frag) > 6 and frag not in seen:
            seen.add(frag)
            out.append(frag)
            if len(out) >= 50:
                break
    return out


_DTD_PUBLIC_RE = re.compile(r'PUBLIC\s+"([^"]*)"(?:\s+"([^"]*)")?')
_DTD_SYSTEM_RE = re.compile(r'SYSTEM\s+"([^"]*)"')
_DTD_MODULE_SWITCH_RE = re.compile(r'\s+"(IGNORE|INCLUDE)"')


def _dtd_lineage(decls) -> List[Dict[str, Any]]:
    """External entity references (PUBLIC/SYSTEM) as lineage tuples.

    Each entry carries the entity name, the raw public id when present,
    and the parsed owner/keyword split of the PUBLIC identifier (the
    standard form is `owner//keyword//language`, e.g.
    `-//OASIS//DTD DocBook V3.1//EN`). SYSTEM-only references carry their
    system id. Entity bodies are never scanned — the scanner already
    yields only top-level declarations (LAW.AMP.13), so an injected
    reference inside an entity value cannot surface here.
    """
    out: List[Dict[str, Any]] = []
    for kind, name, decl in decls:
        if kind != "ENTITY" or not name:
            continue
        m = _DTD_PUBLIC_RE.search(decl)
        if m is not None:
            public_id = m.group(1)
            parts = [p.strip() for p in public_id.split("//")]
            owner = parts[1] if len(parts) > 1 else ""
            keyword = parts[2] if len(parts) > 2 else ""
            out.append(
                {
                    "name": name,
                    "public_id": public_id,
                    "owner": owner,
                    "keyword": keyword,
                    "system_id": m.group(2),
                }
            )
            continue
        m = _DTD_SYSTEM_RE.search(decl)
        if m is not None:
            out.append(
                {
                    "name": name,
                    "public_id": None,
                    "owner": "",
                    "keyword": "",
                    "system_id": m.group(1),
                }
            )
    return out


def _dtd_module_switches(decls) -> List[Dict[str, str]]:
    """Customization-layer switches: %xxx.module "IGNORE"/"INCLUDE" entities.

    The DocBook customization recipe switches whole modules off before
    inclusion (`<!ENTITY % sect3.module "IGNORE">`). The switch set is a
    signature of the customization layer (defguide examples/remv.sect4.dtd).
    """
    out: List[Dict[str, str]] = []
    for kind, name, decl in decls:
        if kind != "ENTITY" or not name or not name.endswith(".module"):
            continue
        m = _DTD_MODULE_SWITCH_RE.search(decl)
        if m is not None:
            out.append({"name": name, "value": m.group(1)})
    return out


def _dtd_role(decls) -> str:
    """Driver vs module: a driver declares module switches or includes
    external DTDs (PUBLIC/SYSTEM references); a module is a pure
    declaration pool."""
    if _dtd_module_switches(decls) or _dtd_lineage(decls):
        return "driver"
    return "module"


def _scan_dtd_declarations(content: str):
    """Yield (kind, name, declaration_text) for each top-level DTD declaration.

    A declaration runs from '<!' to its matching '>' with single/double
    quotes respected, so a '>' inside a quoted entity value never splits a
    declaration (LAW.AMP.13: entity bodies are data, never expanded).
    """
    i = 0
    n = len(content)
    while i < n:
        m = _DTD_DECL_START.search(content, i)
        if m is None:
            return
        kind = m.group(1).upper()
        start = m.start()
        j = m.end()
        quote = None
        while j < n:
            ch = content[j]
            if quote is not None:
                if ch == quote:
                    quote = None
            elif ch in ('"', "'"):
                quote = ch
            elif ch == ">":
                break
            j += 1
        if j >= n:
            return
        decl = content[start : j + 1]
        rest = content[m.end() : j].strip()
        if kind == "ENTITY" and rest.startswith("%"):
            rest = rest[1:].lstrip()
        name = rest.split()[0] if rest else ""
        yield kind, name, decl
        i = j + 1


def cdata_terms_of(text: str) -> List[str]:
    """Opaque terms that deserve the exact-match lane."""
    terms = []
    for span, t in classify_spans(text):
        if t != DTYPE_CDATA:
            continue
        core = span.strip("`").strip()
        if len(core) >= 3:
            terms.append(core.lower())
    seen, out = set(), []
    for term in terms:
        if term not in seen:
            seen.add(term)
            out.append(term)
    return out


# --- STRUCT lane (TODO-15): structural grep as a typed sub-lane of CDATA.
# Contract: formal/Symbiose/Lane.lean (total+disjoint routing, shared
# EXACT_LANE_WEIGHT cap, fallback identity when off/absent). Study:
# artifacts/geometry/2026-10-27-ccc-vs-rg-study.md — rg --json is the
# default backend, ccc answers only explicitly structural patterns.
STRUCT_LANE_ENV = "OPENCODE_MEMORY_STRUCT_LANE"
_STRUCT_CODE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_STRUCT_HIT_CAP_PER_FILE = 20


def struct_lane_mode() -> str:
    """STRUCT lane backend from env: 'off' (default), 'rg', 'ccc', 'auto'.

    Anything unrecognized is off: a typo must never invent a backend.
    """
    raw = os.environ.get(STRUCT_LANE_ENV, "").strip().lower()
    return raw if raw in ("rg", "ccc", "auto") else "off"


def _is_code_shaped(token: str) -> bool:
    if "_" in token:
        return True
    return any(a.islower() and b.isupper() for a, b in zip(token, token[1:]))


def classify_query_terms(
    query: str,
) -> Tuple[List[str], List[str], str | None]:
    """Partition opaque query terms into (exact, structural, pattern).

    Realizes the Lane.lean router: opaque spans (urls, hex, paths) vote
    exact, code-shaped identifiers vote structural, and a backslash
    by-example pattern is carried whole for the ccc backend. The two
    term lists are disjoint by construction (partition_counts).
    """
    text = query or ""
    pattern = text.strip() if re.search(r"\\[A-Za-z(]", text) else None
    base = cdata_terms_of(text)
    struct: List[str] = []
    for tok in _STRUCT_CODE_TOKEN_RE.findall(text):
        if _is_code_shaped(tok) and tok.lower() not in struct:
            struct.append(tok.lower())
    for term in base:
        core = term.strip("()")
        if _is_code_shaped(core) and core not in struct:
            struct.append(core)
    exact = [t for t in base if t not in struct and t.strip("()") not in struct]
    return exact, struct, pattern


def _rg_structural_hits(
    terms: List[str], paths: List[str], timeout: float
) -> Dict[str, List[Dict[str, Any]]]:
    exe = shutil.which("rg")
    if not exe or not terms:
        return {}
    alt = "|".join(re.escape(t) for t in terms)
    argv = [
        exe,
        "--json",
        "--no-messages",
        "-i",
        "-m",
        str(_STRUCT_HIT_CAP_PER_FILE),
        "-e",
        rf"\b(?:{alt})\b",
        "--",
        *paths,
    ]
    proc = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode not in (0, 1):
        return {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for line in (proc.stdout or "").splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if not isinstance(ev, dict) or ev.get("type") != "match":
            continue
        data = ev.get("data") or {}
        path = str((data.get("path") or {}).get("text") or "")
        text = str((data.get("lines") or {}).get("text") or "")
        lineno = data.get("line_number") or 0
        if not path:
            continue
        low = text.lower()
        for term in terms:
            if term.lower() in low:
                out.setdefault(path, []).append(
                    {"term": term.lower(), "line": int(lineno)}
                )
    return out


def _norm_struct_path(s: str) -> str:
    """Case/separator-insensitive path key on Windows; identity on POSIX."""
    if os.name == "nt":
        return s.replace("/", "\\").lower()
    return s


def _ccc_structural_hits(
    pattern: str, paths: List[str], timeout: float
) -> Dict[str, List[Dict[str, Any]]]:
    exe = shutil.which("ccc")
    if not exe:
        return {}
    root = os.path.commonpath([str(Path(p).parent) for p in paths])
    proc = subprocess.run(
        [exe, "grep", pattern, root],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        return {}

    wanted = {_norm_struct_path(str(p)): str(p) for p in paths}
    out: Dict[str, List[Dict[str, Any]]] = {}
    current: str | None = None
    for line in (proc.stdout or "").splitlines():
        m = re.match(r"\s*(\d+)\| ", line)
        if m:
            if current and len(out.get(current, [])) < _STRUCT_HIT_CAP_PER_FILE:
                out.setdefault(current, []).append(
                    {"term": "pattern", "line": int(m.group(1))}
                )
            continue
        cand = _norm_struct_path(line.strip())
        if not cand or cand == "---":
            continue
        current = None
        for key, orig in wanted.items():
            if key == cand or key.endswith("\\" + cand) or cand.endswith("\\" + key):
                current = orig
                break
    return out


def structural_hits(
    terms: List[str],
    pattern: str | None,
    source_paths: List[str],
    backend: str = "auto",
    timeout: float = 10.0,
) -> Dict[str, List[Dict[str, Any]]]:
    """Bounded structural evidence over candidate source files.

    Returns {source_path: [{term, line}]} and {} on any absence or
    failure — the lane never raises into search (fallback identity).
    Terms and patterns travel as argv values to a fixed binary; nothing
    is shell-evaluated.
    """
    mode = (backend or "off").strip().lower()
    if mode not in ("rg", "ccc", "auto"):
        return {}
    paths = [
        str(p) for p in dict.fromkeys(source_paths or []) if p and Path(p).is_file()
    ]
    if not paths:
        return {}
    try:
        if pattern and mode in ("ccc", "auto"):
            return _ccc_structural_hits(pattern, paths, timeout)
        if mode == "ccc" or not terms:
            return {}
        return _rg_structural_hits(list(terms), paths, timeout)
    except Exception:
        return {}


def configured_suffixes() -> Tuple[str, ...]:
    """Indexed file suffixes (DtD polyglot: markdown + NestedText + YAML + DTD family)."""
    raw = os.environ.get("OPENCODE_MEMORY_FILE_SUFFIXES", "")
    if raw.strip():
        out = tuple(
            (
                s.strip().lower()
                if s.strip().startswith(".")
                else "." + s.strip().lower()
            )
            for s in raw.split(",")
            if s.strip()
        )
        if out:
            return out
    return (".md", ".nt", ".yaml", ".yml", ".dtd", ".mod", ".ent")


def _matches_suffix(name: str) -> bool:
    return name.lower().endswith(configured_suffixes())


def safe_concept_filename(filename: str) -> str:
    """Leaf .md filename guard: refuse traversal, absolute paths and empties.

    Concept writes name a file, never a path: anything that is not a
    bare leaf name is refused instead of sanitized, so a caller can
    never be surprised by where its bytes landed.
    """
    raw = str(filename or "").strip()
    if not raw:
        raise ValueError(
            "Refusing to write outside the concepts folder: empty filename"
        )
    if not raw.endswith(".md"):
        raw += ".md"
    if Path(raw).name != raw:
        raise ValueError(f"Refusing to write outside the concepts folder: {filename!r}")
    return raw


LEXIKON_GLOBAL_FILE = _path_from_env(
    "OPENCODE_MEMORY_LEXIKON_GLOBAL_FILE", MEMORY_DIR / "lexikon_global.json"
)


# Ensure directories exist
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _latest_session_report(sessions_dir: Path) -> Any:
    """Newest session report by modification time (names lie).

    Dated reports sort chronologically by name, but digest-named spans
    (rtrre-*) sort arbitrarily — modification time is the only true
    recency signal. Returns None when no report exists.
    """
    try:
        reports = [p for p in sessions_dir.glob("*.md") if p.is_file()]
    except Exception:
        return None
    if not reports:
        return None
    try:
        return max(reports, key=lambda p: p.stat().st_mtime)
    except Exception:
        return None


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically (tmp + rename) so a crash never leaves a half file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _in_scope(path_str: str, scope) -> bool:
    """True when path_str is a scope root or lives beneath one."""
    norm = os.path.normcase(path_str)
    return any(norm == root or norm.startswith(root + os.sep) for root in scope)


# One index run at a time per process: concurrent index_all/index_files
# runs duplicate embedding work and race Chroma segments. Ticks and
# manual runs serialize here; searches never block on it.
_INDEX_LOCK = threading.Lock()

# Wave size for chunk+upsert streaming: jobs materialize per wave, never
# for the whole run, so a 5k-file scope cannot balloon RAM before the
# first upsert lands.
INDEX_WAVE_SIZE = 200

# Page size for janitor/repair collection scans: one giant get() exceeds
# SQLite's variable limit on big collections (measured live 2026-11-10).
JANITOR_PAGE_SIZE = 500


def process_rss_mb() -> float:
    """Current process RSS in MB (Windows ctypes, POSIX resource)."""
    try:
        import ctypes

        class _PMC(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        if psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb
        ):
            return pmc.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return -1.0


def thread_top_frames(limit: int = 3) -> Dict[str, List[str]]:
    """Top stack frames per live thread (stdlib faulthandler-free snapshot)."""
    import sys
    import threading
    import traceback

    out: Dict[str, List[str]] = {}
    frames = sys._current_frames()
    names = {t.ident: t.name for t in threading.enumerate()}
    for ident, frame in frames.items():
        stack = traceback.extract_stack(frame)[-limit:]
        out[names.get(ident, str(ident))] = [
            f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in stack
        ]
    return out


class MemoryEngine:
    # Process-wide ChromaDB clients, one per DB path. Multiple live
    # PersistentClient instances on the same path go stale against each
    # other (deleted HNSW ids resurfacing as "Error finding id" on filtered
    # queries). A single shared client per path is the documented shape.
    _CLIENTS: Dict[str, Any] = {}
    _CLIENT_HOLDERS: Dict[str, weakref.WeakSet] = {}

    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._chroma_client = None
        self._collections: Dict[str, Any] = {}
        self._writer_lock, self._writer_holder = _acquire_writer_lock(_db_dir())
        self.read_only = self._writer_lock is None

    def close(self) -> None:
        """Release the writer lock handle and the Chroma client.

        Without the lock release every short-lived engine leaks one fd
        and unittest reports ResourceWarning per test (measured
        2026-10-26). The client is closed AND evicted from the
        process-wide _CLIENTS cache: a closed client's
        RustBindingsAPI deletes its bindings on stop(), so a cached
        corpse would poison every later engine on the same DB path in
        this process ('RustBindingsAPI' object has no attribute
        'bindings'). Close is terminal for this engine's DB path —
        collections are dropped with the client, and the next engine
        on the path builds a fresh client. Co-live engines keep the
        shared client: eviction waits for the last holder to close.
        """
        key = str(_db_dir())
        holders = MemoryEngine._CLIENT_HOLDERS.get(key)
        last_holder = True
        if holders is not None:
            try:
                holders.discard(self)
            except Exception:
                pass
            last_holder = len(holders) == 0
        if last_holder:
            MemoryEngine._CLIENT_HOLDERS.pop(key, None)
            client = MemoryEngine._CLIENTS.pop(key, None)
            if client is None:
                client = getattr(self, "_chroma_client", None)
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
        self._chroma_client = None
        self._collections = {}
        fh = getattr(self, "_writer_lock", None)
        if fh is not None:
            try:
                fh.close()
            except Exception:
                pass
            self._writer_lock = None

    def _require_writer(self, op: str) -> Any:
        if self.read_only:
            holder = (
                f" (lock held by PID {self._writer_holder})"
                if self._writer_holder
                else ""
            )
            return {
                "status": "error",
                "message": f"{op} refused: another RTR server holds the writer lock{holder}. Stop the other server and retry — a single writer keeps the index uncorrupted.",
            }
        return None

    @property
    def embed_model_names(self) -> List[str]:
        return configured_embed_models()

    @property
    def primary_model_name(self) -> str:
        return self.embed_model_names[0]

    @property
    def models(self) -> Dict[str, Any]:
        """All configured embedding models, keyed by slug. Warms ONNX on first access."""
        for name in self.embed_model_names:
            slug = model_slug(name)
            if slug not in self._models:
                threads = resolve_threads_for(name)
                print(
                    f"Loading {name} via fastembed... (threads={threads})",
                    file=sys.stderr,
                )
                self._models[slug] = TextEmbedding(model_name=name, threads=threads)
        return self._models

    @property
    def model(self):
        """Backward-compat: primary embedding model."""
        return self.models[model_slug(self.primary_model_name)]

    def embed_all(
        self, texts: List[str], for_query: bool = False
    ) -> Dict[str, List[List[float]]]:
        out: Dict[str, List[List[float]]] = {}
        for slug, m in self.models.items():
            model_texts = list(texts)
            if for_query:
                prompt = query_prompt_for(slug)
                if prompt:
                    model_texts = [prompt + t for t in model_texts]
            out[slug] = [[float(v) for v in e] for e in m.embed(model_texts)]
        return out

    @property
    def chroma_client(self):
        key = str(_db_dir())
        client = MemoryEngine._CLIENTS.get(key)
        if client is None:
            client = chromadb.PersistentClient(path=key)
            MemoryEngine._CLIENTS[key] = client
        holders = MemoryEngine._CLIENT_HOLDERS.setdefault(key, weakref.WeakSet())
        holders.add(self)
        self._chroma_client = client
        return client

    def rtr_collections(self) -> Dict[str, Any]:
        """All RTR collections actually present (configured + legacy/orphans).

        Purge and delete fan out over these so model switches never leak.
        """
        out: Dict[str, Any] = dict(self.collections)
        try:
            for col in self.chroma_client.list_collections():
                if col.name == "opencode_memory" or col.name.startswith(
                    "opencode_memory_"
                ):
                    out.setdefault(col.name, col)
        except Exception:
            pass
        return out

    @property
    def collections(self) -> Dict[str, Any]:
        """One ChromaDB collection per embedding model (fixed vector spaces never mix)."""
        if not self._collections:
            metadata: Dict[str, Any] = {"hnsw:space": "cosine"}
            # Determinism knobs (measured, TODO-31): chroma's HNSW build is
            # multithreaded by default and its search is approximate, so two
            # identical bench runs differed on 52-118/163 queries. Pinning
            # num_threads=1 (deterministic graph) and a high search_ef
            # (near-exact search) makes results reproducible. Unset keeps
            # chroma defaults; the bench pins both.
            try:
                nt = os.environ.get("OPENCODE_MEMORY_HNSW_NUM_THREADS", "").strip()
                if nt:
                    metadata["hnsw:num_threads"] = int(nt)
            except Exception:
                pass
            try:
                sef = os.environ.get("OPENCODE_MEMORY_HNSW_SEARCH_EF", "").strip()
                if sef:
                    metadata["hnsw:search_ef"] = int(sef)
            except Exception:
                pass
            for name in self.embed_model_names:
                slug = model_slug(name)
                self._collections[slug] = self.chroma_client.get_or_create_collection(
                    name=collection_name_for(name),
                    metadata=metadata,
                )
        return self._collections

    @property
    def collection(self):
        """Backward-compat: primary collection."""
        return self.collections[model_slug(self.primary_model_name)]

    def calculate_sha256(self, filepath: Path) -> str:
        """Calculate SHA256 of file content to detect changes."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def discover_wikis(self) -> List[Dict[str, Any]]:
        """
        Recursively discover wiki-like markdown files across all scopes:
        configured PROJECT_ROOTS plus auto-registered out-of-roots project dirs.
        Matches directives/*.md and files/folders with 'wiki' in their paths.
        """
        discovered = []
        for scope_base, fixed_key in iter_discovery_scopes():
            if not scope_base.exists():
                continue
            # Walk through the scope recursively (for a fixed out-of-roots
            # project only its own subtree; siblings are never indexed, so a
            # drive-root parent never turns a commit into a full-drive walk)
            walk_root = scope_base / fixed_key if fixed_key else scope_base
            if not walk_root.exists():
                continue
            for root, dirs, files in os.walk(walk_root):
                # Deterministic discovery: os.walk yields entries in OS
                # enumeration order, which varies across runs on Windows.
                # Unstable insertion order makes the HNSW index
                # nondeterministic (measured: two identical bench runs
                # differed on 118/163 queries). Sorting fixes it.
                dirs.sort()
                files.sort()
                root_path = Path(root)

                # Skip common noise dirs to keep index fast
                if any(part in root_path.parts for part in _NOISE_DIRS):
                    continue

                for file in files:
                    if not _matches_suffix(file):
                        continue

                    file_path = root_path / file
                    try:
                        rel_path = file_path.relative_to(scope_base)
                    except Exception:
                        continue
                    parts = rel_path.parts

                    if not parts:
                        continue

                    project_name = fixed_key if fixed_key else parts[0]

                    # Check if it fits option B: inside directives/ folder
                    is_directive = "directives" in parts

                    # Check if path or file has "wiki" in its name (priority)
                    has_wiki = any("wiki" in part.lower() for part in parts)

                    # DTD-family files are first-class (TODO-64): discovered
                    # anywhere, not just under directives/ or wiki paths.
                    is_dtd = file_path.suffix.lower() in _DTD_SUFFIXES

                    # We prioritize all .md files in directives/ folder,
                    # and any .md files with "wiki" in their paths
                    if is_directive or has_wiki or is_dtd:
                        category = "wiki" if has_wiki else "directive"
                        # If it's a concept subfolder inside directives, extract that subcategory
                        sub_category = None
                        if is_directive:
                            dir_idx = parts.index("directives")
                            if len(parts) > dir_idx + 2:
                                sub_category = parts[dir_idx + 1]

                        discovered.append(
                            {
                                "path": str(file_path),
                                "project": project_name,
                                "category": category,
                                "subcategory": sub_category or "general",
                                "filename": file_path.name,
                                "rel_path": str(rel_path),
                            }
                        )

        return discovered

    def chunk_markdown(self, filepath: Path, rel_path: str) -> List[Dict[str, Any]]:
        """
        Split a markdown file into logical sections based on headers.
        Each section includes the main document path context for the embedding model.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
            return []

        # If file is empty, return nothing
        if not content.strip():
            return []

        # Parse sections using markdown headers
        # Split on headers (# , ## , ### , ####)
        header_pattern = re.compile(r"^(#{1,4}\s+.*)$", re.MULTILINE)
        parts = header_pattern.split(content)

        chunks = []
        current_title = "Introduction"

        # The split returns [initial_text, header_1, section_1, header_2, section_2, ...]
        if parts[0].strip():
            chunks.append({"title": current_title, "text": parts[0].strip()})

        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            section_body = parts[i + 1].strip() if i + 1 < len(parts) else ""

            # Extract header text
            title = header.lstrip("#").strip()

            if section_body:
                chunks.append({"title": title, "text": f"{header}\n\n{section_body}"})

        # If no header chunks were created, just treat the whole file as one chunk
        if not chunks:
            chunks.append({"title": "Full Document", "text": content.strip()})

        formatted_chunks = []
        for idx, chunk in enumerate(chunks):
            section_text = (
                f"Document: {rel_path}\nSection: {chunk['title']}\n\n{chunk['text']}"
            )
            links = list(set(re.findall(r"\[\[([^\]]+)\]\]", chunk["text"])))
            formatted_chunks.append(
                {
                    "chunk_id": f"{rel_path}#chunk_{idx}",
                    "text": section_text,
                    "title": chunk["title"],
                    "raw_body": chunk["text"],
                    "linked_concepts": links,
                }
            )

        return formatted_chunks

    def chunk_dtd_whole(self, filepath: Path, rel_path: str) -> List[Dict[str, Any]]:
        """One chunk per DTD-like file, prefixed with a structural inventory.

        Measured (TODO-30): fragmenting DTDs into declaration chunks degraded
        retrieval below the whole-file baseline (0.5652 → 0.5435 overall;
        T9 0.667 → 0.5, T10 0.5 → 0.25) because DTD files are compact and
        the queries are file-level. This variant keeps the winning whole-file
        granularity and adds the vocabulary signal the dense model lacks: an
        inventory header naming the file's elements, attributes, entities and
        notations, so attribute/entity/cross-family queries can match the
        names without fragmentation noise. Raw content follows verbatim —
        entity bodies are data, never expanded (LAW.AMP.13).
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
            return []
        if not content.strip():
            return []
        # Schema-scoped inventory (TODO-13): span files carry verbatim
        # content that may quote DTD declarations (measured live: quoted
        # SAMPLE_DTD polluted ROOT/ATTRIBUTES/ENTITIES with book, copyright,
        # xhtml.list). The structure lives before the first span element;
        # inventory scans that schema block only. Raw content still follows
        # whole. Files without spans scan whole as before.
        inv_text = content
        span_at = content.find("<span ")
        if span_at < 0:
            span_at = content.find("<span>")
        if span_at > 0:
            inv_text = content[:span_at]
        try:
            decls = list(_scan_dtd_declarations(inv_text))
        except Exception as e:
            print(f"Error scanning {filepath}: {e}", file=sys.stderr)
            return []
        elements = sorted({n for k, n, _d in decls if k == "ELEMENT" and n})
        attrs = sorted({n for k, n, _d in decls if k == "ATTLIST" and n})
        entities = sorted({n for k, n, _d in decls if k == "ENTITY" and n})
        notations = sorted({n for k, n, _d in decls if k == "NOTATION" and n})
        root = next((n for k, n, _d in decls if k == "ELEMENT" and n), "")
        header_lines = []
        if root:
            header_lines.append("ROOT: " + root)
        # No ELEMENTS list: a full element-name bag homogenizes the corpus
        # and hurt T1/T7/T9/T10 (measured, TODO-30). Element vocabulary stays
        # available in the raw content that follows the header.
        if attrs:
            header_lines.append("ATTRIBUTES: " + ", ".join(attrs[:200]))
        if entities:
            header_lines.append("ENTITIES: " + ", ".join(entities[:200]))
        if notations:
            header_lines.append("NOTATIONS: " + ", ".join(notations[:200]))
        frags = _content_model_fragments(decls)
        if frags:
            header_lines.append("CONTENT MODELS: " + ", ".join(frags))
        # Family signatures (TODO-64, proposals A-C): role, lineage and
        # customization switches give dense retrieval the discriminator it
        # lacks for families that share element vocabulary (measured T10
        # collapse: DITA vs DocBook `appendix`).
        role = _dtd_role(decls)
        header_lines.append("ROLE: " + role)
        lineage = _dtd_lineage(decls)
        if lineage:
            parts = []
            for entry in lineage:
                if entry["public_id"]:
                    parts.append(
                        f"{entry['name']} ({entry['owner']} · {entry['keyword']})"
                    )
                else:
                    parts.append(f"{entry['name']} SYSTEM {entry['system_id']}")
            header_lines.append("LINEAGE: " + "; ".join(parts))
        switches = _dtd_module_switches(decls)
        if switches:
            header_lines.append(
                "MODULE SWITCHES: "
                + ", ".join(f"{s['name']}={s['value']}" for s in switches)
            )
        header = "\n".join(header_lines)
        body = f"{header}\n\n{content}" if header else content
        try:
            section_text = f"Document: {rel_path}\nSection: Full Document\n\n{body}"
        except Exception as e:
            print(f"Error assembling chunk for {filepath}: {e}", file=sys.stderr)
            return []
        return [
            {
                "chunk_id": f"{rel_path}#chunk_0",
                "text": section_text,
                "title": "Full Document",
                "raw_body": body,
                "linked_concepts": [],
            }
        ]

    def chunk_dtd(self, filepath: Path, rel_path: str) -> List[Dict[str, Any]]:
        """Split a DTD-like file (.dtd/.mod/.ent) on structural boundaries.

        Hybrid design (measured, TODO-30): files with up to
        OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX declarations (default 300)
        get one atomic chunk per declaration — element/attribute/entity/
        content-model queries then match exactly the declaration they target
        (the grouped design diluted these lanes: T9 fell 0.667 → 0.167).
        Files above the threshold get consecutive declarations grouped into
        chunks bounded by OPENCODE_MEMORY_DTD_CHUNK_TOKENS (default 512) so
        the giants (TEI: 2702 declarations) stay bounded — the 23 GB memory
        blow-up measured on the unbounded per-declaration design came from
        the count, not the text. Declaration boundaries are always respected
        as split points. Titles carry the first declaration's kind and name.
        Raw declaration text is kept verbatim — entity bodies are data, never
        expanded (LAW.AMP.13).
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
            return []
        if not content.strip():
            return []
        try:
            per_decl_max = int(
                os.environ.get("OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX", "300")
            )
            per_decl_max = per_decl_max if per_decl_max > 0 else 300
        except Exception:
            per_decl_max = 300
        decls = list(_scan_dtd_declarations(content))
        chunks: List[Dict[str, Any]] = []

        def emit(idx: int, kind: str, name: str, body: str) -> None:
            title = f"{kind}: {name}" if name else kind
            section_text = f"Document: {rel_path}\nSection: {title}\n\n{body}"
            chunks.append(
                {
                    "chunk_id": f"{rel_path}#chunk_{idx}",
                    "text": section_text,
                    "title": title,
                    "raw_body": body,
                    "linked_concepts": [],
                }
            )

        if len(decls) <= per_decl_max:
            for idx, (kind, name, decl) in enumerate(decls):
                emit(idx, kind, name, decl)
            return chunks

        try:
            max_tokens = int(os.environ.get("OPENCODE_MEMORY_DTD_CHUNK_TOKENS", "512"))
            max_tokens = max_tokens if max_tokens > 0 else 512
        except Exception:
            max_tokens = 512
        buf: List[Tuple[str, str, str]] = []
        buf_tokens = 0

        def flush() -> None:
            nonlocal buf, buf_tokens
            if not buf:
                return
            first_kind, first_name, _ = buf[0]
            body = "\n".join(d for _, _, d in buf)
            emit(len(chunks), first_kind, first_name, body)
            buf = []
            buf_tokens = 0

        for kind, name, decl in decls:
            decl_tokens = max(1, len(decl) // 4)
            if buf and buf_tokens + decl_tokens > max_tokens:
                flush()
            buf.append((kind, name, decl))
            buf_tokens += decl_tokens
        flush()
        # Hard ceiling (operator guard, TODO-31): a pathological env or file
        # must never recreate the 23 GB blow-up. If a per-declaration split
        # would exceed this many chunks, fall back to the whole-file inventory
        # chunk instead.
        try:
            hard_ceiling = int(os.environ.get("OPENCODE_MEMORY_DTD_MAX_CHUNKS", "2000"))
            hard_ceiling = hard_ceiling if hard_ceiling > 0 else 2000
        except Exception:
            hard_ceiling = 2000
        if len(chunks) > hard_ceiling:
            return self.chunk_dtd_whole(filepath, rel_path)
        return chunks

    def load_registry(self) -> Dict[str, str]:
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_registry(self, registry: Dict[str, str]):
        try:
            _atomic_write_json(REGISTRY_FILE, registry)
        except Exception as e:
            print(f"Error saving registry: {e}", file=sys.stderr)

    def derive_importance_rating(self, rel_path: str, text: str) -> str:
        """Derive importance rating for metadata tagging."""
        path_lower = rel_path.lower()
        if (
            "agents.md" in path_lower
            or "claude.md" in path_lower
            or "workflow_state.json" in path_lower
            or "feature_list.json" in path_lower
        ):
            return "critical"
        elif "scratch" in path_lower:
            return "low"
        elif "directives" in path_lower and not (
            "concepts" in path_lower or "wiki" in path_lower
        ):
            return "high"
        return "medium"

    def _hash_infos(self, discovered, registry, new_registry, stats, force=False):
        """Hash discovered infos into a to_index list (shared index core)."""
        to_index = []
        for info in discovered:
            path_str = info["path"]
            filepath = Path(path_str)
            if not filepath.exists():
                continue
            try:
                current_hash = self.calculate_sha256(filepath)
                old_hash = registry.get(path_str)
                new_registry[path_str] = current_hash
                if force or old_hash != current_hash:
                    if old_hash is None:
                        stats["new"] += 1
                    else:
                        stats["updated"] += 1
                    to_index.append((info, filepath, old_hash, current_hash))
                else:
                    stats["unchanged"] += 1
            except Exception as e:
                print(f"Failed to hash {path_str}: {e}", file=sys.stderr)
                stats["failed"] += 1
                if path_str in registry:
                    new_registry[path_str] = registry[path_str]
        return to_index

    def _chunk_jobs(self, to_index, new_registry, stats):
        """Pre-chunk every file once; embeddings fan out per model below."""
        jobs = []
        for info, filepath, old_hash, new_hash in to_index:
            if filepath.suffix.lower() in (".dtd", ".mod", ".ent"):
                mode = (
                    os.environ.get("OPENCODE_MEMORY_DTD_CHUNK_MODE", "inventory")
                    .strip()
                    .lower()
                )
                if mode == "markdown":
                    chunks = self.chunk_markdown(filepath, info["rel_path"])
                elif mode == "hybrid":
                    chunks = self.chunk_dtd(filepath, info["rel_path"])
                else:
                    chunks = self.chunk_dtd_whole(filepath, info["rel_path"])
            else:
                chunks = self.chunk_markdown(filepath, info["rel_path"])
            if not chunks:
                stats["failed"] += 1
                if old_hash is None:
                    new_registry.pop(info["path"], None)
                else:
                    new_registry[info["path"]] = old_hash
                continue
            mtime_val = os.path.getmtime(filepath) if filepath.exists() else time.time()
            imp = self.derive_importance_rating(info["rel_path"], "")
            masked = [mask_ndata(c["text"]) for c in chunks]
            hists = [dtype_histogram(c["text"]) for c in chunks]
            nots = [",".join(notations_of(c["text"])) for c in chunks]
            jobs.append(
                (
                    info,
                    filepath,
                    old_hash,
                    new_hash,
                    chunks,
                    mtime_val,
                    imp,
                    masked,
                    hists,
                    nots,
                )
            )
        return jobs

    def _upsert_jobs(self, jobs, to_index, new_registry, stats):
        """Embed and upsert jobs per model; failed paths keep old hashes."""
        models = self.models
        cols = self.collections
        failed_paths = set()
        for slug, col in cols.items():
            model_name = next(
                (n for n in self.embed_model_names if model_slug(n) == slug),
                slug,
            )
            for (
                info,
                filepath,
                old_hash,
                new_hash,
                chunks,
                mtime_val,
                imp,
                masked,
                hists,
                nots,
            ) in jobs:
                if old_hash is not None:
                    try:
                        existing = col.get(where={"source": info["path"]})
                        if existing and existing["ids"]:
                            col.delete(ids=existing["ids"])
                    except Exception as e:
                        print(
                            f"Error purging old chunks for {info['rel_path']}: {e}",
                            file=sys.stderr,
                        )
                ids = [c["chunk_id"] for c in chunks]
                texts = masked
                metadatas = [
                    {
                        "source": info["path"],
                        "rel_path": info["rel_path"],
                        "project": info["project"],
                        "category": info["category"],
                        "subcategory": info["subcategory"],
                        "title": c["title"],
                        "content_hash": new_hash,
                        "linked_concepts": ",".join(c["linked_concepts"]),
                        "created_at": str(mtime_val),
                        "updated_at": str(mtime_val),
                        "last_accessed": str(time.time()),
                        "access_count": "0",
                        "importance": imp,
                        "embed_model": model_name,
                        "dtype_hist": h,
                        "notations": n,
                    }
                    for c, h, n in zip(chunks, hists, nots)
                ]
                try:
                    embeddings = [
                        [float(val) for val in e] for e in models[slug].embed(texts)
                    ]
                    col.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=texts,
                        metadatas=metadatas,
                    )
                except Exception as e:
                    print(
                        f"Failed indexing chunks for {info['rel_path']}: {e}",
                        file=sys.stderr,
                    )
                    stats["failed"] += 1
                    failed_paths.add(info["path"])
        if failed_paths:
            old_by_path = {i["path"]: o for i, _f, o, _n in to_index}
            for col in cols.values():
                for path in failed_paths:
                    try:
                        existing = col.get(where={"source": path})
                        if existing and existing["ids"]:
                            col.delete(ids=existing["ids"])
                    except Exception:
                        pass
            for path in failed_paths:
                if path in old_by_path and old_by_path[path] is not None:
                    new_registry[path] = old_by_path[path]
                else:
                    new_registry.pop(path, None)

    def index_all(
        self, force: bool = False, projects: List[str] | None = None
    ) -> Dict[str, Any]:
        """Scan projects, compute hashes, update vector DB only for new/changed wikis.

        `projects`: scope the walk to these project refs (resolved +
        registered first, so out-of-roots codebases index on first
        touch). Scoped runs hash, upsert AND purge only inside the
        scope; unscoped files are invisible and never deleted. Omit
        for the full broadcast walk.
        """
        refused = self._require_writer("index_all")
        if refused is not None:
            return refused
        wedged = _worker_refusal("index_all")
        if wedged is not None:
            return _empty_index_stats(wedged)
        if force:
            no_charge = _full_reindex_refusal()
            if no_charge is not None:
                return _empty_index_stats(no_charge)
        scope = None
        if projects:
            scope = set()
            for pref in projects or []:
                try:
                    scope.add(os.path.normcase(str(resolve_project_dir(pref))))
                except Exception:
                    pass
        discovered = self.discover_wikis()
        if scope is not None:
            discovered = [i for i in discovered if _in_scope(i["path"], scope)]
        registry = self.load_registry()

        stats = {
            "scanned": len(discovered),
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
        }

        # Track active paths to purge deleted files later
        active_paths = {i["path"] for i in discovered}
        new_registry = {} if scope is None else dict(registry)

        to_index = self._hash_infos(
            discovered, registry, new_registry, stats, force=force
        )

        # Execute indexing for new/changed files, once per embedding model.
        # Each model owns its collection since fixed vector spaces never mix.
        # Waved: chunk+upsert per wave so RAM stays bounded on big scopes.
        if to_index:
            with _INDEX_LOCK:
                for start in range(0, len(to_index), INDEX_WAVE_SIZE):
                    wave = to_index[start : start + INDEX_WAVE_SIZE]
                    jobs = self._chunk_jobs(wave, new_registry, stats)
                    self._upsert_jobs(jobs, wave, new_registry, stats)

        # 3. Detect deleted files and remove them from every RTR collection.
        # Scoped runs purge (and forget) only scoped deletions: unscoped
        # files are invisible to this run and must never be deleted by it.
        missing = set(registry.keys()) - active_paths
        if scope is not None:
            missing = {p for p in missing if _in_scope(p, scope)}
            for p in missing:
                new_registry.pop(p, None)
        self._purge_deleted_paths(missing)

        self.save_registry(new_registry)

        # 4. Seed the lexikon for projects that carry DTD-family files
        # (TODO-37): the amplification is architecture, not bench-only.
        dtd_projects = {
            info.get("project")
            for info, filepath, _o, _n in to_index
            if filepath.suffix.lower() in _DTD_SUFFIXES and info.get("project")
        }
        seeded = 0
        if os.environ.get("OPENCODE_MEMORY_DTD_LEXIKON_SEED", "1").strip() != "0":
            for proj in sorted(dtd_projects):
                try:
                    seeded += self.seed_dtd_lexikon(str(proj))
                except Exception:
                    pass
        stats["lexikon_seeded"] = seeded
        return stats

    def index_files(self, paths: List[str] | None) -> Dict[str, Any]:
        """Index explicit files without discovering the world (RRD-169).

        The auto-indexer's bounded call: only the named paths are hashed,
        chunked, embedded and upserted. Missing, unsuffixed and duplicate
        paths are skipped quietly (a raced delete must never fail the
        run). Never purges (the active set is scoped, not global).
        """
        refused = self._require_writer("index_files")
        if refused is not None:
            return refused
        wedged = _worker_refusal("index_files")
        if wedged is not None:
            return _empty_index_stats(wedged)
        registry = self.load_registry()
        stats = {"scanned": 0, "new": 0, "updated": 0, "unchanged": 0, "failed": 0}
        new_registry = dict(registry)
        infos = []
        seen = set()
        for raw in paths or []:
            path_str = str(raw)
            if path_str in seen:
                continue
            seen.add(path_str)
            filepath = Path(path_str)
            if not filepath.is_file() or not _matches_suffix(filepath.name):
                continue
            key, rel, _root = describe_indexed_path(path_str)
            parts = Path(rel).parts if rel else ()
            is_directive = "directives" in parts
            has_wiki = any("wiki" in part.lower() for part in parts)
            infos.append(
                {
                    "path": path_str,
                    "project": key,
                    "category": "wiki" if has_wiki else "directive",
                    "subcategory": "general",
                    "filename": filepath.name,
                    "rel_path": rel,
                }
            )
        stats["scanned"] = len(infos)
        to_index = self._hash_infos(infos, registry, new_registry, stats)
        if to_index:
            with _INDEX_LOCK:
                for start in range(0, len(to_index), INDEX_WAVE_SIZE):
                    wave = to_index[start : start + INDEX_WAVE_SIZE]
                    jobs = self._chunk_jobs(wave, new_registry, stats)
                    self._upsert_jobs(jobs, wave, new_registry, stats)
        self.save_registry(new_registry)
        return stats

    def repair_registry(self) -> Dict[str, Any]:
        """Rebuild the hash registry from Chroma contents plus disk truth.

        For every chunk source known to any collection: if the file still
        exists, rehash and register it; dead sources are left for janitor
        (which deletes their chunks). Repairs crash-skewed registries
        (2 files over 61k chunks) without re-embedding a single byte.
        """
        refused = self._require_writer("repair_registry")
        if refused is not None:
            return refused
        registry = self.load_registry()
        sources = set()
        seen_cols = set()
        for col in self.rtr_collections().values():
            cname = getattr(col, "name", None)
            if cname in seen_cols:
                continue
            seen_cols.add(cname)
            try:
                total = col.count()
            except Exception:
                continue
            if total == 0:
                continue
            offset = 0
            while offset < total:
                try:
                    got = col.get(
                        limit=JANITOR_PAGE_SIZE,
                        offset=offset,
                        include=["metadatas"],
                    )
                except Exception:
                    break
                metas = got["metadatas"] if got else []
                if not got or not got["ids"]:
                    break
                for meta in metas or []:
                    src = (meta or {}).get("source", "")
                    if src:
                        sources.add(src)
                offset += len(got["ids"])
        fixed = 0
        pre_image = dict(registry)
        for src in sorted(sources):
            if src in registry:
                continue
            p = Path(src)
            if not p.exists():
                continue
            try:
                registry[src] = self.calculate_sha256(p)
                fixed += 1
            except Exception:
                continue
        if fixed:
            try:
                Path(str(REGISTRY_FILE) + ".bak").write_text(
                    json.dumps(pre_image, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
        self.save_registry(registry)
        return {"status": "success", "repaired": fixed, "total": len(registry)}

    def _purge_deleted_paths(self, deleted_paths: set) -> None:
        """Remove deleted files from every RTR collection (configured +
        legacy), verifying so segment desync cannot linger."""
        if not deleted_paths:
            return
        for col in self.rtr_collections().values():
            for path in deleted_paths:
                try:
                    existing = col.get(where={"source": path})
                    if existing and existing["ids"]:
                        col.delete(ids=existing["ids"])
                        print(
                            f"Purged deleted file from index: {path}", file=sys.stderr
                        )
                    again = col.get(where={"source": path})
                    if again and again["ids"]:
                        print(
                            f"WARNING: remnants of {path} persist in "
                            f"{col.name} ({len(again['ids'])} chunks)",
                            file=sys.stderr,
                        )
                except Exception as e:
                    print(f"Error purging deleted file {path}: {e}", file=sys.stderr)

    def compute_bm25_scores(self, query: str, documents: List[str]) -> List[float]:
        """Compute pure-Python BM25 scores for a list of candidate documents."""
        import math

        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        if not query_terms or not documents:
            return [0.0] * len(documents)

        doc_terms_list = []
        for doc in documents:
            doc_terms_list.append([t.lower() for t in re.findall(r"\w+", doc)])

        doc_count = len(documents)
        df = {}
        for terms in doc_terms_list:
            unique_terms = set(terms)
            for term in unique_terms:
                df[term] = df.get(term, 0) + 1

        k1 = 1.5
        b = 0.75
        avg_doc_len = sum(len(terms) for terms in doc_terms_list) / max(doc_count, 1)

        scores = []
        for terms in doc_terms_list:
            score = 0.0
            doc_len = len(terms)
            term_counts = {}
            for term in terms:
                term_counts[term] = term_counts.get(term, 0) + 1

            for q_term in query_terms:
                if q_term in term_counts:
                    n = df.get(q_term, 0)
                    idf = math.log((doc_count - n + 0.5) / (n + 0.5) + 1.0)
                    tf = term_counts[q_term]
                    tf_score = (tf * (k1 + 1)) / (
                        tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
                    )
                    score += idf * tf_score
            scores.append(score)

        max_score = max(scores) if scores else 0
        if max_score > 0:
            scores = [s / max_score for s in scores]
        return scores

    def compute_recency_score(self, created_at_str: str) -> float:
        """Compute an exponential decay recency score based on creation timestamp (half-life of 14 days)."""
        import math

        try:
            created_at = float(created_at_str)
            age_days = (time.time() - created_at) / (24 * 3600)
            return math.exp(-0.05 * max(0.0, age_days))
        except Exception:
            return 1.0

    def compute_importance_score(self, importance_str: str) -> float:
        """Translate metadata importance string into numeric multiplier score."""
        imp = str(importance_str or "").lower()
        if imp == "critical":
            return 1.0
        elif imp == "high":
            return 0.7
        elif imp == "medium":
            return 0.5
        elif imp == "low":
            return 0.2
        return 0.5

    def _fused_candidates(
        self, query: str, k: int = 3, project: str | None = None, hybrid: bool = True
    ) -> List[Dict[str, Any]]:
        """Single-query convenience over _fused_multi (identical math)."""
        return self._fused_multi([query], k=k, project=project, hybrid=hybrid)

    def build_expansions(
        self, query: str, project: str | None = None
    ) -> tuple[List[str], List[str]]:
        """Split expansion into trusted (lexikon) and noisy (delta) lanes.

        Lexikon entries are curated/derived knowledge — they bypass the
        relevance gate. Delta stems are guesses — gated by evidence. The
        lexikon lane is gated by the Optimizer's resolved modality
        `expansion` flag: classic RAG modalities (expansion=false) do not
        expand through the lexikon.
        """
        lex_subs, delta_subs = [], []
        expansion_enabled = True
        try:
            expansion_enabled = bool(_cb.resolve_retrieval_profile()["expansion"])
        except Exception:  # noqa: BLE001
            expansion_enabled = True
        if project:
            if expansion_enabled:
                try:
                    lex = self.lexikon_expansion(project, query)
                    if lex:
                        cand = (query + " " + " ".join(lex)).strip()
                        if cand != query:
                            lex_subs.append(cand)
                except Exception:
                    pass
            try:
                deltas = self.detect_workspace_deltas(project)
                toks: List[str] = []
                for p in (deltas.get("created", []) + deltas.get("modified", []))[:10]:
                    toks.extend(
                        t
                        for t in re.findall(r"\w+", Path(p).stem.lower())
                        if len(t) > 2
                    )
                extra = [t for t in dict.fromkeys(toks) if t not in query.lower()][:8]
                if extra:
                    delta_subs.append(query + " " + " ".join(extra))
            except Exception:
                pass
        return lex_subs, delta_subs

    def build_subqueries(self, query: str, project: str | None = None) -> List[str]:
        """RTR Pillar 1: original + lexikon-expanded + workspace-delta-expanded.

        Lookup-only expansion (registry aliases, glossary definitions, recent
        file-delta stems). Deterministic, no generator model. Note: search()
        and explain_search() use the gated _search_subqueries() instead; this
        raw shape stays for callers that want ungated expansion.
        """
        lex_subs, delta_subs = self.build_expansions(query, project)
        out = [query]
        for s in lex_subs + delta_subs:
            if s not in out:
                out.append(s)
        return out[:4]

    def _fused_multi(
        self,
        subqueries: List[str],
        k: int = 3,
        project: str | None = None,
        hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fuse sub-queries x models with confidence-weighted RRF.

        Each (sub-query, model) run votes 1/(K+rank), weighted by its own
        decisiveness (top-vs-median similarity spread): peaked runs vote
        loudly, flat uncertain runs vote quietly. Unsupervised, per-query,
        no labels. A CDATA exact-match lane adds a bounded bonus for opaque
        query terms (pillar 2).
        """
        subs = [s for s in (subqueries or []) if str(s or "").strip()]
        if not subs:
            return []
        base_query = subs[0]
        cols = self.collections
        counts = {slug: col.count() for slug, col in cols.items()}
        if not cols or max(counts.values()) == 0:
            return []

        candidate_count = min(max(counts.values()), max(20, k * 4))

        where_filter = None
        if project:
            filter_key = project_filter_key(project)
            if filter_key:
                where_filter = {"project": filter_key}

        query_vecs = {q: self.embed_all([q], for_query=True) for q in subs}
        per_doc: Dict[str, Dict[str, Any]] = {}
        run_ranks: List[Dict[str, int]] = []
        run_spreads: List[float] = []
        for q in subs:
            for slug, col in cols.items():
                if counts[slug] == 0:
                    continue
                qv = [[float(v) for v in e] for e in query_vecs[q][slug]][0]
                try:
                    results = col.query(
                        query_embeddings=[qv],
                        n_results=min(candidate_count, counts[slug]),
                        where=where_filter,
                    )
                except Exception as e:
                    print(f"Query failed on {slug}: {e}", file=sys.stderr)
                    continue
                if not results or not results["ids"] or not results["ids"][0]:
                    continue
                ids = results["ids"][0]
                sims = []
                for i, doc_id in enumerate(ids):
                    try:
                        sims.append(1.0 - float(results["distances"][0][i]))
                    except Exception:
                        sims.append(0.0)
                    per_doc.setdefault(
                        doc_id,
                        {
                            "document": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                        },
                    )
                # Decisiveness of this run: top similarity vs median.
                # A flat (uncertain) run votes quietly; a peaked run votes
                # loudly. Unsupervised, per-query, no labels, no tuning.
                ordered = sorted(sims, reverse=True)
                spread = max(ordered[0] - ordered[len(ordered) // 2], 1e-9)
                run_ranks.append({doc_id: i + 1 for i, doc_id in enumerate(ids)})
                run_spreads.append(spread)

        if not per_doc:
            return []

        rrf_k = configured_rrf_k()
        # Vote truncation (measured 2026-10-26, versus intense): a weak
        # model voting over the full corpus tail drags the fusion below
        # its best member (arctic 0.183 on dtd-commands vs bge 0.498,
        # full 0.460). Only top-VOTE_TOP ranks vote; tail ranks are noise
        # with a ballot. 0 disables truncation.
        try:
            vote_top = int(os.environ.get("OPENCODE_MEMORY_RRF_VOTE_TOP", "10"))
        except Exception:
            vote_top = 10
        total_spread = sum(run_spreads) or 1.0
        # Consensus weighting (TODO-31): a run whose top ranks disagree with
        # the other runs is likely a confidently-wrong model (measured:
        # arctic-m on dtd-commands votes confidently wrong and drags the
        # fusion below its best member). Down-weight such runs. Single-run
        # fusions (one model, one subquery) keep full weight.
        try:
            consensus_on = (
                os.environ.get("OPENCODE_MEMORY_RRF_CONSENSUS", "0").strip() == "1"
            )
        except Exception:
            consensus_on = False
        run_consensus = (
            _compute_run_consensus(run_ranks)
            if consensus_on
            else [1.0] * len(run_ranks)
        )
        raw_rrf: Dict[str, float] = {doc_id: 0.0 for doc_id in per_doc}
        for doc_ranks, spread, cw in zip(run_ranks, run_spreads, run_consensus):
            w = spread / total_spread * cw
            for doc_id, r in doc_ranks.items():
                if vote_top > 0 and r > vote_top:
                    continue
                raw_rrf[doc_id] = raw_rrf.get(doc_id, 0.0) + w / (rrf_k + r)
        lo, hi = min(raw_rrf.values()), max(raw_rrf.values())
        span = hi - lo

        doc_texts = [v["document"] for v in per_doc.values()]
        bm25_scores = (
            self.compute_bm25_scores(base_query, doc_texts)
            if hybrid
            else [0.0] * len(doc_texts)
        )
        # Lane decisiveness: a standout lexical match takes the lead over
        # dense; a generic field keeps default weights. See
        # hybrid_lane_weights for the statistic and its measured history.
        w_dense, w_bm25 = hybrid_lane_weights(bm25_scores) if hybrid else (0.45, 0.30)
        if hybrid:
            weights = {
                "dense": w_dense,
                "bm25": w_bm25,
                "recency": 0.15,
                "importance": 0.10,
            }
        else:
            weights = {"dense": 1.0, "bm25": 0.0, "recency": 0.0, "importance": 0.0}
        q_cdata = cdata_terms_of(base_query)
        # STRUCT lane (TODO-15): code-shaped terms may earn bounded
        # structural evidence over candidate sources. Default off; an
        # absent backend or zero hits merges every term back into the
        # exact lane, reproducing the legacy bonus (lane_off_identity).
        exact_terms, struct_terms, struct_pattern, struct_map = (
            list(q_cdata),
            [],
            None,
            {},
        )
        lane_mode = struct_lane_mode()
        if lane_mode != "off":
            e_terms, s_terms, s_pattern = classify_query_terms(base_query)
            if s_terms or s_pattern:
                sources = list(
                    dict.fromkeys(
                        str(v["metadata"].get("source") or "") for v in per_doc.values()
                    )
                )
                struct_map = structural_hits(
                    s_terms, s_pattern, sources, backend=lane_mode
                )
                if struct_map:
                    exact_terms, struct_terms, struct_pattern = (
                        e_terms,
                        s_terms,
                        s_pattern,
                    )
        total_terms = (
            len(exact_terms) + len(struct_terms) + (1 if struct_pattern else 0)
        )

        fused = []
        for (doc_id, v), sparse in zip(per_doc.items(), bm25_scores):
            dense = (raw_rrf[doc_id] - lo) / span if span > 0 else 1.0
            meta = v["metadata"]
            recency = self.compute_recency_score(
                meta.get("created_at", str(time.time()))
            )
            importance = self.compute_importance_score(meta.get("importance", "medium"))
            if hybrid:
                final = (
                    (w_dense * dense)
                    + (w_bm25 * sparse)
                    + (0.15 * recency)
                    + (0.10 * importance)
                )
            else:
                final = dense
            struct_hits_here = struct_map.get(str(meta.get("source") or ""), [])
            if total_terms:
                hay = str(v["document"]).lower()
                e_hits = sum(1 for t in exact_terms if t in hay)
                s_terms_hit = {h.get("term") for h in struct_hits_here}
                s_hits = len(s_terms_hit & set(struct_terms)) + (
                    1 if struct_pattern and "pattern" in s_terms_hit else 0
                )
                if e_hits + s_hits:
                    # Disjoint lanes: e_hits + s_hits <= total_terms, so
                    # the shared cap bounds the lift (bonus_bounded).
                    final = min(
                        1.0,
                        final + EXACT_LANE_WEIGHT * (e_hits + s_hits) / total_terms,
                    )
            fused.append(
                {
                    "id": doc_id,
                    "document": v["document"],
                    "metadata": meta,
                    "dense": dense,
                    "sparse": sparse,
                    "recency": recency,
                    "importance": importance,
                    "struct_hits": len(struct_hits_here),
                    "score": final,
                    "weights": weights,
                }
            )
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused

    @staticmethod
    def _resolve_hybrid(hybrid: bool | None) -> bool:
        """Explicit bool wins; None resolves the Optimizer profile's flag."""
        if hybrid is not None:
            return hybrid
        try:
            return bool(_cb.resolve_retrieval_profile()["hybrid"])
        except Exception:  # noqa: BLE001
            return True

    def _search_subqueries(
        self, query: str, project: str | None, k: int, hybrid: bool
    ) -> List[str]:
        """Sub-queries exactly as search() builds them: original +
        lexikon-expanded (curated, ungated) + workspace-delta-expanded
        (gated by top-2 evidence) + optional PRF expansion. Shared by
        search() and explain_search() so the explanation always
        describes the ranking search returns.
        """
        lex_subs, delta_subs = self.build_expansions(query, project)
        subs = [query] + [s for s in lex_subs if s != query]
        # Relevance gate (delta lane only): a delta-guess subquery votes only
        # if at least one of its added terms appears in the top-2
        # original-query docs. Lexikon subs are curated knowledge and bypass.
        # Without evidence a guess is drift, not expansion — bench proved it.
        first = []
        if delta_subs:
            try:
                first = self._fused_multi([query], k=k, project=project, hybrid=hybrid)[
                    :2
                ]
            except Exception:
                first = []
        if delta_subs and first:
            qtok = set(query.lower().split())
            hay = " ".join(str(f["document"]) for f in first).lower()
            for s in delta_subs:
                added = [t for t in s.lower().split() if t not in qtok]
                if added and any(t in hay for t in added) and s not in subs:
                    subs.append(s)
        if os.environ.get("OPENCODE_MEMORY_PRF", "0").strip() == "1":
            try:
                first = self._fused_multi(subs, k=k, project=project, hybrid=hybrid)[:2]
                toks: List[str] = []
                for f in first:
                    toks.extend(
                        t
                        for t in re.findall(
                            r"\w+", str(f["metadata"].get("title", "")).lower()
                        )
                        if len(t) > 2
                    )
                extra = [t for t in dict.fromkeys(toks) if t not in query.lower()][:8]
                if extra:
                    cand = query + " " + " ".join(extra)
                    if cand not in subs:
                        subs = subs + [cand]
            except Exception:
                pass
        return subs

    def search(
        self,
        query: str,
        k: int = 3,
        project: str | None = None,
        hybrid: bool | None = None,
    ) -> List[Dict[str, Any]]:
        """Semantic/Hybrid search across indexed wikis with Recency & Importance weighting (v2).

        RTR: multi-query expansion (pillar 1) fused over models with RRF,
        plus an optional PRF second pass (OPENCODE_MEMORY_PRF=1).

        hybrid=None means the Optimizer's resolved modality decides (its
        `hybrid` flag); an explicit bool always wins. The bench and CLI
        pass explicit values; only the default is profile-driven.
        """
        hybrid = self._resolve_hybrid(hybrid)
        subs = self._search_subqueries(query, project, k, hybrid)
        try:
            fused = self._fused_multi(subs, k=k, project=project, hybrid=hybrid)
        except Exception as e:
            if "hnsw" in str(e).lower():
                _quarantine_corrupt_index(f"search hnsw failure: {e}")
            raise
        if not fused:
            return []

        formatted = [
            {
                "id": f["id"],
                "document": f["document"],
                "metadata": f["metadata"],
                "score": f["score"],
            }
            for f in fused[:k]
        ]

        # Expand sources using Obsidian wikilinks (across all model collections)
        seen_ids = {f["id"] for f in formatted}
        for res in list(formatted):
            links = res["metadata"].get("linked_concepts", "")
            if not links:
                continue
            for concept in links.split(","):
                concept = concept.strip()
                if not concept:
                    continue
                for col in self.collections.values():
                    try:
                        linked = col.get(where_document={"$contains": concept})
                    except Exception:
                        continue
                    if linked and linked["ids"]:
                        for j, linked_id in enumerate(linked["ids"]):
                            if linked_id in seen_ids:
                                continue
                            is_rel = linked["metadatas"][j].get("rel_path", "") != res[
                                "metadata"
                            ].get("rel_path", "")
                            if not is_rel:
                                continue
                            seen_ids.add(linked_id)
                            formatted.append(
                                {
                                    "id": linked_id,
                                    "document": linked["documents"][j],
                                    "metadata": linked["metadatas"][j],
                                    "score": res["score"] * 0.9,
                                }
                            )

        return formatted

    def explain_search(
        self,
        query: str,
        k: int = 3,
        project: str | None = None,
        hybrid: bool | None = None,
    ) -> List[Dict[str, Any]]:
        """Explain search query ranking parameters with detailed mathematical score breakdowns.

        The `dense` column is the min-max normalized RRF across configured models.
        Sub-queries and hybrid resolution mirror search() exactly, so the
        breakdown always describes the ranking search returns.
        """
        hybrid = self._resolve_hybrid(hybrid)
        fused = self._fused_multi(
            self._search_subqueries(query, project, k, hybrid),
            k=k,
            project=project,
            hybrid=hybrid,
        )
        if not fused:
            return []

        formatted = []
        for f in fused[:k]:
            meta = f["metadata"]
            formatted.append(
                {
                    "rel_path": meta["rel_path"],
                    "title": meta.get("title", "Unknown"),
                    "dense": f["dense"],
                    "bm25": f["sparse"],
                    "recency": f["recency"],
                    "importance": f["importance"],
                    "final": f["score"],
                    "weights": f["weights"],
                }
            )

        formatted.sort(key=lambda x: x["final"], reverse=True)
        return formatted[:k]

    def write_wiki(
        self, project: str, filename: str, content: str
    ) -> Tuple[str, List[str]]:
        """Write new wiki entry to project directives folder and auto-link related docs."""
        project_dir = resolve_project_dir(project)
        if not project_dir.exists():
            raise ValueError(f"Project directory {project_dir} does not exist.")

        directives_dir = project_dir / "directives"

        # Check if wiki_concepts exists inside directives, otherwise write directly in directives
        concepts_dir = directives_dir / "wiki_concepts"
        if concepts_dir.exists():
            target_dir = concepts_dir
        else:
            target_dir = directives_dir
            target_dir.mkdir(parents=True, exist_ok=True)

        filename = safe_concept_filename(filename)

        filepath = target_dir / filename

        # Clean markdown formatting (normalize line breaks, etc.)
        content = content.strip()

        # Step 1: Write initial content to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # Step 2: Temporarily index this file so we can find links, OR search before indexing it
        # Actually, let's search for related documents across ALL projects first
        related_links = []
        try:
            # Rebuild index of all OTHER files first to ensure search is fresh
            self.index_all()

            # Search using the title/intro of the new wiki entry
            # Extract first 200 chars or title
            search_query = filename.replace(".md", "").replace("_", " ")
            search_results = self.search(query=search_query, k=4, project=None)

            # Filter results to find highly relevant docs (score > 0.50) and exclude the file itself
            seen_paths = set()
            for res in search_results:
                src_path = Path(res["metadata"]["source"])
                if src_path == filepath:
                    continue

                score = res["score"]
                if score > 0.50 and src_path not in seen_paths:
                    seen_paths.add(src_path)

                    # Calculate relative path from target_dir to src_path
                    try:
                        # Find path relative to PROJECTS_DIR or just a clean relative path
                        # If both are in projects, we can compute relative path
                        rel_link = os.path.relpath(src_path, start=target_dir)
                        # Normalize path separators for markdown
                        rel_link = rel_link.replace("\\", "/")
                        related_links.append(
                            f"- [{src_path.name}]({rel_link}) (Similarity: {score:.2f})"
                        )
                    except Exception:
                        related_links.append(
                            f"- [{src_path.name}](file://{src_path.as_posix()}) (Similarity: {score:.2f})"
                        )
        except Exception as e:
            print(f"Auto-linking failed: {e}", file=sys.stderr)

        # Step 3: Append related docs section if any found
        if related_links:
            related_section = (
                "\n\n## Related Knowledge\n" + "\n".join(related_links) + "\n"
            )
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(related_section)

        # Step 4: Re-index specifically to get the final chunk with related links
        self.index_all()

        return str(filepath), related_links

    def janitor(self, dry_run: bool = False) -> Dict[str, Any]:
        """Delete chunks whose source files no longer exist on disk.

        Catches orphans the hash-registry purge cannot see (model switches,
        deleted temp projects). Reports per-collection freed counts.
        """
        report: Dict[str, Any] = {"collections": {}, "freed": 0, "dry_run": dry_run}
        seen_cols = set()
        for name, col in self.rtr_collections().items():
            cname = getattr(col, "name", name)
            if cname in seen_cols:
                continue
            seen_cols.add(cname)
            try:
                total = col.count()
            except Exception:
                continue
            if total == 0:
                report["collections"][name] = {"chunks": 0, "freed": 0}
                continue
            # Paginated scan: one giant get() exceeds SQLite's variable
            # limit on big collections (measured: arctic 57k errors).
            by_source: Dict[str, List[str]] = {}
            offset = 0
            failed = None
            while offset < total:
                try:
                    got = col.get(
                        limit=JANITOR_PAGE_SIZE,
                        offset=offset,
                        include=["metadatas"],
                    )
                except Exception as e:
                    failed = str(e)
                    break
                ids = got["ids"] if got else []
                if not ids:
                    break
                for cid, meta in zip(ids, got["metadatas"] or []):
                    src = (meta or {}).get("source", "")
                    by_source.setdefault(src, []).append(cid)
                offset += len(ids)
            if failed is not None:
                report["collections"][name] = {"error": failed}
                continue
            freed = 0
            for src, ids in by_source.items():
                if src and not Path(src).exists():
                    if not dry_run:
                        try:
                            col.delete(ids=ids)
                        except Exception:
                            continue
                    freed += len(ids)
            report["collections"][name] = {"chunks": total, "freed": freed}
            report["freed"] += freed
        pruned_roots: List[str] = []
        unmounted_roots: List[str] = []
        known = _load_extra_roots()
        kept = []
        for root in known:
            if root.exists():
                kept.append(root)
                continue
            # A missing root on a missing drive is unmounted, not dead:
            # pruning it would drop a live project between remounts.
            anchor = root.drive if os.name == "nt" else "/"
            if os.name == "nt" and anchor and not Path(anchor + os.sep).exists():
                unmounted_roots.append(str(root))
                kept.append(root)
                continue
            pruned_roots.append(str(root))
        if pruned_roots and not dry_run:
            try:
                _atomic_write_json(EXTRA_ROOTS_FILE, [str(k) for k in kept])
            except Exception as e:
                print(f"Error pruning extra roots: {e}", file=sys.stderr)
        report["pruned_roots"] = pruned_roots
        report["unmounted_roots"] = unmounted_roots
        return report

    def stats(self) -> Dict[str, Any]:
        """Retrieve corpus stats (chunk counts summed across model collections)."""
        registry = self.load_registry()

        total_chunks = sum(col.count() for col in self.collections.values())
        total_files = len(registry)

        project_counts = {}
        for path, _ in registry.items():
            key, _, _ = describe_indexed_path(path)
            project_counts[key] = project_counts.get(key, 0) + 1

        db_size_bytes = 0
        db_home = _db_dir()
        if db_home.exists():
            for f in db_home.glob("**/*"):
                if f.is_file():
                    db_size_bytes += f.stat().st_size

        return {
            "total_files": total_files,
            "total_chunks": total_chunks,
            "projects": project_counts,
            "db_size_mb": db_size_bytes / (1024 * 1024),
        }

    def consolidate_wiki(self, project: str) -> Dict[str, Any]:
        """Deduplicate and consolidate redundant wiki markdown files under a project's directives/wiki_concepts or design_wiki_concepts."""

        project_dir = resolve_project_dir(project)
        if not project_dir.exists():
            return {
                "status": "error",
                "message": f"Project directory {project_dir} does not exist.",
            }

        directives_dir = project_dir / "directives"
        concepts_dir = directives_dir / "wiki_concepts"
        if not concepts_dir.exists():
            concepts_dir = directives_dir / "design_wiki_concepts"

        if not concepts_dir.exists():
            return {
                "status": "error",
                "message": "No wiki_concepts/ or design_wiki_concepts/ directory found.",
            }

        md_files = list(concepts_dir.glob("**/*.md"))
        if len(md_files) < 2:
            return {
                "status": "success",
                "message": "Fewer than 2 concept files. No consolidation needed.",
                "merged": [],
            }

        merged_count = 0
        merged_details = []

        file_contents = {}
        for f in md_files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    file_contents[f] = file.read()
            except Exception:
                pass

        already_merged = set()
        for i in range(len(md_files)):
            f1 = md_files[i]
            if f1 in already_merged or f1 not in file_contents:
                continue

            for j in range(i + 1, len(md_files)):
                f2 = md_files[j]
                if f2 in already_merged or f2 not in file_contents:
                    continue

                stem1 = f1.stem.lower().replace("_", " ").replace("-", " ")
                stem2 = f2.stem.lower().replace("_", " ").replace("-", " ")

                words1 = set(re.findall(r"\w+", stem1))
                words2 = set(re.findall(r"\w+", stem2))
                common_words = words1.intersection(words2)

                is_duplicate = False
                if (
                    len(common_words) >= min(len(words1), len(words2))
                    and len(common_words) > 0
                ):
                    is_duplicate = True

                if is_duplicate:
                    # Target the file with the shorter filename as the master concept
                    if len(f1.name) > len(f2.name):
                        f1, f2 = f2, f1

                    content1 = file_contents[f1].strip()
                    content2 = file_contents[f2].strip()

                    merged_content = f"{content1}\n\n## Consolidated Concept: {f2.stem.replace('_', ' ').title()}\n{content2}"

                    try:
                        with open(f1, "w", encoding="utf-8") as file:
                            file.write(merged_content)

                        f2.unlink()
                        already_merged.add(f2)

                        merged_count += 1
                        merged_details.append(
                            f"Merged duplicate {f2.name} into {f1.name}"
                        )
                        file_contents[f1] = merged_content
                    except Exception as e:
                        print(f"Error merging {f2} into {f1}: {e}", file=sys.stderr)

        if merged_count > 0:
            self.index_all(force=True)

        return {
            "status": "success",
            "message": f"Consolidated {merged_count} duplicate wiki documents.",
            "merged": merged_details,
        }

    def init_project(self, project_name: str, variant: str = "wiki") -> Dict[str, Any]:
        """Bootstrap the Harness Engineering Framework structure in a new or existing project folder."""
        project_dir = resolve_project_dir(project_name)

        # 1. Create Directories
        dirs_to_create = [
            project_dir / "directives",
            project_dir
            / "directives"
            / ("wiki_concepts" if variant == "wiki" else "design_wiki_concepts"),
            project_dir / "execution" / "core",
            project_dir / "execution" / "utils",
            project_dir / "execution" / "scratch",
            project_dir / "state",
            project_dir / "project",
        ]

        created_dirs = []
        for d in dirs_to_create:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created_dirs.append(
                    str(
                        describe_indexed_path(str(d))[1] if d != project_dir else d.name
                    )
                )

        # 2. Write standard documents
        files_written = []

        agents_md = project_dir / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text(
                f"# Harness Engineering Framework — {project_name}\n\nMUST read at EVERY session start AND end.\n\n## Project Overview\nThis repository contains the {project_name} workspace structured under a deterministic 3-layer architecture.\n\n## Lifecycle Status\n| Phase | Status | Description |\n|---|---|---|\n| PHASE_ONE | `[ ]` Pending | Initialization and Setup |\n\n## Lifecycle Protocol\n- **Start:** Read `directives/progress.md` and `directives/session-handoff.md`\n- **End:** Save learnings to inbox, run wiki maintainer, and update `directives/progress.md`\n",
                encoding="utf-8",
            )
            files_written.append("AGENTS.md")

        claude_md = project_dir / "CLAUDE.md"
        if not claude_md.exists():
            claude_md.write_text(
                "# CLAUDE.md\nRefer to [AGENTS.md](AGENTS.md) for workspace lifecycle details.\n",
                encoding="utf-8",
            )
            files_written.append("CLAUDE.md")

        # Create wiki inbox
        inbox_name = "wiki_inbox.md" if variant == "wiki" else "design_wiki.md"
        inbox_file = project_dir / "directives" / inbox_name
        if not inbox_file.exists():
            label = "Wiki Inbox" if variant == "wiki" else "Design Wiki Inbox"
            inbox_file.write_text(
                f"# {label}\n\nAppend raw lessons, API observations, and style guidelines here.\n",
                encoding="utf-8",
            )
            files_written.append(f"directives/{inbox_name}")

        # Create progress.md
        progress_file = project_dir / "directives" / "progress.md"
        if not progress_file.exists():
            progress_file.write_text(
                f"# Project Progress Log — {project_name}\n\n- **{time.strftime('%Y-%m-%d')}:** System bootstrapped using Local-Memory-RAG MCP bootstrapper.\n",
                encoding="utf-8",
            )
            files_written.append("directives/progress.md")

        # Create session-handoff.md
        handoff_file = project_dir / "directives" / "session-handoff.md"
        if not handoff_file.exists():
            handoff_file.write_text(
                "# Session Handoff\n\n## Next Action\nComplete phase one requirements.\n\n## CLI Startup Commands\n`make check`\n",
                encoding="utf-8",
            )
            files_written.append("directives/session-handoff.md")

        # Create state files
        state_file = project_dir / "state" / "workflow_state.json"
        if not state_file.exists():
            import json

            state_data = {
                "current_phase": "PHASE_ONE",
                "completed_steps": [],
                "history": [],
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)
            files_written.append("state/workflow_state.json")

        feature_file = project_dir / "state" / "feature_list.json"
        if not feature_file.exists():
            import json

            feature_data = {
                "phases": [
                    {"id": "PHASE_ONE", "name": "System Setup", "completed": False}
                ]
            }
            with open(feature_file, "w", encoding="utf-8") as f:
                json.dump(feature_data, f, indent=2)
            files_written.append("state/feature_list.json")

        # Create bootstrap scripts
        init_sh = project_dir / "init.sh"
        if not init_sh.exists():
            init_sh.write_text(
                '#!/bin/bash\n# Bootstrap virtual environment and workspace\necho "Bootstrapping Harness environment..."\npython3 -m venv .venv\nsource .venv/bin/activate\nif [ -f requirements.txt ]; then\n  pip install -r requirements.txt\nfi\necho "Workspace bootstrap complete."\n',
                encoding="utf-8",
            )
            try:
                os.chmod(init_sh, 0o755)
            except Exception:
                pass
            files_written.append("init.sh")

        gitignore = project_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                ".venv/\n.tmp/\n.env\n__pycache__/\n", encoding="utf-8"
            )
            files_written.append(".gitignore")

        return {
            "status": "success",
            "message": f"Successfully initialized Harness framework in {project_name}.",
            "created_directories": created_dirs,
            "created_files": files_written,
        }

    def restore_session_state(self, project: str) -> Dict[str, Any]:
        """Session Restoration Engine (Phase 1): Parses Harness state logs and auto-restores context."""
        project_dir = resolve_project_dir(project)
        if not project_dir.exists():
            return {
                "status": "error",
                "message": f"Project directory {project_dir} does not exist.",
            }

        directives = project_dir / "directives"
        state = project_dir / "state"

        progress = directives / "progress.md"
        handoff = directives / "session-handoff.md"
        goals = state / "current-goals.md"
        issues = state / "open-issues.md"
        decisions = state / "active-decisions.md"

        active_goals = []
        blockers = []
        discoveries = []
        full_content = ""

        def parse_items(filepath, only_bullet_points=True):
            if not filepath.exists():
                return []
            try:
                content = filepath.read_text(encoding="utf-8")
                items = []
                for line in content.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if only_bullet_points:
                        if line.startswith("-"):
                            clean = re.sub(r"^-\s*(?:\[[ xX/]\])?\s*", "", line)
                            if clean.strip():
                                items.append(clean.strip())
                    else:
                        clean = re.sub(r"^-\s*(?:\[[ xX/]\])?\s*", "", line)
                        if clean.strip():
                            items.append(clean.strip())
                return items
            except Exception:
                return []

        if goals.exists():
            active_goals.extend(parse_items(goals, only_bullet_points=True))
            full_content += goals.read_text(encoding="utf-8")
        elif handoff.exists():
            handoff_content = handoff.read_text(encoding="utf-8")
            match = re.search(
                r"## Next Action\s*\n\s*(?:-\s*)?([^\n#]+)", handoff_content
            )
            if match:
                active_goals.append(match.group(1).strip())
            full_content += handoff_content

        if issues.exists():
            blockers.extend(parse_items(issues, only_bullet_points=True))
            full_content += issues.read_text(encoding="utf-8")

        if decisions.exists():
            discoveries.extend(parse_items(decisions, only_bullet_points=False))
            full_content += decisions.read_text(encoding="utf-8")

        if not discoveries:
            try:
                sessions_dir = directives / "sessions"
                if sessions_dir.exists():
                    reports = sorted(
                        sessions_dir.glob("*.md"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if reports:
                        items = parse_items(reports[0], only_bullet_points=True)
                        discoveries.extend(
                            [i for i in items if not re.fullmatch(r"-+", i.strip())][:5]
                        )
            except Exception:
                pass

        if progress.exists():
            full_content += "\n" + progress.read_text(encoding="utf-8")

        keywords = " ".join(re.findall(r"\w+", full_content.strip())[:15])

        if not keywords:
            try:
                sessions_dir = directives / "sessions"
                if sessions_dir.exists():
                    reports = sorted(
                        sessions_dir.glob("*.md"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if reports:
                        full_content += (
                            "\n" + reports[0].read_text(encoding="utf-8")[:2000]
                        )
                        keywords = " ".join(
                            re.findall(r"\w+", full_content.strip())[:15]
                        )
            except Exception:
                pass

        recommended_files = []
        if keywords:
            try:
                results = self.search(keywords, k=4, project=project)
                recommended_files = [res["metadata"]["rel_path"] for res in results]
            except Exception:
                pass

        return {
            "status": "success",
            "project": project,
            "active_goals": active_goals[:5],
            "blockers": blockers[:5],
            "recent_discoveries": discoveries[:5],
            "recommended_files": recommended_files,
            "query_context": keywords[:60],
        }

    def _get_wiki_paths(self, project: str) -> Dict[str, Any]:
        """Detect wiki naming convention for a project."""
        directives = resolve_project_dir(project) / "directives"
        design_concepts = directives / "design_wiki_concepts"
        wiki_concepts = directives / "wiki_concepts"

        if design_concepts.exists():
            return {
                "inbox": directives / "design_wiki.md",
                "concepts": design_concepts,
                "variant": "design_wiki",
            }
        return {
            "inbox": directives / "wiki_inbox.md",
            "concepts": wiki_concepts,
            "variant": "wiki",
        }

    def detect_workspace_deltas(self, project: str) -> Dict[str, List[str]]:
        """Scan project's directives/ for any new, modified, or deleted files compared to wiki_registry.json."""
        project_dir = resolve_project_dir(project)
        if not project_dir.exists():
            return {"created": [], "modified": [], "deleted": []}

        directives_dir = project_dir / "directives"
        registry = self.load_registry()

        discovered_paths = set()
        created = []
        modified = []

        if directives_dir.exists():
            for root, _, files in os.walk(directives_dir):
                root_path = Path(root)
                # Skip common noise dirs
                if any(part in root_path.parts for part in _NOISE_DIRS):
                    continue
                for file in files:
                    if not _matches_suffix(file):
                        continue
                    file_path = root_path / file
                    path_str = str(file_path)
                    discovered_paths.add(path_str)

                    if not file_path.exists():
                        continue

                    current_hash = self.calculate_sha256(file_path)
                    old_hash = registry.get(path_str)

                    if old_hash is None:
                        created.append(path_str)
                    elif old_hash != current_hash:
                        modified.append(path_str)

        # Detect deleted files for this project
        deleted = []
        want_key = project_filter_key(project)
        for path_str in registry.keys():
            key, rel, _ = describe_indexed_path(path_str)
            if (want_key is None or key == want_key) and "directives" in rel:
                if path_str not in discovered_paths:
                    deleted.append(path_str)

        return {"created": created, "modified": modified, "deleted": deleted}

    def reflect_session(
        self, project: str, conversation_text: str = ""
    ) -> Dict[str, Any]:
        """Perform Session Reflection. Scans workspace deltas and extracts event-driven knowledge events."""
        deltas = self.detect_workspace_deltas(project)

        knowledge_events = []

        # 1. Automatically classify concepts from workspace file deltas
        for path_str in deltas["created"]:
            p = Path(path_str)
            if "wiki_concepts" in p.parts or "design_wiki_concepts" in p.parts:
                concept_name = p.stem.replace("_", " ").replace("-", " ").title()
                knowledge_events.append(
                    {
                        "type": "decision",
                        "concept": concept_name,
                        "evidence": f"Created concept node: {p.name}",
                        "confidence": 1,
                    }
                )

        for path_str in deltas["modified"]:
            p = Path(path_str)
            if "wiki_concepts" in p.parts or "design_wiki_concepts" in p.parts:
                concept_name = p.stem.replace("_", " ").replace("-", " ").title()
                knowledge_events.append(
                    {
                        "type": "observation",
                        "concept": concept_name,
                        "evidence": f"Modified concept node: {p.name}",
                        "confidence": 1,
                    }
                )

        # 2. Try parsing structured data from conversation_text (JSON / YAML / Markdown sections)
        parsed_structured = False
        text_clean = conversation_text.strip()

        # Check for JSON
        if text_clean.startswith("{") and text_clean.endswith("}"):
            try:
                data = json.loads(text_clean)
                if "knowledge_events" in data:
                    knowledge_events.extend(data["knowledge_events"])
                    parsed_structured = True
            except Exception:
                pass

        # Check for YAML-like list block of knowledge_events
        if not parsed_structured:
            events_match = re.findall(
                r"-\s*type:\s*(\w+)\s*\n\s*concept:\s*([^\n]+)(?:\s*\n\s*evidence:\s*([^\n]+))?",
                conversation_text,
            )
            if events_match:
                for t, c, ev in events_match:
                    knowledge_events.append(
                        {
                            "type": t.strip(),
                            "concept": c.strip(),
                            "evidence": ev.strip() if ev else "Session logs",
                            "confidence": 1,
                        }
                    )
                parsed_structured = True

        # Heuristic extraction if raw unformatted text
        if not parsed_structured and conversation_text:
            sentences = re.split(r"[.!?\n]+", conversation_text)
            registry = None  # lazy: loaded once, only if an unquoted sentence needs it
            for s in sentences:
                s_clean = s.strip()
                if not s_clean or len(s_clean) < 10:
                    continue

                lower_s = s_clean.lower()
                event_type = None

                if any(
                    k in lower_s
                    for k in ["we think", "we believe", "it might", "hypothesis"]
                ):
                    event_type = "hypothesis"
                elif any(
                    k in lower_s
                    for k in ["we tested", "we tried", "testing", "experiment"]
                ):
                    event_type = "experiment"
                elif any(
                    k in lower_s
                    for k in [
                        "improved",
                        "success",
                        "confirmed",
                        "validated",
                        "validation",
                    ]
                ):
                    event_type = "validation"
                elif any(
                    k in lower_s
                    for k in ["failed", "bug", "error", "produced noisy", "failure"]
                ):
                    event_type = "failure"
                elif any(k in lower_s for k in ["we decided", "let's use", "decision"]):
                    event_type = "decision"
                elif any(
                    k in lower_s
                    for k in [
                        "deprecated",
                        "no longer recommended",
                        "retired",
                        "deprecation",
                    ]
                ):
                    event_type = "deprecation"
                elif any(
                    k in lower_s
                    for k in [
                        "observed",
                        "noticed",
                        "discovered",
                        "learned",
                        "observation",
                    ]
                ):
                    event_type = "observation"

                if event_type:
                    matched_concept = "General Learning"
                    quoted = re.findall(r"['\"`]([^'\n`\"]+)['\"`]", s_clean)
                    if quoted:
                        matched_concept = quoted[0].title()
                    else:
                        if registry is None:
                            registry = self._load_concept_registry(project)
                        for cid, data in registry.items():
                            cname = data["canonical_name"].lower()
                            if cname.replace("-", " ") in lower_s:
                                matched_concept = data["canonical_name"].title()
                                break
                            for alias in data.get("aliases", []):
                                if alias.lower() in lower_s:
                                    matched_concept = alias.title()
                                    break

                    knowledge_events.append(
                        {
                            "type": event_type,
                            "concept": matched_concept,
                            "evidence": s_clean,
                            "confidence": 1,
                        }
                    )

        # Deduplicate events
        seen_events = set()
        deduped_events = []
        for ev in knowledge_events:
            key = (ev["type"].lower(), ev["concept"].lower(), ev["evidence"].lower())
            if key not in seen_events:
                seen_events.add(key)
                deduped_events.append(ev)

        # Write Session Learning Report
        project_dir = resolve_project_dir(project)
        sessions_dir = project_dir / "directives" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        date_str = time.strftime("%Y-%m-%d")
        report_file = sessions_dir / f"{date_str}.md"

        if report_file.exists():
            report_file = sessions_dir / f"{date_str}_{int(time.time() % 100000)}.md"

        import yaml

        yaml_content = yaml.dump(
            {"knowledge_events": deduped_events}, default_flow_style=False
        )

        report_content = f"""---
date: {date_str}
project: {project}
---
# Session Learning Report — {date_str}

## Knowledge Events
```yaml
{yaml_content.strip()}
```
"""
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        return {
            "status": "success",
            "report_path": str(report_file),
            "knowledge_events": deduped_events,
        }

    def _load_concept_registry(self, project: str) -> Dict[str, Any]:
        """Load project's state/concept_registry.json."""
        project_dir = resolve_project_dir(project)
        reg_file = project_dir / "state" / "concept_registry.json"
        if reg_file.exists():
            try:
                with open(reg_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_concept_registry(self, project: str, registry: Dict[str, Any]):
        """Save project's state/concept_registry.json."""
        project_dir = resolve_project_dir(project)
        reg_file = project_dir / "state" / "concept_registry.json"
        try:
            _atomic_write_json(reg_file, registry)
        except Exception as e:
            print(f"Error saving concept registry: {e}", file=sys.stderr)

    # --- RTR Pillar 3: Lexikon/Glossary ---
    # Lookup-first terminology: canonical terms + aliases + definitions, merged
    # from the _global user lexikon and the project's own. Query expansion
    # becomes a lookup, not inference — the models stay chilly.
    def _lexikon_files_for(self, project: str) -> List[Path]:
        files = [LEXIKON_GLOBAL_FILE]
        if str(project or "").strip() not in ("", "_global"):
            try:
                d = resolve_project_dir(project)
                if d.exists():
                    files.append(d / "state" / "lexikon.json")
            except Exception:
                pass
        return files

    @staticmethod
    def _read_lexikon_file(fp: Path) -> Dict[str, Any]:
        try:
            if fp.exists():
                data = json.loads(fp.read_text(encoding="utf-8"))
                terms = data.get("terms") or {}
                return {str(k).lower(): v for k, v in terms.items()}
        except Exception:
            pass
        return {}

    def get_lexikon(self, project: str) -> Dict[str, Any]:
        """Merged lexikon: _global first, project entries win."""
        merged: Dict[str, Any] = {}
        for fp in self._lexikon_files_for(project):
            merged.update(self._read_lexikon_file(fp))
        return merged

    def add_lexikon_term(
        self,
        project: str,
        term: str,
        definition: str = "",
        aliases: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Hand-add a lexikon entry (source=hand wins over derived ones)."""
        term = str(term or "").strip()
        if not term:
            return {"status": "error", "message": "Empty term."}
        if str(project or "").strip() in ("", "_global"):
            fp = LEXIKON_GLOBAL_FILE
        else:
            d = resolve_project_dir(project)
            fp = d / "state" / "lexikon.json"
        try:
            data = {}
            if fp.exists():
                data = json.loads(fp.read_text(encoding="utf-8"))
            terms = data.get("terms") or {}
            terms[term.lower()] = {
                "term": term,
                "definition": definition or "",
                "aliases": sorted({a.strip() for a in (aliases or []) if a.strip()}),
                "source": "hand",
                "updated": time.strftime("%Y-%m-%d %H:%M"),
            }
            data["terms"] = terms
            _atomic_write_json(fp, data)
            return {"status": "success", "message": f"Lexikon entry '{term}' saved."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to save lexikon: {e}"}

    def seed_dtd_lexikon(self, project: str) -> int:
        """Seed the project lexikon with DTD vocabulary (TODO-37).

        Scans the project's DTD-family files (.dtd/.mod/.ent), extracts
        profiles with the engine's own scanners, and seeds:
          - every rare attribute (df==1) -> its owning element as alias;
          - every rare entity/parameter-entity -> the file's root element.
        Lane discipline: source present (df==1), single owner, alias present
        in the owner file, alias differs from source, definition empty
        (only the alias enters the query expansion). This is the
        architecture hook: real projects get the amplification, not
        just the benchmark harness. Returns the number of terms seeded.
        """
        try:
            d = resolve_project_dir(project)
        except Exception:
            return 0
        if not d.exists():
            return 0
        files = sorted(
            p
            for p in d.rglob("*")
            if p.is_file()
            and p.suffix.lower() in _DTD_SUFFIXES
            and not any(part in p.parts for part in _NOISE_DIRS)
        )
        if not files:
            return 0
        attr_df: Dict[str, int] = defaultdict(int)
        ent_df: Dict[str, int] = defaultdict(int)
        elem_df: Dict[str, int] = defaultdict(int)
        profiles = {}
        for p in files:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            decls = list(_scan_dtd_declarations(text))
            ents = set()
            elems: List[str] = []
            for kind, name, _decl in decls:
                if kind == "ELEMENT" and name and name not in elems:
                    elems.append(name)
                elif kind == "ENTITY" and name:
                    ents.add(name)
            attr_owners = _dtd_attr_owners(text)
            for a in attr_owners:
                attr_df[a] += 1
            for e in ents:
                ent_df[e] += 1
            for el in set(elems):
                elem_df[el] += 1
            profiles[str(p)] = (attr_owners, ents, elems)
        # Element names are the vocabulary of T1/T2/T10 queries, so a
        # seed term that is itself an element name would collide with
        # element queries and pollute their expansions (measured:
        # author/media/char/data as seeds corrupted T1/T10).
        elem_names = set()
        for _p, (_ao, _ents, elems) in profiles.items():
            elem_names.update(elems)
        seeds = []
        for p, (attr_owners, ents, elems) in profiles.items():
            for a, owner in attr_owners.items():
                # Term length > 3 mirrors the T7/T8 query derivation: short
                # names (w, re, ap) would substring-match unrelated queries
                # and pollute their expansions (measured).
                if (
                    attr_df[a] == 1
                    and len(a) > 3
                    and a not in elem_names
                    and len(owner) > 2
                    and owner != a
                ):
                    # The definition carries the owner element. TODO-33
                    # measured two type-in-definition variants and both
                    # failed: CDATA (majority type) polluted the expansion
                    # (T7 0.675 -> 0.600), and distinctive types (ID,
                    # NMTOKEN, enumerated) regressed `operator` because
                    # enumerated tokens (over/in/out/xor) are themselves
                    # common words. The owner element remains the safest
                    # expansion context.
                    seeds.append((a, owner))
            root = elems[0] if elems else ""
            for e in ents:
                if (
                    ent_df[e] == 1
                    and len(e) > 3
                    and e not in elem_names
                    and len(root) > 2
                    and root != e
                ):
                    seeds.append((e, root))
        count = 0
        for term, ctx in seeds:
            # The element context goes in the DEFINITION, not the aliases:
            # lexikon_expansion matches on term+aliases, so alias-based
            # seeds would pollute T1/T10 queries that contain element
            # names. Definition words are added only when the query
            # contains the term itself (the rare attribute/entity name).
            self.add_lexikon_term(project, term, definition=ctx, aliases=[])
            count += 1
        return count

    def build_lexikon(self, project: str) -> Dict[str, Any]:
        """Derive project lexikon from registry + latest session report.

        Hand entries (source=hand) always win over derived ones.
        """
        if str(project or "").strip() in ("", "_global"):
            return {
                "status": "error",
                "message": "The _global lexikon is hand-curated only.",
            }
        d = resolve_project_dir(project)
        if not d.exists():
            return {"status": "error", "message": f"Project dir {d} missing."}
        fp = d / "state" / "lexikon.json"
        existing = self._read_lexikon_file(fp)
        derived: Dict[str, Any] = {}
        try:
            for _cid, cdata in self._load_concept_registry(project).items():
                canon = str(cdata.get("canonical_name", "")).strip()
                if not canon:
                    continue
                derived[canon.lower()] = {
                    "term": canon,
                    "definition": "",
                    "aliases": sorted(
                        {str(a) for a in (cdata.get("aliases") or []) if str(a).strip()}
                    ),
                    "source": "registry",
                    "updated": time.strftime("%Y-%m-%d %H:%M"),
                }
        except Exception:
            pass
        try:
            latest = _latest_session_report(d / "directives" / "sessions")
            if latest is not None:
                import yaml

                content = latest.read_text(encoding="utf-8")
                m = re.search(r"```yaml(.*?)```", content, re.DOTALL)
                if m:
                    events = (yaml.safe_load(m.group(1)) or {}).get(
                        "knowledge_events", []
                    )
                    for ev in events or []:
                        concept = str((ev or {}).get("concept", "")).strip()
                        if concept and concept.lower() not in derived:
                            derived[concept.lower()] = {
                                "term": concept,
                                "definition": str((ev or {}).get("evidence", ""))[:200],
                                "aliases": [],
                                "source": "session",
                                "updated": time.strftime("%Y-%m-%d %H:%M"),
                            }
        except Exception:
            pass
        for key, entry in derived.items():
            if key not in existing or existing[key].get("source") != "hand":
                existing[key] = entry
        try:
            _atomic_write_json(fp, {"terms": existing})
        except Exception as e:
            return {"status": "error", "message": f"Failed to write lexikon: {e}"}
        glossary_path = self._write_glossary_dtd(d, existing)
        return {
            "status": "success",
            "message": f"Lexikon built: {len(existing)} terms.",
            "terms": len(existing),
            "glossary_dtd": str(glossary_path) if glossary_path else None,
        }

    def _write_glossary_dtd(
        self, project_dir: Path, terms: Dict[str, Any]
    ) -> Path | None:
        """Write the keeper glossary as a DTD corpus member (TODO-70).

        The glossary lives beside the keeper memory root
        (<project>/.opencode/memory/rtrre-glossary.dtd) and follows the
        rtrre-glossary.mod architectural form: every term is a declaration
        carrying term/alias/definition/source/ts attributes, so the DTD
        chunker's inventory header makes glossary terms retrievable
        structure-first — the operator's glossary-sync-in-DTD vision.
        Attribute values are XML-escaped: a term carrying quotes or
        markup must never break the document that carries it.
        """
        from xml.sax.saxutils import quoteattr

        try:
            memory_root = project_dir / ".opencode" / "memory"
            memory_root.mkdir(parents=True, exist_ok=True)
            path = memory_root / "rtrre-glossary.dtd"
            lines = [
                "<!-- RTR-RE:Symbiose keeper glossary v2 (DTD-shaped) -->",
                '<!ENTITY % rtrre.glossary.module "INCLUDE">',
                "<![%rtrre.glossary.module;[",
                "<!ELEMENT glossaryentry EMPTY>",
                "<!ATTLIST glossaryentry",
                "    term CDATA #REQUIRED",
                "    alias CDATA #IMPLIED",
                "    definition CDATA #IMPLIED",
                "    source CDATA #IMPLIED",
                "    ts CDATA #IMPLIED>",
                "]]>",
                "<!-- glossary entries follow -->",
                "",
            ]
            for key, entry in terms.items():
                term = str(entry.get("term") or key)
                aliases = entry.get("aliases") or []
                alias = ", ".join(str(a) for a in aliases)
                definition = str(entry.get("definition") or "")
                source = str(entry.get("source") or "hand")
                ts = str(entry.get("updated") or "")
                lines.append(
                    f"<glossaryentry term={quoteattr(term)} alias={quoteattr(alias)} "
                    f"definition={quoteattr(definition)} source={quoteattr(source)} ts={quoteattr(ts)}/>"
                )
            path.write_bytes(("\n".join(lines)).encode("utf-8"))
            return path
        except Exception:
            return None

    def lexikon_expansion(self, project: str, query: str, limit: int = 8) -> List[str]:
        """Lookup-only expansion terms: lexikon hits overlapping the query."""
        q = str(query or "").lower()
        qtokens = {t for t in re.findall(r"\w+", q) if len(t) > 2}
        if not qtokens:
            return []
        out = []
        try:
            lex = self.get_lexikon(project)
        except Exception:
            return []
        for _key, entry in lex.items():
            if not isinstance(entry, dict):
                continue
            term = str(entry.get("term", ""))
            aliases = [str(a) for a in (entry.get("aliases") or [])]
            # Match on whole whitespace tokens of the query, never on
            # substring or any-token overlap: DTD vocabulary is full of
            # dotted/hyphenated compound names (book.set.part.wrapper,
            # %SVG.animate.qname;, MediaServerControl), and substring
            # matching lets a bare query like "chart:chart" match a
            # seeded term "char" that merely prefixes it, polluting the
            # expansion (measured: T1/T10 regressed under substring
            # matching).
            qtokens_ws = q.split()
            if (term.lower() in qtokens_ws) or any(
                a.lower() in qtokens_ws for a in aliases if a
            ):
                for t in re.findall(r"\w+", str(entry.get("definition", "")).lower()):
                    if len(t) > 2 and t not in qtokens and t not in out:
                        out.append(t)
                    if len(out) >= limit:
                        return out
                for a in aliases:
                    al = a.lower()
                    if al not in qtokens and al not in out and len(al) > 2:
                        out.append(al)
                    if len(out) >= limit:
                        return out
        return out

    def _resolve_concept(self, project: str, term: str) -> Tuple[str, Dict[str, Any]]:
        """
        Resolve a term (canonical name or alias) against the registry.
        Returns (concept_id, concept_data) if found, otherwise returns (new_id, new_data_stub).
        """
        registry = self._load_concept_registry(project)
        term_clean = term.strip().lower()

        # 1. Direct match on canonical name or aliases
        for cid, data in registry.items():
            canonical = data.get("canonical_name", "").lower()
            aliases = [a.lower() for a in data.get("aliases", [])]
            if term_clean == canonical or term_clean in aliases:
                return cid, data

        # 2. Fast semantic/substring check
        for cid, data in registry.items():
            canonical = data.get("canonical_name", "").lower()
            c_words = set(re.findall(r"\w+", canonical))
            t_words = set(re.findall(r"\w+", term_clean))
            if (
                c_words
                and t_words
                and len(c_words.intersection(t_words))
                >= max(1, min(len(c_words), len(t_words)))
            ):
                if term not in data.get("aliases", []):
                    data.setdefault("aliases", []).append(term)
                    self._save_concept_registry(project, registry)
                return cid, data

        # 3. Create a new concept stub if not found
        next_num = len(registry) + 1
        new_id = f"concept_{next_num:03d}"

        canonical_name = (
            re.sub(r"[^a-zA-Z0-9\s-]", "", term).strip().replace(" ", "-").lower()
        )
        if not canonical_name:
            canonical_name = f"concept-{next_num}"

        new_data = {
            "canonical_name": canonical_name,
            "aliases": [term],
            "status": "candidate",
            "confidence": 1,
            "evidence_count": 0,
            "session_count": 0,
        }

        registry[new_id] = new_data
        self._save_concept_registry(project, registry)
        return new_id, new_data

    def materialize_concepts(self, project: str) -> Dict[str, Any]:
        """Parse session learning reports, update Concept Registry, and materialize validated concept nodes."""
        project_dir = resolve_project_dir(project)
        if not project_dir.exists():
            return {
                "status": "error",
                "message": f"Project directory {project_dir} does not exist.",
            }

        directives_dir = project_dir / "directives"
        sessions_dir = directives_dir / "sessions"
        if not sessions_dir.exists():
            return {
                "status": "success",
                "message": "No session reports found.",
                "materialized": [],
            }

        paths = self._get_wiki_paths(project)
        concepts_dir = paths["concepts"]
        concepts_dir.mkdir(parents=True, exist_ok=True)

        latest_report = _latest_session_report(sessions_dir)
        if latest_report is None:
            return {
                "status": "success",
                "message": "No session reports found.",
                "materialized": [],
            }

        try:
            content = latest_report.read_text(encoding="utf-8")
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read latest session report: {e}",
            }

        date_str = time.strftime("%Y-%m-%d")
        date_match = re.search(r"date:\s*([^\s\n]+)", content)
        if date_match:
            date_str = date_match.group(1).strip()

        # Parse YAML block of knowledge_events
        knowledge_events = []
        yaml_match = re.search(r"```yaml\n(.*?)\n```", content, re.DOTALL)
        if yaml_match:
            try:
                import yaml

                data = yaml.safe_load(yaml_match.group(1))
                if isinstance(data, dict) and "knowledge_events" in data:
                    knowledge_events = data["knowledge_events"]
            except Exception as e:
                print(f"Error parsing YAML from report: {e}", file=sys.stderr)

        if not knowledge_events:
            return {
                "status": "success",
                "message": "No knowledge events found to materialize.",
                "materialized": [],
            }

        registry = self._load_concept_registry(project)
        materialized_log = []

        import yaml

        # Process each event and update registry
        for event in knowledge_events:
            concept_name = event.get("concept", "General Learning")
            event_type = event.get("type", "observation").lower()
            evidence = event.get("evidence", "")

            cid, cdata = self._resolve_concept(project, concept_name)

            cdata["evidence_count"] = cdata.get("evidence_count", 0) + (
                1 if evidence else 0
            )
            cdata["session_count"] = cdata.get("session_count", 0) + 1

            confidence = cdata.get("confidence", 1)
            if event_type == "validation":
                confidence = min(5, confidence + 1)
            elif event_type == "failure":
                confidence = max(1, confidence - 1)
            cdata["confidence"] = confidence

            current_status = cdata.get("status", "candidate")

            if event_type == "deprecation":
                new_status = "deprecated"
            elif cdata["session_count"] >= 5 and cdata["confidence"] >= 4:
                new_status = "canonical"
            elif cdata["evidence_count"] >= 3 or current_status == "validated":
                new_status = "validated"
            elif cdata["session_count"] >= 2:
                new_status = "emerging"
            else:
                new_status = "candidate"

            cdata["status"] = new_status

            registry[cid] = cdata
            self._save_concept_registry(project, registry)

            concept_file = concepts_dir / f"{cid}.md"

            if new_status in ["validated", "canonical"]:
                existing_body = ""
                is_new = not concept_file.exists()

                if not is_new:
                    try:
                        existing_text = concept_file.read_text(encoding="utf-8")
                        fm_match = re.match(
                            r"^---\s*\n(.*?)\n---\s*\n(.*)$", existing_text, re.DOTALL
                        )
                        if fm_match:
                            existing_body = fm_match.group(2).strip()
                        else:
                            existing_body = existing_text.strip()
                    except Exception:
                        pass

                learnings_text = (
                    f"- **{event_type.title()}**: {evidence}" if evidence else ""
                )

                if is_new:
                    body_content = f"# {cdata['canonical_name'].replace('-', ' ').title()}\n\nThis concept is a validated organizational knowledge node.\n\n## Learnings ({date_str})\n{learnings_text}\n"
                else:
                    body_content = existing_body
                    if learnings_text:
                        body_content += (
                            f"\n\n## Learnings ({date_str})\n{learnings_text}\n"
                        )

                fm_aliases = yaml.dump(
                    cdata.get("aliases", []), default_flow_style=True
                ).strip()
                concept_content = f"""---
concept_id: {cid}
canonical_name: {cdata["canonical_name"]}
status: {new_status}
confidence: {cdata["confidence"]}
evidence_count: {cdata["evidence_count"]}
session_count: {cdata["session_count"]}
aliases: {fm_aliases}
---
{body_content}"""

                try:
                    concept_file.write_text(
                        concept_content.strip() + "\n", encoding="utf-8"
                    )
                    materialized_log.append(
                        f"Materialized validated node: {cid} ({cdata['canonical_name']}) status={new_status}"
                    )
                except Exception as e:
                    print(f"Failed to materialize {cid}: {e}", file=sys.stderr)

            elif new_status == "deprecated":
                if concept_file.exists():
                    try:
                        concept_file.unlink()
                        materialized_log.append(
                            f"Archived/Deleted deprecated node: {cid} ({cdata['canonical_name']})"
                        )
                    except Exception as e:
                        print(
                            f"Failed to delete deprecated node {cid}: {e}",
                            file=sys.stderr,
                        )
            else:
                if concept_file.exists():
                    try:
                        concept_file.unlink()
                    except Exception:
                        pass
                materialized_log.append(
                    f"Registry updated: {cid} ({cdata['canonical_name']}) status={new_status} (Not materialized on disk)"
                )

        return {"status": "success", "materialized": materialized_log}

    def update_concept_graph(self, project: str) -> Dict[str, Any]:
        """Analyze all materialized concept nodes in a project and establish reciprocal bidirectional ID-based links: [[concept_XXX|Canonical Name]]."""
        project_dir = resolve_project_dir(project)
        if not project_dir.exists():
            return {
                "status": "error",
                "message": f"Project directory {project_dir} does not exist.",
            }

        paths = self._get_wiki_paths(project)
        concepts_dir = paths["concepts"]

        if not concepts_dir.exists():
            return {
                "status": "success",
                "message": "No concepts directory exists yet.",
                "links_added_or_normalized": 0,
            }

        concept_files = list(concepts_dir.glob("concept_*.md"))
        if not concept_files:
            return {
                "status": "success",
                "message": "No concept files found.",
                "links_added_or_normalized": 0,
            }

        registry = self._load_concept_registry(project)
        concepts_data = {}

        for f in concept_files:
            cid = f.stem
            if cid not in registry:
                continue

            try:
                text = f.read_text(encoding="utf-8")
                cdata = registry[cid]

                links = set(re.findall(r"\[\[(concept_\d+)(?:\|[^\]]*)?\]\]", text))

                concepts_data[cid] = {
                    "path": f,
                    "name": cdata["canonical_name"].replace("-", " ").title(),
                    "text": text,
                    "links": links,
                }
            except Exception:
                pass

        connections = {cid: set(data["links"]) for cid, data in concepts_data.items()}

        for cid_a, data_a in concepts_data.items():
            text_lower = data_a["text"].lower()
            fm_match = re.match(
                r"^---\s*\n.*?\n---\s*\n(.*)$", data_a["text"], re.DOTALL
            )
            body_text = fm_match.group(1).lower() if fm_match else text_lower

            for cid_b, data_b in concepts_data.items():
                if cid_a == cid_b:
                    continue

                bdata = registry[cid_b]
                b_canonical = bdata["canonical_name"].lower()
                b_spaced = b_canonical.replace("-", " ")

                matched = False
                if (
                    re.search(rf"\b{re.escape(cid_b)}\b", body_text)
                    or re.search(rf"\b{re.escape(b_canonical)}\b", body_text)
                    or re.search(rf"\b{re.escape(b_spaced)}\b", body_text)
                ):
                    matched = True
                else:
                    for alias in bdata.get("aliases", []):
                        if re.search(rf"\b{re.escape(alias.lower())}\b", body_text):
                            matched = True
                            break

                if matched:
                    connections[cid_a].add(cid_b)

        reciprocal_connections = {cid: set(conn) for cid, conn in connections.items()}
        for cid_a, conns in connections.items():
            for cid_b in conns:
                if cid_b in reciprocal_connections:
                    reciprocal_connections[cid_b].add(cid_a)

        links_added_count = 0
        for cid, data in concepts_data.items():
            filepath = data["path"]
            current_text = data["text"]
            target_links = reciprocal_connections[cid]

            target_links = {
                link for link in target_links if link in concepts_data and link != cid
            }

            if not target_links:
                continue

            fm_match = re.match(
                r"^(---\s*\n.*?\n---\s*\n)(.*)$", current_text, re.DOTALL
            )
            if not fm_match:
                continue

            header = fm_match.group(1)
            body = fm_match.group(2)

            body_clean = re.split(
                r"\n##\s+(?:Related Knowledge|Related)\b", body, flags=re.IGNORECASE
            )[0].strip()

            related_lines = []
            for target_cid in sorted(target_links):
                target_name = (
                    registry[target_cid]["canonical_name"].replace("-", " ").title()
                )
                related_lines.append(
                    f"- [[{target_cid}|{target_name}]] — {target_name}"
                )

            related_section = "\n\n## Related Knowledge\n" + "\n".join(related_lines)
            new_content = header + body_clean + related_section + "\n"

            if new_content != current_text:
                try:
                    filepath.write_text(new_content, encoding="utf-8")
                    links_added_count += len(target_links) - len(data["links"])
                except Exception:
                    pass

        return {
            "status": "success",
            "message": f"Successfully updated bidirectional Graph links across {len(concept_files)} nodes using Concept IDs.",
            "links_added_or_normalized": links_added_count,
        }

    def add_memory_reference(self, project: str, text: str = "") -> Dict[str, Any]:
        """Bounded memory-reference insert: embed exactly this conversation text
        into the RTR collections and return. No discovery, no registry scan,
        no janitor/lexikon/graph, no corpus reindex — the compact's job is to
        persist the compacted conversation as a chroma memory reference, not
        to re-embed the world (measured: full index_all on a fresh DB grew to
        ~20 GB and crashed the host session).
        """
        refused = self._require_writer("add_memory_reference")
        if refused is not None:
            return refused
        wedged = _worker_refusal("add_memory_reference")
        if wedged is not None:
            return {"status": "error", "message": wedged}
        text = (text or "").strip()
        if not text:
            return {"status": "success", "chunks_added": 0, "message": "empty text"}

        now = time.time()
        stamp = (
            time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(now * 1000000) % 1000000:06d}"
        )
        rel_path = f"memoryref://{project}/compaction/{stamp}"
        chunk_text = f"Compaction Memory Reference\nProject: {project}\n\n{text}"
        chunks = [
            {
                "chunk_id": f"{rel_path}#chunk_0",
                "text": chunk_text,
                "title": "Compaction Memory Reference",
                "raw_body": text,
                "linked_concepts": [],
            }
        ]

        try:
            models = self.models
            cols = self.collections
        except Exception as e:
            return {"status": "error", "message": f"model/collection init failed: {e}"}

        added = 0
        for slug, col in cols.items():
            model_name = next(
                (n for n in self.embed_model_names if model_slug(n) == slug),
                slug,
            )
            try:
                texts = [mask_ndata(c["text"]) for c in chunks]
                embeddings = [
                    [float(val) for val in e] for e in models[slug].embed(texts)
                ]
                col.add(
                    ids=[c["chunk_id"] for c in chunks],
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=[
                        {
                            "rel_path": rel_path,
                            "project": project_filter_key(project) or project,
                            "category": "memory-reference",
                            "subcategory": "compaction",
                            "title": c["title"],
                            "content_hash": hashlib.sha256(
                                text.encode("utf-8")
                            ).hexdigest(),
                            "linked_concepts": "",
                            "created_at": str(now),
                            "updated_at": str(now),
                            "last_accessed": str(time.time()),
                            "access_count": "0",
                            "importance": "high",
                            "embed_model": model_name,
                            "dtype_hist": dtype_histogram(c["text"]),
                            "notations": "",
                        }
                        for c in chunks
                    ],
                )
                added += len(chunks)
            except Exception as e:
                print(
                    f"Failed memory-reference insert into {slug}: {e}",
                    file=sys.stderr,
                )
        return {"status": "success", "chunks_added": added}

    def session_commit(
        self, project: str, conversation_text: str = "", full_reindex: bool = False
    ) -> Dict[str, Any]:
        """Master Proactive Orchestrator. Performs reflection, materialization, bidirectional linking, and indexing."""
        refused = self._require_writer("session_commit")
        if refused is not None:
            return refused
        wedged = _worker_refusal("session_commit")
        if wedged is not None:
            return {"status": "error", "message": wedged}
        if full_reindex:
            no_charge = _full_reindex_refusal()
            if no_charge is not None:
                return {"status": "error", "message": no_charge}
        reflection = self.reflect_session(project, conversation_text)
        if reflection["status"] == "error":
            return reflection

        materialize = self.materialize_concepts(project)
        if materialize["status"] == "error":
            return materialize

        graph = self.update_concept_graph(project)
        if graph["status"] == "error":
            return graph

        # Automatic maintenance: lexikon plus janitor ride every commit so no
        # derived store ever goes stale waiting for a manual tool call. Both
        # are tolerant on purpose — a maintenance hiccup must never sink the
        # commit that carries the session's learnings.
        try:
            lexikon = self.build_lexikon(project)
        except Exception as e:
            print(f"commit lexikon skipped: {e}", file=sys.stderr)
            lexikon = {}
        try:
            janitor = self.janitor(dry_run=False)
        except Exception as e:
            print(f"commit janitor skipped: {e}", file=sys.stderr)
            janitor = {}

        index_stats = self.index_all(force=full_reindex)

        return {
            "status": "success",
            "report_path": reflection["report_path"],
            "knowledge_events": reflection["knowledge_events"],
            "materialized_log": materialize["materialized"],
            "links_updated": graph["links_added_or_normalized"],
            "lexikon_message": lexikon.get("message", "")
            if isinstance(lexikon, dict)
            else "",
            "janitor_freed": janitor.get("freed", 0)
            if isinstance(janitor, dict)
            else 0,
            "index_stats": index_stats,
            "index_refusal": index_stats.get("message")
            if isinstance(index_stats, dict)
            else None,
        }
