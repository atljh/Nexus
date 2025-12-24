# Nexus

Desktop app for Telegram automation.

## Requirements

- Python 3.11+
- Node.js 18+
- pnpm (recommended) or npm

## Quick Start

```bash
# Initial setup (first time only)
./scripts/setup.sh

# Start development
./scripts/dev.sh
```

Or using npm/pnpm:

```bash
# Setup
pnpm setup

# Development
pnpm start
```

## Project Structure

```
nexus/
├── electron/          # Electron main process
│   ├── main.ts        # Main window, IPC handlers
│   └── preload.ts     # Context bridge API
├── src/               # Vue 3 frontend
│   ├── pages/         # Route pages
│   ├── layouts/       # Layout components
│   └── assets/        # CSS, images
├── backend/           # Python FastAPI backend
│   ├── api/           # REST endpoints
│   ├── database/      # SQLAlchemy models
│   └── telegram/      # Telethon integration
└── scripts/           # Build & dev scripts
```

## Features

- **Account Import**: tdata, JSON sessions, session strings
- **Proxy Management**: SOCKS4/5, HTTP/HTTPS with auth
- **Account Groups & Tags**: Organize accounts
- **Session Validation**: Check account status

## Build

```bash
# macOS
./scripts/build.sh mac

# Windows
./scripts/build.sh win
```

Output: `release/`
