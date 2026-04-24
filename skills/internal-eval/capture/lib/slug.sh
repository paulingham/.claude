#!/usr/bin/env bash
# Slugify a string (CLI wrapper). Same logic as slug_fn.sh.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/slug_fn.sh"
slugify "$1"
