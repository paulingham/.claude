#!/usr/bin/env bash
# Exact scoring: candidate diff must byte-equal the golden diff.

# score_exact <golden-patch> <candidate-patch> → rc 0 if byte-equal else rc 1.
score_exact() {
  cmp -s "$1" "$2"
}
