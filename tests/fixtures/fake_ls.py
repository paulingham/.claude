"""Stdio Language Server double for tests.

Reads Content-Length-framed JSON-RPC requests and replies with canned
responses for initialize and textDocument/definition.  Pass --hang to
read one request then block forever (exercises the select-timeout path).
"""
import argparse
import json
import os
import sys


def _stdin():
    return sys.stdin.buffer


def _stdout():
    return sys.stdout.buffer


def _read_request():
    while True:
        line = _stdin().readline()
        if not line or line == b"\r\n":
            continue
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":")[1].strip())
            _stdin().readline()
            return json.loads(_stdin().read(length))


def _send_response(obj):
    body = json.dumps(obj).encode()
    _stdout().write(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
    _stdout().flush()


def _handle_initialize(req_id):
    _send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "capabilities": {"definitionProvider": True},
            "serverInfo": {"name": "fake-ls", "version": "0.0.1"},
        },
    })


def _handle_definition(req_id):
    _send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": [{
            "uri": "file:///project/src/main.ts",
            "range": {
                "start": {"line": 10, "character": 4},
                "end": {"line": 10, "character": 10},
            },
        }],
    })


def _dispatch(req):
    method = req.get("method", "")
    req_id = req.get("id")
    if method == "initialize":
        _handle_initialize(req_id)
    elif method == "initialized":
        pass
    elif method == "textDocument/definition":
        _handle_definition(req_id)
    elif method == "shutdown":
        _send_response({"jsonrpc": "2.0", "id": req_id, "result": None})


def _loop_normal():
    while True:
        try:
            req = _read_request()
        except (EOFError, ValueError):
            break
        _dispatch(req)


def _loop_hang():
    req = _read_request()
    if req.get("method") == "initialize":
        _handle_initialize(req.get("id"))
    _stdin().read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hang", action="store_true")
    args = parser.parse_args()
    if args.hang:
        _loop_hang()
    else:
        _loop_normal()


if __name__ == "__main__":
    main()
