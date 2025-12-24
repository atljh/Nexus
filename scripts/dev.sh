#!/bin/bash

# Nexus Development Startup Script
# Usage: ./scripts/dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Nexus Development          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_DIR"

# Check Python
echo -e "${YELLOW}[1/4]${NC} Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "       ${GREEN}✓${NC} $PYTHON_VERSION"

# Setup Python venv
echo -e "${YELLOW}[2/4]${NC} Setting up Python environment..."
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "       Creating virtual environment..."
    python3 -m venv "$BACKEND_DIR/.venv"
fi

source "$BACKEND_DIR/.venv/bin/activate"

# Install Python dependencies
if [ ! -f "$BACKEND_DIR/.venv/.deps_installed" ] || [ "$BACKEND_DIR/requirements.txt" -nt "$BACKEND_DIR/.venv/.deps_installed" ]; then
    echo "       Installing Python dependencies..."
    pip install -q --upgrade pip
    pip install -q -r "$BACKEND_DIR/requirements.txt"
    touch "$BACKEND_DIR/.venv/.deps_installed"
    echo -e "       ${GREEN}✓${NC} Dependencies installed"
else
    echo -e "       ${GREEN}✓${NC} Dependencies up to date"
fi

# Check Node.js
echo -e "${YELLOW}[3/4]${NC} Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "       ${GREEN}✓${NC} Node.js $NODE_VERSION"

# Install Node dependencies
if [ ! -d "$PROJECT_DIR/node_modules" ] || [ "$PROJECT_DIR/package.json" -nt "$PROJECT_DIR/node_modules/.package-lock.json" ]; then
    echo "       Installing Node.js dependencies..."
    if command -v pnpm &> /dev/null; then
        pnpm install --silent
    elif command -v npm &> /dev/null; then
        npm install --silent
    else
        echo -e "${RED}Error: pnpm or npm is not installed${NC}"
        exit 1
    fi
    echo -e "       ${GREEN}✓${NC} Dependencies installed"
else
    echo -e "       ${GREEN}✓${NC} Dependencies up to date"
fi

# Start development servers
echo -e "${YELLOW}[4/4]${NC} Starting development servers..."
echo ""
echo -e "${GREEN}Starting Nexus...${NC}"
echo -e "  Frontend: ${BLUE}http://localhost:5173${NC}"
echo -e "  Backend:  ${BLUE}http://localhost:8000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Run with pnpm or npm
if command -v pnpm &> /dev/null; then
    pnpm dev
else
    npm run dev
fi
