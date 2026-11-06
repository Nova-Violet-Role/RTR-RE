# chromadb import errors — diagnosis (2026-11-06)

## Symptom

`python -m unittest execution.test_memory` (and `test_mcp_status`) failed with:

```
ModuleNotFoundError: No module named 'chromadb'
```

## Root cause — wrong interpreter, not a missing dependency

Both project venvs are CPython 3.13 created by uv and **contain** chromadb
1.5.9. The failures occurred because the bare `python` on PATH resolves to the
uv-managed interpreter (3.14), not to the project venv. The project venv is
only used when the command is invoked through `uv run`.

Measured:

| check | result |
|---|---|
| `C:\RTR-RE\.venv` / `C:\RTR\.venv` pyvenv.cfg | CPython 3.13, uv 0.12.5, include-system-site-packages=false |
| `uv run python -c "import chromadb"` (RE) | OK, chromadb 1.5.9 |
| `uv run python -c "import chromadb"` (RTR) | OK, chromadb 1.5.9 |
| `^python --version` (PATH) | uv-managed 3.14 — no project deps |

## Correct invocation

Every project-local Python command must run through `uv run python …`, never
bare `python`:

```bash
uv run python -m unittest execution.test_memory
uv run python -m execution.memory_mcp_server
uv run python eval/bench_versus.py --intense
```

Installed-package commands keep `uvx --from rtr-role-type-retrieval …`.

## Full suites under the correct interpreter

| suite | RE | RTR |
|---|---|---|
| python unittest (11 modules) | 131/131 OK | 137/137 OK (1 expected lab-guard skip) |
| keeper node --test | 22/22 | 22/22 |
| mjs bun test | 13/13 | — |

## Affected docs fixed

- `README-PYPI.md` (both repos): `python -m unittest`, `python -m
  execution.memory_mcp_server`, `python eval/bench_*.py` → `uv run python …`
- `eval/TAXONOMY.md` (both repos): release gate `python -m execution.rtr_eval`
  → `uv run python -m execution.rtr_eval`
