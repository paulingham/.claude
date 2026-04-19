"""argparse CLI wrapper — emits JSON envelope."""
import argparse
import json
import sys
from recall import recall
from recall._lib import envelope


def main(argv=None):
    args = _parse(argv)
    hits = _invoke(args)
    env = envelope.envelope(args.tier, hits, args.limit)
    print(json.dumps(env, separators=(",", ":")))
    return 0


def _invoke(args):
    if args.tier == "search":
        return recall.search(args.query, limit=args.limit,
                             source=args.source, db_path=args.db)
    return recall.timeline(limit=args.limit, source=args.source,
                           db_path=args.db)


def _parse(argv):
    p = argparse.ArgumentParser(prog="recall")
    sub = p.add_subparsers(dest="tier", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    _add_common(s, ("both", "observations", "scratchpad"), 20)
    _add_common(sub.add_parser("timeline"),
                ("observations", "scratchpad"), 50)
    return p.parse_args(argv)


def _add_common(p, sources, default_limit):
    p.add_argument("--source", choices=sources, default=sources[0])
    p.add_argument("--limit", type=int, default=default_limit)
    p.add_argument("--db", default=None)


if __name__ == "__main__":
    sys.exit(main())
