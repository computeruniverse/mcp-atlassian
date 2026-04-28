# Windows Setup Guide

> **Important**: Always run the server from the cloned repository — never install from PyPI.

---

## Prerequisites

### 1. Install Git

Download and install from https://git-scm.com/download/win. Use default settings.

### 2. Install Python ≥ 3.10

Download from https://www.python.org/downloads/windows/. During installation, check **"Add Python to PATH"**.

### 3. Install `uv`

Open PowerShell and run:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Restart your terminal after installation so `uv` is on your PATH.

---

## Clone and install

```powershell
git clone https://github.com/computeruniverse/mcp-atlassian.git
cd mcp-atlassian
uv sync --frozen --all-extras --dev
```

This installs all dependencies (including `tzdata`, which is Windows-only) into a local `.venv`.

---

## Configure credentials

Copy `.env.example` to `.env` and fill in your Atlassian credentials:

```powershell
copy .env.example .env
```

Open `.env` in any editor and set at minimum:

```
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your.email@example.com
JIRA_API_TOKEN=your_jira_api_token_here

CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_USERNAME=your.email@example.com
CONFLUENCE_API_TOKEN=your_confluence_api_token_here
```

Get API tokens from: https://id.atlassian.com/manage-profile/security/api-tokens

---

## Verify the server starts

```powershell
uv run mcp-atlassian -v
```

You should see startup logs with no errors. Press `Ctrl+C` to stop.

---

## Configure Claude Code (MCP client)

Claude Code needs to know how to launch the server. The config file lives at:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Add the following entry (adjust the path to where you cloned the repo):

```json
{
  "mcpServers": {
    "mcp-atlassian": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:\\Users\\YourName\\path\\to\\mcp-atlassian",
        "mcp-atlassian"
      ],
      "env": {}
    }
  }
}
```

Using `uv run --directory <repo>` ensures the server always runs from the local repo source, not any installed package.

Credentials are read from the `.env` file in the repo root — no need to repeat them in the config.

---

## Windows-specific notes

| Topic | Detail |
| --- | --- |
| **Event loop** | The server sets `WindowsSelectorEventLoopPolicy` automatically to avoid high CPU usage. |
| **Timezone data** | `tzdata` is installed automatically on Windows (handled in `pyproject.toml`). |
| **Line endings** | `.gitattributes` and Ruff's `line-ending = "auto"` handle CRLF/LF differences. |
| **Paths** | Use double backslashes (`\\`) or forward slashes (`/`) in JSON config files. |
| **SIGPIPE** | Not available on Windows; the server handles this gracefully in `lifecycle.py`. |

---

## Troubleshooting

**`uv` not found after install**
Restart your terminal, or add `%USERPROFILE%\.local\bin` to your PATH manually.

**`uv run mcp-atlassian` exits immediately**
Check that `.env` exists in the repo root and contains valid credentials.

**Claude Code does not show the mcp-atlassian tools**
- Confirm the path in `claude_desktop_config.json` uses double backslashes or forward slashes.
- Restart Claude Code after editing the config.
- Run `uv run mcp-atlassian -v` manually first to confirm the server starts cleanly.
