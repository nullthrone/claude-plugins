# Scan API Reference

Everything here is from [pan.dev](https://pan.dev/prisma-airs/api/airuntimesecurity/)
unless marked otherwise. This is the citation trail behind
`scripts/airs.py`; if the two ever disagree, the code is what actually runs
but this file is wrong and should be fixed.

## Base URLs (region fixed at deployment-profile creation)

| Region | Host |
|---|---|
| US | `https://service.api.aisecurity.paloaltonetworks.com` |
| EU / Germany | `https://service-de.api.aisecurity.paloaltonetworks.com` |
| India | `https://service-in.api.aisecurity.paloaltonetworks.com` |
| Singapore | `https://service-sg.api.aisecurity.paloaltonetworks.com` |

Source: [airuntimesecurityapi](https://pan.dev/prisma-airs/api/airuntimesecurity/airuntimesecurityapi/).

## Auth

Header `x-pan-token: <api key>`. Generated in Strata Cloud Manager during
onboarding. (OAuth2 Bearer also exists for this API per pan.dev, but this
plugin's Scan API client only uses the API-key form.)

## Endpoints

| Op | Method | Path | Doc |
|---|---|---|---|
| Sync scan | `POST` | `/v1/scan/sync/request` | [scan-sync-request](https://pan.dev/prisma-airs/api/airuntimesecurity/scan/scan-sync-request/) |
| Async scan | `POST` | `/v1/scan/async/request` | [scan-async-request](https://pan.dev/prisma-airs/api/airuntimesecurity/scan/scan-async-request/) |
| Scan results | `GET` | `/v1/scan/results?scan_ids=...` | [get-scan-results-by-scan-i-ds](https://pan.dev/prisma-airs/api/airuntimesecurity/scan/get-scan-results-by-scan-i-ds/) |
| Threat reports | `GET` | `/v1/scan/reports?report_ids=...` | [get-threat-scan-reports](https://pan.dev/prisma-airs/api/airuntimesecurity/scan/get-threat-scan-reports/) |

## Request: `contents[]` entries

Each entry is one of: `prompt`, `response`, `code_prompt`, `code_response`,
`context` (for contextual grounding), or `tool_event`. `tool_event` carries
`metadata: {ecosystem, method, server_name, tool_invoked}` plus
`input`/`output` (raw JSON strings) -- pan.dev's example values are
`ecosystem: "mcp"`, `method: "tools/list"`/`"tools/call"`.

## Response fields this plugin reads

- `action`: `"allow"` | `"block"` (pan.dev only documents these two; see
  `reference/upstream.md` for the third, `"alert"`, sourced elsewhere).
- `category`: `"malicious"` | `"benign"` | `"error"` | `"timeout"`.
- `timeout`, `error`, `errors[]` (`{content_type, feature, status}`).
- `prompt_detected` / `response_detected`: per-category booleans
  (`injection`, `url_cats`, `dlp`, `toxic_content`, `malicious_code`,
  `agent`, `topic_violation`, plus response-only `db_security`,
  `ungrounded`). Note the asymmetry: `injection` is prompt-only;
  `db_security`/`ungrounded` are response-only.
- `tool_detected`: `{verdict, metadata, summary: {detections, threats[]},
  input_detected, output_detected}` -- threats include values like
  `"credential leakage"`, `"context poisoning"`.
- `scan_id`, `report_id` -- carried into the audit log for later
  correlation with `get_threat_reports()`.

## Limits

- 2 MB max payload, sync. 5 MB max payload, async. ≤100 URLs either way.
- Async batch size: limitations page says 25; the Python SDK usage page's
  own prose says 5. `airs.py`'s `MAX_ASYNC_BATCH_ITEMS = 5` takes the
  smaller, so this client never exceeds either stated number.
- `scan_ids`/`report_ids` per results/reports call: ≤5.
- Results/reports calls: 10 requests/minute regardless of scan quota
  (source: [errorcodes](https://pan.dev/prisma-airs/api/airuntimesecurity/errorcodes/)).
- Contextual grounding: context ≤100,000 chars, prompt ≤10,000, response
  ≤20,000.

## What pan.dev does *not* say (checked directly, not assumed absent)

- No numeric requests-per-second figure for scan calls -- only "based on
  API call quota" with no number.
- No client-side latency, retry, backoff, or fail-open/fail-closed
  guidance anywhere on the error-codes page, the API overview, or the
  use-cases page.
- No downloadable OpenAPI spec file or Postman collection is linked.
- No Go or JS/TS SDK exists on pan.dev -- Python (`pan-aisecurity`) is the
  only one documented, for the Scan API.
