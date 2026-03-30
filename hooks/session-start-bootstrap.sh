#!/bin/bash
# Session-start hook: bootstrap skill awareness and iron laws
# Outputs a concise skill directory reminder so the model knows what skills exist

echo "SKILL AWARENESS BOOTSTRAP:"
echo "Entry: /intake (classify + route) | /pipeline (drive phases)"
echo "Build: /build-implementation, /refactor, /bug-fix"
echo "Review: /code-review + /security-review (parallel)"
echo "Verify: /verify | Test: /qa-test-strategy | Accept: /product-acceptance"
echo "Ship: /pr-creation | Deploy: /deploy + /deployment-verification"
echo "Scaffold: /api-scaffold, /db-migration, /infra-scaffold, /design-system-init"
echo "Plan: /epic-breakdown, /estimation, /story-writing, /tech-spike"
echo "Debug: /debug (persistent state for complex bugs)"
echo "Utils: /forensics (post-incident investigation) | /workstream (parallel feature isolation)"

# Learning system
LEARNING_DIR="$HOME/.claude/learning"
if [[ -d "$LEARNING_DIR" ]]; then
    INSTINCT_COUNT=$(find "$LEARNING_DIR/instincts" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$INSTINCT_COUNT" -gt 0 ]]; then
        echo ""
        echo "LEARNED PATTERNS ($INSTINCT_COUNT instincts):"
        # Show top 5 by confidence
        for f in $(grep -l "confidence:" "$LEARNING_DIR/instincts/"*.md 2>/dev/null | head -5); do
            CONF=$(grep "confidence:" "$f" | head -1 | awk '{print $2}')
            PATTERN=$(grep "^## Pattern" -A1 "$f" | tail -1)
            echo "  [$CONF] $PATTERN"
        done
    fi
fi

echo ""
echo "IRON LAWS:"
echo "- NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
echo "- NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"
echo "- THE ORCHESTRATOR NEVER WRITES SOURCE CODE"
echo "- NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED."
