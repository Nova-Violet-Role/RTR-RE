---
description: Turn rtr-re off for this session, or confirm it is on
---

If $ARGUMENTS is off (or "stop rtr" / "normal mode"): say so in one line and stop applying this ruleset for the rest of the session.

If $ARGUMENTS is empty or on: confirm rtr-re is on in one line, then carry on with whatever was being discussed.

If $ARGUMENTS names a memory action (search, stats, index, write, session-start, session-commit, janitor, explain): run it through rtr-cli and report the measured result, or say in one line that rtr-cli is not installed.
