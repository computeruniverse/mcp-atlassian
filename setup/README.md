# mcp-atlassian — Claude Code Setup

This folder contains everything needed to connect mcp-atlassian to Claude Code as an MCP server.

## Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed (`brew install uv`)
- A personal Atlassian API token — get one at:
  https://id.atlassian.com/manage-profile/security/api-tokens

## Setup

Clone this repository and run the setup script:

```bash
git clone https://github.com/computeruniverse/mcp-atlassian.git
cd mcp-atlassian
./setup/setup-claude-mcp.sh
```

The script will prompt for:

| Prompt | Default | Notes |
|---|---|---|
| Jira URL | `https://cyberport.atlassian.net` | Press Enter to accept |
| Jira username | — | Your Atlassian email address |
| Jira API token | — | Input is hidden |
| Project filter | `NOP` | Comma-separated list of Jira project keys |

Restart Claude Code when done.

## What the script does

1. Creates `~/.config/mcp-atlassian/` with restricted permissions (`700`)
2. Writes your credentials to `~/.config/mcp-atlassian/.env` (`600` — owner read/write only)
3. Generates `~/.config/mcp-atlassian/run.sh` — the launcher Claude Code calls to start the server
4. Excludes `~/.config/mcp-atlassian/` from Time Machine backups
5. Installs Claude Code skills from `setup/skills/` into `~/.claude/skills/`
6. Registers the MCP server with Claude Code at user scope (available in all projects)

## Resulting setup

```
~/.config/mcp-atlassian/
    .env        # Your credentials (chmod 600, excluded from Time Machine)
    run.sh      # Launcher: sources .env, then starts the MCP server via uv

~/.claude/settings.json
    mcpServers:
        mcp-atlassian:
            command: /bin/bash
            args: [~/.config/mcp-atlassian/run.sh]
```

When Claude Code starts, it launches `run.sh` as a subprocess. That script loads your credentials from `.env` into the environment and hands off to `uv run --directory <repo> mcp-atlassian`, which starts the MCP server from this repository.

```
Claude Code
    └── /bin/bash run.sh
            └── uv run --directory /path/to/mcp-atlassian mcp-atlassian
```

The server is registered at **user scope**, meaning it is available across all your Claude Code projects without additional configuration.

## Included skills

The setup script installs the following Claude Code skills into `~/.claude/skills/`:

| Skill | Usage | Description |
|---|---|---|
| `create-ticket` | `/create-ticket "Summary" [--type Story\|Defect] [--brand CP\|CU\|"CP & CU"] [--sprint "..."] [--labels A,B] [--due YYYY-MM-DD]` | Creates a Jira ticket in the NOP project with the correct custom fields, template structure, and workflow transition |

Skills are invoked as slash commands inside Claude Code. Example:

```
/create-ticket "MailKit upgraden" --type Story --brand "CP & CU" --sprint "Tech Debt Backlog" --labels Backend,TechnicalDebt
```

## Verify

```bash
claude mcp list
# mcp-atlassian: /bin/bash ~/.config/mcp-atlassian/run.sh - Connected
```

## Security notes

- Each team member uses their **own** Atlassian API token — never share tokens
- The `.env` file is readable only by you (`chmod 600`)
- The `~/.config/mcp-atlassian/` directory is excluded from Time Machine backups to prevent the token from being stored in plaintext on backup media
- Tokens can be revoked at any time at https://id.atlassian.com/manage-profile/security/api-tokens

## Updating

When the repository is updated, pull the latest changes and restart Claude Code:

```bash
cd /path/to/mcp-atlassian
git pull
# Restart Claude Code
```

No need to re-run the setup script unless your credentials change.
