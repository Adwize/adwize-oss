#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Adwize/adwize-oss.git"
INSTALL_DIR="${ADWIZE_DIR:-$HOME/adwize}"

BOLD=$'\033[1m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
RED=$'\033[0;31m'
DIM=$'\033[2m'
NC=$'\033[0m'
BOLD_CYAN=$'\033[1;36m'
BOLD_BLUE=$'\033[1;34m'
BOLD_MAGENTA=$'\033[1;35m'
BOLD_GREEN=$'\033[1;32m'

info()  { echo "${GREEN}▸${NC} $1"; }
warn()  { echo "${YELLOW}▸${NC} $1"; }
error() { echo "${RED}✗${NC} $1"; exit 1; }

echo ""
echo "${BOLD_CYAN}     █████╗ ${BOLD_BLUE}██████╗ ${BOLD_MAGENTA}██╗    ██╗${BOLD_GREEN}██╗${BOLD_CYAN}███████╗${BOLD_BLUE}███████╗${NC}"
echo "${BOLD_CYAN}    ██╔══██╗${BOLD_BLUE}██╔══██╗${BOLD_MAGENTA}██║    ██║${BOLD_GREEN}██║${BOLD_CYAN}╚══███╔╝${BOLD_BLUE}██╔════╝${NC}"
echo "${BOLD_CYAN}    ███████║${BOLD_BLUE}██║  ██║${BOLD_MAGENTA}██║ █╗ ██║${BOLD_GREEN}██║${BOLD_CYAN}  ███╔╝ ${BOLD_BLUE}█████╗  ${NC}"
echo "${BOLD_CYAN}    ██╔══██║${BOLD_BLUE}██║  ██║${BOLD_MAGENTA}██║███╗██║${BOLD_GREEN}██║${BOLD_CYAN} ███╔╝  ${BOLD_BLUE}██╔══╝  ${NC}"
echo "${BOLD_CYAN}    ██║  ██║${BOLD_BLUE}██████╔╝${BOLD_MAGENTA}╚███╔███╔╝${BOLD_GREEN}██║${BOLD_CYAN}███████╗${BOLD_BLUE}███████╗${NC}"
echo "${BOLD_CYAN}    ╚═╝  ╚═╝${BOLD_BLUE}╚═════╝ ${BOLD_MAGENTA} ╚══╝╚══╝ ${BOLD_GREEN}╚═╝${BOLD_CYAN}╚══════╝${BOLD_BLUE}╚══════╝${NC}"
echo ""
echo "    ${DIM}Open-source event monitoring with deterministic rules${NC}"
echo "    ${DIM}and webhook alerts.${NC}"
echo ""

# --- Checks ---

command -v git >/dev/null 2>&1 || error "git is required. Install it: https://git-scm.com"
command -v docker >/dev/null 2>&1 || error "Docker is required. Install Docker Desktop: https://docs.docker.com/get-docker/"

docker info >/dev/null 2>&1 || error "Docker daemon is not running. Please start Docker Desktop."

if command -v uv >/dev/null 2>&1; then
    info "uv found: $(uv --version)"
else
    warn "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    info "uv installed: $(uv --version)"
fi

# --- Clone ---

if [ -d "$INSTALL_DIR" ]; then
    warn "Directory $INSTALL_DIR already exists."
    read -p "  Update existing installation? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        info "Updating..."
        cd "$INSTALL_DIR"
        git pull --ff-only || warn "Could not fast-forward. Manual update may be needed."
    else
        info "Keeping existing installation."
    fi
else
    info "Cloning Adwize to $INSTALL_DIR..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# --- Install CLI ---

info "Installing Adwize CLI..."
uv sync --quiet 2>/dev/null || uv sync

if ! command -v adwize >/dev/null 2>&1; then
    info "Adding adwize to PATH..."

    SHELL_NAME=$(basename "$SHELL")
    case "$SHELL_NAME" in
        zsh)  RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bashrc" ;;
        fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
        *)    RC_FILE="$HOME/.profile" ;;
    esac

    VENV_BIN="$INSTALL_DIR/.venv/bin"
    if [ -d "$VENV_BIN" ]; then
        if ! grep -q "adwize" "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# Adwize CLI" >> "$RC_FILE"
            echo "export PATH=\"$VENV_BIN:\$PATH\"" >> "$RC_FILE"
            info "Added $VENV_BIN to PATH in $RC_FILE"
        fi
        export PATH="$VENV_BIN:$PATH"
    fi
fi

echo ""
echo "  ${BOLD_GREEN}✓ Adwize installed successfully!${NC}"
echo ""
echo "  ${DIM}Next steps:${NC}"
echo "    ${BOLD_CYAN}cd $INSTALL_DIR${NC}"
echo "    ${BOLD_CYAN}adwize setup${NC}"
echo ""
echo "  ${DIM}This will configure your .env and start services via Docker Compose.${NC}"
echo ""
