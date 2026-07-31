# Error Codes -> Hook Reaction

Status codes and their documented meanings are from pan.dev's
[error codes page](https://pan.dev/prisma-airs/api/airuntimesecurity/errorcodes/).
The "hook reaction" column is this plugin's own mapping -- pan.dev
specifies none of it (see the note at the bottom).

| Code | pan.dev meaning | `scripts/airs.py` | Hook reaction |
|---|---|---|---|
| 200 | Successfully scanned | returns parsed JSON | act on `action` -- see `skills/prisma-airs-runtime/SKILL.md` |
| 400 | Malformed request (bad payload, too many IDs, profile name too long, ...) | `AirsHTTPError(400, ...)` | logged, allowed through (a client-side bug shouldn't itself become a security incident) |
| 401 | Missing API key / token | `AirsHTTPError(401, ...)` | logged, allowed through -- but this means setup is broken; `/prisma-airs-setup`'s test call is what should have caught it first |
| 403 | Invalid/revoked/expired key | `AirsHTTPError(403, ...)` | same as 401 |
| 404 | Wrong endpoint | `AirsHTTPError(404, ...)` | same -- indicates a plugin bug, not a content threat |
| 405 | Wrong HTTP method | `AirsHTTPError(405, ...)` | same |
| 413 | Payload too large | `AirsHTTPError(413, ...)` | same; `max_content_chars` truncation should make this rare |
| 415 | Missing/wrong `Content-Type` | `AirsHTTPError(415, ...)` | same -- would indicate a client bug, since `airs.py` always sets it |
| 429 | Rate limit exceeded | `AirsHTTPError(429, ...)` | logged, allowed through per `on_unreachable` treatment -- see below |
| 500 | Server error | `AirsHTTPError(500, ...)` | same as 429 |
| (no response) | connection refused, DNS failure, client-side timeout | `AirsUnreachable` | governed by `.prisma-airs.json`'s `on_unreachable`, per event -- see `skills/prisma-airs-runtime/SKILL.md` |

All error response bodies pan.dev documents are `{"error": {"message":
"..."}}`.

## Why HTTP errors aren't split by code in the hooks

`hook_prompt.py`/`hook_pretool.py`/`hook_posttool.py` catch `AirsHTTPError`
as one class and always log-and-allow, rather than treating 429 differently
from 400. Reasoning: every one of these codes means *this specific scan
attempt* produced no usable verdict -- the only two response-shaped things
that could reasonably differ (a client bug like 400/404/405/415, vs. a
capacity problem like 429/500) both come down to "the profile's decision is
unavailable right now." Splitting further would mean guessing at policy
pan.dev doesn't specify. `/prisma-airs-gate` doesn't get this leniency --
it fails closed on any HTTP error, same as on `AirsUnreachable`.

## The one thing pan.dev is silent on that matters most

No fail-open/fail-closed recommendation exists anywhere on pan.dev for any
of the rows above. Every "hook reaction" here is this plugin's engineering
default, documented as such rather than presented as a vendor
recommendation. See `skills/prisma-airs-runtime/SKILL.md`.
