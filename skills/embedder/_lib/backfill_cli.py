"""CLI argument parsing + stdout summary for backfill."""
import argparse

FORMAT = ("BACKFILL processed={processed} inserted={inserted} "
          "skipped={skipped} errors={errors}\n")


def parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    return p.parse_args(argv)


def format_summary(stats):
    return FORMAT.format(**stats)
