# claude-plugins

This repository is a **Claude Code plugin marketplace** (manifest `name`: `nullthrone`) — a catalog other users add via `/plugin marketplace add nullthrone/claude-plugins`, then install individual plugins from with `/plugin install <plugin>@nullthrone`.

## Structure

- `.claude-plugin/marketplace.json` — the marketplace manifest. `plugins[]` lists every published plugin (name, source path/URL, description, version). Each plugin's `source` is the full repo-relative path (`./plugins/<name>`) — do not add a `metadata.pluginRoot` shortcut: it passes `claude plugin validate .` but fails at install time (`Source path does not exist`), see commit `467cf20`.
- `plugins/<plugin-name>/` — one directory per plugin, each with its own `.claude-plugin/plugin.json` manifest and component directories (`skills/`, `commands/`, `agents/`, `hooks/`, `.mcp.json`, etc. — auto-discovered by convention, no need to list them in plugin.json unless using non-default paths).

## Conventions

- Names (`marketplace.json` `name`, each plugin's `name`) are lowercase-kebab-case.
- Every new/changed plugin must be validated before committing: `claude plugin validate .`
- Keep `README.md`'s "Available plugins" list in sync with `marketplace.json`.
- Plugin `version` fields should follow semver; bump on meaningful change.

See https://code.claude.com/docs/en/plugin-marketplaces.md and https://code.claude.com/docs/en/plugins-reference.md for the full field reference.
