#!/bin/bash

# Nexus Initial Setup Script
# Usage: ./scripts/setup.sh

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

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Nexus Initial Setup        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_DIR"

# Check requirements
echo -e "${YELLOW}Checking requirements...${NC}"

# Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    echo "  Install: brew install python3"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3: $(python3 --version)"

# Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js is not installed${NC}"
    echo "  Install: brew install node"
    exit 1
fi
echo -e "${GREEN}✓${NC} Node.js: $(node --version)"

# pnpm (optional but preferred)
if command -v pnpm &> /dev/null; then
    echo -e "${GREEN}✓${NC} pnpm: $(pnpm --version)"
    PKG_MANAGER="pnpm"
else
    echo -e "${YELLOW}!${NC} pnpm not found, using npm"
    PKG_MANAGER="npm"
fi

echo ""
echo -e "${YELLOW}Setting up Python environment...${NC}"

# Create venv
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    python3 -m venv "$BACKEND_DIR/.venv"
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment exists"
fi

# Activate and install
source "$BACKEND_DIR/.venv/bin/activate"
pip install --upgrade pip -q
pip install -r "$BACKEND_DIR/requirements.txt" -q
touch "$BACKEND_DIR/.venv/.deps_installed"
echo -e "${GREEN}✓${NC} Python dependencies installed"

echo ""
echo -e "${YELLOW}Setting up Node.js environment...${NC}"

# Install Node dependencies
$PKG_MANAGER install
echo -e "${GREEN}✓${NC} Node.js dependencies installed"

echo ""
echo -e "${GREEN}╔════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Setup Complete!            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════╝${NC}"
echo ""
echo -e "Run ${BLUE}./scripts/dev.sh${NC} to start development"
echo ""
