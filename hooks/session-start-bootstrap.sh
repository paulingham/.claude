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
echo ""
echo "IRON LAWS:"
echo "- NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
echo "- NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"
echo "- THE ORCHESTRATOR NEVER WRITES SOURCE CODE"
echo "- NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED."
