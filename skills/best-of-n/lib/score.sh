#!/usr/bin/env bash
# Pure-bash scoring helpers for /best-of-n. Integer math only.
# Exports: score_candidate, pick_winner, check_budget_gate.

score_candidate() {
  local test_pass="$1" violations="$2" quality="$3" diff="$4"
  local shape=$(( 10 - violations ))
  [ "$shape" -lt 0 ] && shape=0
  echo $(( test_pass*1000 + shape*10 + quality*20 - diff/100 ))
}

pick_winner() {
  sort -t'|' -k2,2nr -k3,3n -k4,4n | head -n1 | cut -d'|' -f1
}

check_budget_gate() {
  local budget="$1"
  [ "$budget" -ge 7 ] && echo "OK" || echo "WRONG_SKILL"
}

export -f score_candidate pick_winner check_budget_gate
