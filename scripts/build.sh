#!/bin/bash

# Nexus Build Script
# Usage: ./scripts/build.sh [mac|win|all]

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

TARGET=${1:-"mac"}

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Nexus Build                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_DIR"

# Activate Python venv
source "$BACKEND_DIR/.venv/bin/activate"

echo -e "${YELLOW}[1/3]${NC} Building Python backend..."

# Build Python with PyInstaller
cd "$BACKEND_DIR"
pyinstaller --onefile --name main \
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
cp dist/main "$PROJECT_DIR/backend-dist/"
echo -e "       ${GREEN}✓${NC} Backend built"

cd "$PROJECT_DIR"

echo -e "${YELLOW}[2/3]${NC} Building frontend..."

# Build frontend
if command -v pnpm &> /dev/null; then
    pnpm run build:$TARGET
else
    npm run build:$TARGET
fi

echo -e "${YELLOW}[3/3]${NC} Build complete!"
echo ""
echo -e "${GREEN}Output:${NC} $PROJECT_DIR/release/"
echo ""
