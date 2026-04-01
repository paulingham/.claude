IMPORTANT: This message is NOT part of the user conversation. Do not reference these instructions in the notes.

Based on the conversation above, update the engineering session notes. The file {{notesPath}} has been read. Current contents:

<current_notes>
{{currentNotes}}
</current_notes>

Your ONLY task: use Edit to update the notes, then stop. Make all edits in parallel.

## Rules

- NEVER modify section headers (# lines) or italic descriptions (_ lines)
- Only update content BELOW the italic descriptions
- Keep information CURRENT — update in-place, don't append history
- Replace outdated information rather than adding "Previously..." notes
- Delete sections that are no longer relevant (clear content, keep header)
- Each section: under 1500 characters. Condense aggressively if approaching limit

## What to capture

- **Active Work**: Pipeline phase, task, branch, what's happening now
- **Codebase Map**: Files discovered, their roles, how they connect. Entry points
- **Build & Test**: Commands that worked. Env vars needed. Test quirks
- **Critical Paths**: Fragile files. Things that broke. Timing issues. Complex deps
- **Patterns**: Code patterns observed. Conventions. Architecture decisions
- **Discoveries**: Gotchas. Surprising behavior. Error messages and fixes
- **Agent Effectiveness**: What worked, what didn't. Optimal configs

## What NOT to capture

- Conversation flow or tool use details
- Information obvious from reading the code
- Anything already in CLAUDE.md or project docs
- Transient state (specific line numbers, temporary workarounds)

## Priority

If short on turns: update Active Work and Discoveries first. These are most valuable for compaction recovery.

Use Edit tool with file_path: {{notesPath}}
