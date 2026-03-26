#!/bin/bash

# Nexus Build Script
# Usage: ./scripts/build.sh [mac|win]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

HOST_OS="$(uname -s)"

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    case "$HOST_OS" in
        MINGW*|MSYS*|CYGWIN*|Windows_NT)
            TARGET="win"
            ;;
        *)
            TARGET="mac"
            ;;
    esac
fi

if [ "$TARGET" != "mac" ] && [ "$TARGET" != "win" ]; then
    echo -e "${RED}ERROR:${NC} Unsupported build target '$TARGET'. Use 'mac' or 'win'."
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Nexus Build                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_DIR"

# Guard against producing Windows installer with non-Windows backend binary.
if [ "$TARGET" = "win" ]; then
    case "$HOST_OS" in
        MINGW*|MSYS*|CYGWIN*|Windows_NT)
            ;;
        *)
            if [ "${NEXUS_ALLOW_UNSUPPORTED_WIN_BUILD:-0}" != "1" ]; then
                echo -e "${RED}ERROR:${NC} Windows build with bundled backend must run on a Windows host."
                echo "Set NEXUS_ALLOW_UNSUPPORTED_WIN_BUILD=1 to bypass for UI-only/debug packaging."
                exit 1
            fi
            echo -e "${YELLOW}WARNING:${NC} Building win target on $HOST_OS with override; backend binary may be incompatible."
            ;;
    esac
fi

# Activate Python venv
source "$BACKEND_DIR/.venv/bin/activate"

echo -e "${YELLOW}[1/3]${NC} Building Python backend..."

# Build Python with PyInstaller
cd "$BACKEND_DIR"
pyinstaller -y --onedir --name main \
    --hidden-import=aiosqlite \
    --hidden-import=uvicorn.logging \
    --hidden-import=uvicorn.loops \
    --hidden-import=uvicorn.loops.auto \
    --hidden-import=uvicorn.protocols \
    --hidden-import=uvicorn.protocols.http \
    --hidden-import=uvicorn.protocols.http.auto \
    --hidden-import=uvicorn.protocols.websockets \
    --hidden-import=uvicorn.protocols.websockets.auto \
    --hidden-import=uvicorn.lifespan \
    --hidden-import=uvicorn.lifespan.on \
    --add-data "database:database" \
    --add-data "api:api" \
    --add-data "telegram:telegram" \
    main.py

# Move to backend-dist
mkdir -p "$PROJECT_DIR/backend-dist"
rm -rf "$PROJECT_DIR/backend-dist/main"
cp -R dist/main "$PROJECT_DIR/backend-dist/main"
echo -e "       ${GREEN}✓${NC} Backend built"

cd "$PROJECT_DIR"

echo -e "${YELLOW}[2/3]${NC} Building frontend..."

# Build frontend
if command -v pnpm &> /dev/null; then
    pnpm run package:$TARGET
else
    npm run package:$TARGET
fi

echo -e "${YELLOW}[3/3]${NC} Build complete!"
echo ""
echo -e "${GREEN}Output:${NC} $PROJECT_DIR/release/"
echo ""
