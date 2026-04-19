"""argparse CLI wrapper — emits JSON envelope."""
import argparse
import json
import sys
from recall import recall
from recall._lib import envelope


def main(argv=None):
    args = _parse(argv)
    raw = _invoke(args, args.limit + 1)
    env = _env(args.tier, raw, args.limit)
    print(json.dumps(env, separators=(",", ":")))
    return 0


def _env(tier, raw, limit):
    return envelope.envelope(tier, raw[:limit], limit, fetched=len(raw))


def _invoke(args, limit):
    if args.tier == "search":
        return recall.search(args.query, limit=limit,
                             source=args.source, db_path=args.db)
    return recall.timeline(limit=limit, source=args.source,
                           db_path=args.db)


_SEARCH = ("both", "observations", "scratchpad")
_TL = ("observations", "scratchpad")


def _parse(argv):
    p = argparse.ArgumentParser(prog="recall")
    sub = p.add_subparsers(dest="tier", required=True)
    _common(sub.add_parser("search"), _SEARCH, 20).add_argument("query")
    _common(sub.add_parser("timeline"), _TL, 50)
    return p.parse_args(argv)


def _common(p, sources, lim):
    p.add_argument("--source", choices=sources, default=sources[0])
    p.add_argument("--limit", type=int, default=lim)
    p.add_argument("--db", default=None)
    return p


if __name__ == "__main__":
    sys.exit(main())
