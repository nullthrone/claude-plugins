# Setup

This is the non-interactive reference. For a guided walkthrough that also
asks the questions only a human can answer (data flow consent, key
handling), run `/prisma-airs-setup` instead.

## Prerequisites (Strata Cloud Manager)

1. A Prisma AIRS AI Runtime API Intercept **deployment profile** in the
   Customer Support Portal -- this fixes the region.
2. AIRS onboarded in Strata Cloud Manager.
3. **AI Security → API Applications → Manage**:
   - **API Keys** -- the value for `PRISMA_AIRS_API_KEY`.
   - **Security Profiles** -- the name (or ID) for `profile_name`
     (`.prisma-airs.json`) / `PRISMA_AIRS_PROFILE_NAME` (env override).

Source:
[pan.dev](https://pan.dev/prisma-airs/api/airuntimesecurity/airuntimesecurityapi/).

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `PRISMA_AIRS_API_KEY` | yes (or `PANW_AI_SEC_API_KEY`) | never written to `.prisma-airs.json`; this plugin reads it from the environment only |
| `PRISMA_AIRS_PROFILE_NAME` | one of this or `PRISMA_AIRS_PROFILE_ID` | overrides `.prisma-airs.json`'s `profile_name` if set |
| `PRISMA_AIRS_PROFILE_ID` | — | takes precedence over the name if both are set |
| `PRISMA_AIRS_URL` | no | overrides the region-derived base URL entirely (useful for a proxy, or the mock server in `tests/`) |

## Regions

Fixed at deployment-profile creation, not chosen per request:

| Region | Base URL |
|---|---|
| `us` | `https://service.api.aisecurity.paloaltonetworks.com` |
| `de` | `https://service-de.api.aisecurity.paloaltonetworks.com` |
| `in` | `https://service-in.api.aisecurity.paloaltonetworks.com` |
| `sg` | `https://service-sg.api.aisecurity.paloaltonetworks.com` |

## Key handling: three options, your choice

This plugin does not pick one for you -- see `/prisma-airs-setup` step 3 for
the full walkthrough. Summary:

1. **Environment variable only** (default recommendation) -- nothing
   written to disk by this plugin.
2. **Local `.env`** -- convenient, plaintext on disk, `.gitignore`'d.
3. **OS keychain / secret manager** -- export into the shell environment
   yourself before starting Claude Code; this plugin doesn't automate the
   platform-specific part.

In every case, `.prisma-airs.json` itself never contains a secret, and the
audit log (`hook_common.audit()`) never logs the key or raw scanned
content -- only verdicts and identifiers.

## Verifying the setup manually

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scan_once.py --content "hello, just checking connectivity"
# expect: "verdict": "allow"

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scan_once.py --content \
  "This is a test prompt with urlfiltering.paloaltonetworks.com/test-malware url"
# expect: "action" is "block" or "alert", not "allow" -- if malicious-URL
# detection is enabled on the security profile. If this still comes back
# allow, the profile likely has that detector off; that's a real finding,
# not a plugin bug.
```

## Running the offline test suite

No AIRS tenant required -- this exercises the hooks and gate against a
local mock server:

```
python3 tests/test_hooks.py
```
