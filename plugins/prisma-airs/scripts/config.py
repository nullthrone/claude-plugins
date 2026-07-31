"""Configuration and credential resolution for prisma-airs.

Reads the project-level `.prisma-airs.json` (committable, contains no
secrets) and layers environment variables on top for anything sensitive.
Never raises on missing configuration -- callers check `is_configured()`
and go inert (see docs/decisions/0002-inert-until-configured.md).
"""
import json
import os

DEFAULT_CONFIG_NAME = ".prisma-airs.json"

# Regional Scan API hosts, per
# https://pan.dev/prisma-airs/api/airuntimesecurity/airuntimesecurityapi/
# -- fixed at deployment-profile creation time in Strata Cloud Manager, not
# something the API lets you pick per request.
REGION_HOSTS = {
    "us": "https://service.api.aisecurity.paloaltonetworks.com",
    "de": "https://service-de.api.aisecurity.paloaltonetworks.com",
    "in": "https://service-in.api.aisecurity.paloaltonetworks.com",
    "sg": "https://service-sg.api.aisecurity.paloaltonetworks.com",
}
DEFAULT_REGION = "us"

# Two lineages of env var names exist in the wild: pan.dev's own Python SDK
# docs use PANW_AI_SEC_API_KEY; Palo Alto's community Claude Code
# integrations (github.com/PaloAltoNetworks/prisma-airs-integrations) use
# PRISMA_AIRS_API_KEY. We read both so either lineage works, preferring
# PRISMA_AIRS_* since that's this plugin's own convention.
API_KEY_ENV_VARS = ("PRISMA_AIRS_API_KEY", "PANW_AI_SEC_API_KEY")

DEFAULT_TIMEOUT_SECONDS = 5
# pan.dev's contextual-grounding limits cap prompt/response/context sizes
# well above this; this default is about keeping a hook fast, not about an
# API-side limit.
DEFAULT_MAX_CONTENT_CHARS = 20000
DEFAULT_AUDIT_LOG = ".prisma-airs/audit.jsonl"
DEFAULT_TOOL_MATCHER = r"Bash|Write|Edit|WebFetch|WebSearch|mcp__.*"

# What to do when the API doesn't answer at all (network error, timeout,
# 429, 5xx) -- pan.dev documents no client-side guidance for this (verified:
# neither the error-codes page, the API overview, nor the use-cases page
# say anything about fail-open vs fail-closed). This is our own default,
# not a Palo Alto recommendation -- see docs/decisions and the plan's D5.
DEFAULT_ON_UNREACHABLE = {
    "user_prompt_submit": "allow",
    "pre_tool_use": "ask",
    "post_tool_use": "allow",
    "stop": "allow",
}

DEFAULT_HOOKS_ENABLED = {
    "user_prompt_submit": True,
    "pre_tool_use": True,
    "post_tool_use": True,
    # Off by default: sits on the critical path of every turn ending, and
    # pan.dev documents no per-request latency bound. See hook_stop.py.
    "stop": False,
}


class Config:
    def __init__(self, data, project_dir):
        self._data = data or {}
        self.project_dir = project_dir

    @classmethod
    def load(cls, project_dir=None):
        project_dir = project_dir or os.getcwd()
        path = os.path.join(project_dir, DEFAULT_CONFIG_NAME)
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                data = {}
        return cls(data, project_dir)

    # -- secrets: environment only, never the config file --

    @property
    def api_key(self):
        for name in API_KEY_ENV_VARS:
            value = os.environ.get(name)
            if value:
                return value
        return None

    @property
    def profile_name(self):
        return os.environ.get("PRISMA_AIRS_PROFILE_NAME") or self._data.get("profile_name")

    @property
    def profile_id(self):
        return os.environ.get("PRISMA_AIRS_PROFILE_ID") or self._data.get("profile_id")

    # -- non-secret settings: config file, with env overrides where it makes sense --

    @property
    def app_name(self):
        return self._data.get("app_name", "claude-code")

    @property
    def region(self):
        return self._data.get("region", DEFAULT_REGION)

    @property
    def base_url(self):
        override = os.environ.get("PRISMA_AIRS_URL")
        if override:
            return override.rstrip("/")
        return REGION_HOSTS.get(self.region, REGION_HOSTS[DEFAULT_REGION])

    @property
    def timeout_seconds(self):
        return float(self._data.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

    @property
    def max_content_chars(self):
        return int(self._data.get("max_content_chars", DEFAULT_MAX_CONTENT_CHARS))

    @property
    def tool_matcher(self):
        return self._data.get("tool_matcher", DEFAULT_TOOL_MATCHER)

    @property
    def audit_log_path(self):
        rel = self._data.get("audit_log", DEFAULT_AUDIT_LOG)
        return os.path.join(self.project_dir, rel)

    def hook_enabled(self, name):
        hooks = self._data.get("hooks", {})
        return bool(hooks.get(name, DEFAULT_HOOKS_ENABLED.get(name, False)))

    def on_unreachable(self, event):
        table = self._data.get("on_unreachable", {})
        return table.get(event, DEFAULT_ON_UNREACHABLE.get(event, "allow"))

    def is_configured(self):
        """True only if there's enough to actually call the API. Every hook
        calls this first and exits silently (exit 0, no output) if it's
        False -- see docs/decisions/0002-inert-until-configured.md."""
        if not self.api_key:
            return False
        if not (self.profile_name or self.profile_id):
            return False
        return True

    def ai_profile(self):
        """The `ai_profile` object for a scan request body. profile_id wins
        if both are set, matching the API's own precedence (pan.dev:
        "If not provided, then profile_name is required")."""
        if self.profile_id:
            return {"profile_id": self.profile_id}
        return {"profile_name": self.profile_name}
