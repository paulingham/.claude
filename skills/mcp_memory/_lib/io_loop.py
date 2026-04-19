"""Newline-delimited JSON-RPC read/dispatch/write loop over stdio streams."""
import json

from mcp_memory._lib import rpc


def serve(stdin, stdout, dispatcher):
    for line in stdin:
        _handle_line(line, stdout, dispatcher)


def _handle_line(line, stdout, dispatcher):
    stripped = line.strip()
    if not stripped:
        return
    _emit(stdout, _dispatch_or_parse_error(stripped, dispatcher))


def _dispatch_or_parse_error(text, dispatcher):
    try:
        return dispatcher(rpc.parse(text))
    except rpc.ParseError as exc:
        return rpc.error(None, rpc.PARSE_ERROR, f"parse error: {exc}")


def _emit(stdout, response):
    if response is None:
        return
    stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    stdout.flush()
