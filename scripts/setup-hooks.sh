#!/bin/sh
# Point git at the repo-managed hooks directory (ROM commit guard).
set -e
cd "$(dirname "$0")/.."
git config core.hooksPath scripts/git-hooks
echo "core.hooksPath -> scripts/git-hooks"
