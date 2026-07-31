# claude-plugins

A [Claude Code](https://code.claude.com) plugin marketplace.

## Installation

Add this marketplace in Claude Code:

```
/plugin marketplace add nullthrone/claude-plugins
```

Then install any plugin listed below:

```
/plugin install <plugin-name>@nullthrone
```

## Available plugins

- **[compliance-audit](plugins/compliance-audit)**: Audits code, IaC and runtime configuration against German and EU regulatory frameworks (BSI IT-Grundschutz, Cyber Resilience Act, GDPR).
- **[prisma-airs](plugins/prisma-airs)**: Guided setup and runtime protection for Palo Alto Networks Prisma AIRS (AI Runtime Security) -- onboarding, opt-in hooks, an MCP tool-poisoning audit, and a CI gate for prompt-shaped repository artifacts.

## Adding a new plugin

1. Create a new directory under `plugins/<plugin-name>/`.
2. Add a `.claude-plugin/plugin.json` manifest (see [plugin reference](https://code.claude.com/docs/en/plugins-reference.md)).
3. Add the plugin's components as needed: `skills/`, `commands/`, `agents/`, `hooks/`, `.mcp.json`, etc.
4. Register the plugin in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json):

   ```json
   {
     "name": "<plugin-name>",
     "source": "./plugins/<plugin-name>",
     "description": "...",
     "version": "0.1.0"
   }
   ```

5. Validate the marketplace:

   ```
   claude plugin validate .
   ```

6. Commit and push. Existing users pick up the change via `/plugin marketplace update nullthrone`.

## Structure

```
claude-plugins/
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── <plugin-name>/
│       ├── .claude-plugin/plugin.json
│       ├── skills/
│       ├── commands/
│       ├── agents/
│       └── ...
├── README.md
└── LICENSE
```
