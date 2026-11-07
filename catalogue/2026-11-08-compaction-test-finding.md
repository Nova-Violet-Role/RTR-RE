# Compaction live test — finding (2026-11-08)

## What was tested

TODO-61: the emergency compact path in the opencode-dev build, on the
dummy project, with a small model context limit so auto-compaction fires.

## How the trigger works (measured from source)

- `session/overflow.ts`: `isOverflow` fires when the last request's token
  usage >= `model.limit.context - reserved` (default reserved =
  min(20000, maxOutputTokens)). It uses the **current request's** tokens,
  not cumulative session tokens.
- The model's context limit comes from the provider model definition
  (`provider.<id>.models.<model>.limit.context`). The global config sets
  1M for the cpa-gui models; `inception/mercury-3` inherits the catalog
  default (~1M working-set cap).
- `compaction.auto` must be true (the flag); without it, no auto-compact.
- The correct config shape (from customize-opencode.md):
  ```jsonc
  { "compaction": { "auto": true, "reserved": 10000 } }
  ```

## Result

With `context: 3000, output: 1000, reserved: 1000` (trigger at ~2000
tokens) the compaction fired repeatedly — a **cascade**: each compact
spawns the compaction agent, whose own run exceeds the tiny window and
compacts again, spawning a fresh memory server each time. Observed as a
stream of ~26-66k-token messages in a single session and 24 python
processes. The runaway (PID 29456, 1555s CPU, 3.1 GB) was killed.

This is the pathological artifact of too-small a limit, not a defect:
at real preset windows (MUGEN 400k) the trigger is far below the window
and no cascade occurs.

## Finding: opencode-src memory.ts is old-era

`session/memory.ts` commit-on-compact uses `memory_reflect_session`
(lightweight report write) and deliberately avoids `memory_session_commit`
(heavy: loads the dual embedding ensemble ~1.2 GB and runs the full
reflect+materialize+graph+lexikon+janitor+index pipeline, which blocks the
live turn). The Keeper plugin sinks evicted spans verbatim on the transform
hook.

This is the legacy integration in the opencode-dev build — it is **not
part of RTR-RE**. RTR-RE's own keeper/compressor/memory pipeline is
independent and measured. The opencode-src memory.ts remains as shipped;
no changes were made to opencode-src in this session.

## Cleanup performed

- Killed the runaway cascade process by PID (taskkill /F /T /PID 29456).
- Removed the pathological test config from the dummy project.
- Deleted the 4 test sessions and their messages from the opencode DB.
- The dummy project is back to a clean state for the next run.
