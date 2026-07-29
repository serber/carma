#!/bin/sh
# One-command install: clones carma (or updates an existing checkout) and
# runs scripts/install.sh. For a bare-metal Pi with nothing on it yet:
#
#   curl -fsSL https://raw.githubusercontent.com/serber/carma/development/scripts/bootstrap.sh | bash
#
# (swap "development" for the branch/tag you want to deploy). See
# README.md for what install.sh actually sets up.
set -eu

REPO_URL="https://github.com/serber/carma.git"
BRANCH="${CARMA_BRANCH:-development}"
CLONE_DIR="${CARMA_CLONE_DIR:-$HOME/carma-app}"

if ! command -v git >/dev/null 2>&1; then
    echo "==> installing git"
    sudo apt-get update
    sudo apt-get install -y git
fi

if [ -d "$CLONE_DIR/.git" ]; then
    echo "==> updating existing checkout at $CLONE_DIR"
    git -C "$CLONE_DIR" fetch origin "$BRANCH"
    git -C "$CLONE_DIR" checkout "$BRANCH"
    git -C "$CLONE_DIR" reset --hard "origin/$BRANCH"
else
    echo "==> cloning $REPO_URL ($BRANCH) to $CLONE_DIR"
    git clone -b "$BRANCH" "$REPO_URL" "$CLONE_DIR"
fi

exec sudo "$CLONE_DIR/scripts/install.sh"
