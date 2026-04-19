"""Embedder CLI: doctor | status | setup.

doctor — probe configured backend, print ok/error line to stdout.
status — write JSON health payload to CLAUDE_EMBEDDER_STATUS path.
setup  — print setup instructions (ORT_DYLIB_PATH, BGE_MODEL_PATH).
"""
import sys

from embedder._lib import cli_actions

COMMANDS = {"doctor": cli_actions.doctor,
            "status": cli_actions.status,
            "setup": cli_actions.setup}


def main(argv):
    cmd = (argv or ["doctor"])[0]
    return COMMANDS.get(cmd, cli_actions.setup)()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
