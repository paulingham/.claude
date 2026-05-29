#!/usr/bin/env python3
"""Apply Type-A source-line rewrites for plugin portability."""
import os
import glob

REPLACEMENTS = [
    (
        '${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/',
        '${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/'
    ),
    (
        '${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh',
        '${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh'
    ),
    (
        '${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh',
        '${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/loop-guard.sh'
    ),
]


def rewrite_file(fpath):
    with open(fpath, 'r', encoding='utf-8') as fh:
        content = fh.read()
    new_content = content
    count = 0
    for old, new in REPLACEMENTS:
        occurrences = new_content.count(old)
        if occurrences > 0:
            new_content = new_content.replace(old, new)
            count += occurrences
    if new_content != content:
        with open(fpath, 'w', encoding='utf-8') as fh:
            fh.write(new_content)
    return count


def main():
    files = sorted(glob.glob('hooks/*.sh') + glob.glob('hooks/_lib/*.sh'))
    changed = {}
    for fpath in files:
        n = rewrite_file(fpath)
        if n > 0:
            changed[fpath] = n
            print(f"  patched ({n} rewrites): {fpath}")
    print(f"\nTotal files changed: {len(changed)}")
    print(f"Total Type-A rewrites: {sum(changed.values())}")


if __name__ == '__main__':
    main()
