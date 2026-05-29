#!/usr/bin/env python3
"""Find files still containing old Type-A patterns."""
import glob

OLD_PATTERNS = [
    "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/",
    "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh",
    "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh",
]


def main():
    files = sorted(glob.glob("hooks/*.sh") + glob.glob("hooks/_lib/*.sh"))
    total = 0
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()
        for pat in OLD_PATTERNS:
            count = content.count(pat)
            if count > 0:
                total += count
                print(f"{fpath}: {count} occurrences of: {pat}")
                for i, line in enumerate(content.splitlines(), 1):
                    if pat in line:
                        print(f"  line {i}: {line.strip()}")
    print(f"\nTotal remaining: {total}")


if __name__ == "__main__":
    main()
