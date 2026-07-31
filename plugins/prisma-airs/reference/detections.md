# Detection Categories

Source: pan.dev's
[use cases page](https://pan.dev/prisma-airs/api/airuntimesecurity/usecases/)
and the `errors[].feature` enum in the Scan API schema, which is the
authoritative internal name list.

| Use case | Response flag | Content side | Profile toggle |
|---|---|---|---|
| Prompt Injection | `prompt_detected.injection` | prompt only | Prompt Injection Detection |
| Malicious URL | `*_detected.url_cats` | both | Malicious URL Detection (Basic/Advanced) |
| Sensitive Data Loss | `*_detected.dlp` | both | Sensitive Data Detection (Basic/Advanced) |
| Mask Sensitive Data | `prompt_masked_data` / `response_masked_data` | both | Basic DLP profile + Block action (masking only applies then) |
| Database Security Attack | `response_detected.db_security` | response only | Database Security Detection |
| Toxic Content | `*_detected.toxic_content` | both | Toxic Content Detection (per-category confidence-banded actions) |
| Malicious Code | `*_detected.malicious_code` | both | (malicious code detection) |
| AI Agent Threats | `*_detected.agent` | both | AI Agent Protection |
| Contextual Grounding | `response_detected.ungrounded` | response only | Contextual Grounding |
| Custom Topic Guardrails | `*_detected.topic_violation` | both | Custom Topic Guardrails (English only) |
| Secure MCP | `tool_detected.*` | tool_event only | (uses the same detectors above, applied to `tool_event` content) |

`errors[].feature` enum (the service's own internal list):
`dlp, injection, url_cats, toxic_content, malicious_code, agent,
topic_violation, db_security, ungrounded`.

## Language coverage (pan.dev, verbatim scope)

- Prompt injection, toxic content: English, Spanish, Russian, German,
  French, Japanese, Portuguese, Italian, simplified Chinese.
- Contextual grounding: same list minus simplified Chinese.
- Custom topic guardrails: English only.
- Malicious code: JavaScript, Python, VBScript, PowerShell, Batch, Shell,
  Perl. pan.dev's guidance: combine same-language snippets into one scan;
  invoke separately per language if a response mixes them.

## `action` vs `category` -- do not confuse these

`category` is the raw detector judgment (`malicious`/`benign`/`error`/
`timeout`). `action` is what the tenant's **security profile** decided to
do about it (`allow`/`block`, plus `alert` -- see `reference/upstream.md`).
Every gating decision in this plugin uses `action`. See
`skills/prisma-airs-runtime/SKILL.md` for the full table.
