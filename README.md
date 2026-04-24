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

## Сборка `.exe` на Windows (быстрый старт)

Скрипт `scripts/build.ps1` сам скачивает и ставит всё необходимое
(Python 3.11, Git, Node.js LTS, pnpm) через `winget`, собирает бэкенд
через PyInstaller и делает NSIS-инсталлер через electron-builder.

**Что нужно заранее:**

- Windows 10 (версия 1809+) или Windows 11 — в них уже есть `winget`.
  Если `winget` отсутствует, поставьте «App Installer» из Microsoft Store.
- При **первом запуске** нужен PowerShell, запущенный **от имени
  администратора** (winget ставит Git и Node.js в `Program Files`).
  Повторные сборки можно запускать без админа.

**Как запустить:**

1. Скачайте / склонируйте репозиторий на Windows-машину.
2. Нажмите «Пуск» → наберите `PowerShell` → правый клик →
   **«Запуск от имени администратора»**.
3. Перейдите в папку проекта:
   ```powershell
   cd C:\путь\к\Nexus
   ```
4. Запустите скрипт:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build.ps1
   ```

Первый запуск занимает 5–15 минут (скачивание Python/Node/зависимостей).
Готовый установщик появится в `release\Nexus Setup <версия>.exe`.

**Полезные флаги:**

```powershell
# Пересобрать только UI (бэкенд уже собран):
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipBackend

# Собрать только бэкенд-бинарник:
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipFrontend
```

**Если что-то пошло не так:**

- Ошибка «winget is not available» → откройте Microsoft Store, установите
  «App Installer», перезапустите PowerShell.
- Ошибка «winget failed to install …» → убедитесь, что PowerShell запущен
  от имени администратора.
- После установки Python/Node сообщается «…is not on PATH» → закройте
  окно PowerShell, откройте новое (от админа) и запустите скрипт снова.
