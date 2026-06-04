#!/usr/bin/env python3
"""
B10 write-verb scanner — shared helper for test-harness-paths.sh.

Usage:
  python3 b10-scan.py <root_dir> <scan_dir1> [scan_dir2 ...]

Scans <scan_dirN> (relative to <root_dir>) for .md files containing a
write-verb-anchored bare pipeline-state/ path (a known violation of the
HARNESS_DATA relocation requirement).

Verb set covers both Title-case forms and lowercase forms that appear in
description fields and prose:
  Write|Writes|writes|Create|Creates|Persist|persist|persisted|
  Append|append|mkdir|touch|written|
  outputPath: | > pipeline-state | >> pipeline-state

A line is flagged when it matches VERB_PAT AND BARE_PATH_PAT.
BARE_PATH_PAT accepts pipeline-state/ NOT already prefixed by a known-good
resolution form ($HARNESS_DATA, $CLAUDE_PLUGIN_DATA, $CLAUDE_CONFIG_DIR,
state_dir).

Excluded files: PORTING-NOTES.md, ROLLOUT.md (M7 doc-prose, B10-exempt).

Prints the violation count on stdout.
"""
import os
import re
import sys

VERB_PAT = re.compile(
    # Title-case forms (original set)
    r'\b(Write|Writes|Create|Creates|Persist|persist|persisted|'
    r'Append|append|mkdir|touch|written)\b'
    # Lowercase prose forms: write/writes (lookbehind excludes dual-write, overwrite, rewrite)
    r'|(?<!-)\bwrites?\b'
    r'|outputPath:|> pipeline-state|>> pipeline-state'
)

BARE_PATH_PAT = re.compile(
    r'(?<!\$\{HARNESS_DATA\}/)(?<!\$HARNESS_DATA/)'
    r'(?<!\$\{CLAUDE_PLUGIN_DATA)(?<!\$\{CLAUDE_CONFIG_DIR)'
    r'(?<!state_dir\}/)(?<!state_dir/)pipeline-state/'
)

EXCLUDED_FILES = {'PORTING-NOTES.md', 'ROLLOUT.md'}


def scan_dir(root: str, rel: str) -> int:
    count = 0
    dir_path = os.path.join(root, rel)
    if not os.path.isdir(dir_path):
        return 0
    for d, dirs, files in os.walk(dir_path):
        dirs[:] = [x for x in dirs if x not in ('.git',)]
        for f in files:
            if not f.endswith('.md') or f in EXCLUDED_FILES:
                continue
            path = os.path.join(d, f)
            with open(path, errors='replace') as fp:
                for line in fp:
                    if VERB_PAT.search(line) and BARE_PATH_PAT.search(line):
                        count += 1
    return count


def main() -> None:
    if len(sys.argv) < 3:
        sys.stderr.write(
            'usage: b10-scan.py <root_dir> <rel_dir1> [rel_dir2 ...]\n'
        )
        sys.exit(2)
    root = sys.argv[1]
    total = sum(scan_dir(root, rel) for rel in sys.argv[2:])
    print(total)


if __name__ == '__main__':
    main()
