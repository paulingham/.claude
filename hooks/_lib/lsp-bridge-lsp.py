"""LSP process I/O helpers for the go-to-definition bridge.

No threads: every blocking read is guarded by select.select() on a
monotonic deadline in the MAIN thread.
"""
import json
import os
import select
import time
from typing import NamedTuple
_LS_CANDIDATES = {
    "ts": ["typescript-language-server", "tsserver"],
    "py": ["pyright-langserver", "pyright"],
}
_TIMEOUT_SECONDS = 10
class Position(NamedTuple):
    """Bundle of (path, line, character) — keeps function params ≤4."""
    path: str
    line: int
    character: int
class _LsTimeout(Exception):
    """Raised when select deadline expires waiting for LS output."""
def resolve_binary(lang):
    import shutil
    for candidate in _LS_CANDIDATES.get(lang, []):
        found = shutil.which(candidate)
        if found:
            return found
    return None
def run_definition(proc_factory, lang, pos):
    binary = resolve_binary(lang)
    if binary is None:
        return _err("ls-unavailable", f"No LS binary for lang={lang}")
    return _run_with_proc(proc_factory(binary), pos)
def _run_with_proc(proc, pos):
    try:
        return _execute_definition(proc, pos)
    finally:
        _cleanup(proc)
def _execute_definition(proc, pos):
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    try:
        return _resolve_ok(proc, pos, deadline)
    except _LsTimeout:
        return _err("ls-timeout", "LS did not respond within deadline")
    except Exception as exc:
        return _err("ls-unavailable", str(exc))
def _resolve_ok(proc, pos, deadline):
    _handshake(proc, deadline)
    locations = _request_definition(proc, pos, deadline)
    return _ok_envelope({"definitions": _flatten(locations)})
def _handshake(proc, deadline):
    _send_request(proc, 1, "initialize", _init_params())
    _read_frame(proc, deadline)
    _send_notification(proc, "initialized", {})
def _init_params():
    return {"processId": os.getpid(), "rootUri": None, "capabilities": {}}
def _request_definition(proc, pos, deadline):
    _send_request(proc, 2, "textDocument/definition", _def_params(pos))
    frame = _read_frame(proc, deadline)
    return frame.get("result") or []
def _def_params(pos):
    return {
        "textDocument": {"uri": f"file://{pos.path}"},
        "position": {"line": pos.line, "character": pos.character},
    }
def _send_request(proc, req_id, method, params):
    _write_frame(proc, {"jsonrpc": "2.0", "id": req_id,
                        "method": method, "params": params})
def _send_notification(proc, method, params):
    _write_frame(proc, {"jsonrpc": "2.0", "method": method, "params": params})
def _write_frame(proc, obj):
    body = json.dumps(obj).encode()
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()
    proc.stdin.write(header + body)
    proc.stdin.flush()
def _raw_out(proc):
    raw = proc.stdout
    return raw.raw if hasattr(raw, "raw") else raw
def _read_frame(proc, deadline):
    length = _read_header(proc, deadline)
    return _read_body(proc, length, deadline)
def _read_header(proc, deadline):
    raw = _raw_out(proc)
    while True:
        line = _read_raw_line(raw, deadline)
        if line.lower().startswith(b"content-length:"):
            _read_raw_line(raw, deadline)
            return int(line.split(b":", 1)[1].strip())
def _read_raw_line(raw, deadline):
    result = b""
    while not result.endswith(b"\n"):
        _await_readable(raw, deadline)
        ch = raw.read(1)
        if not ch:
            raise EOFError()
        result += ch
    return result
def _read_body(proc, length, deadline):
    return json.loads(_read_exactly(_raw_out(proc), length, deadline).decode())
def _read_exactly(raw, length, deadline):
    buf = b""
    while len(buf) < length:
        _await_readable(raw, deadline)
        chunk = raw.read(length - len(buf))
        if not chunk:
            raise EOFError()
        buf += chunk
    return buf
def _await_readable(stream, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _LsTimeout()
    ready, _, _ = select.select([stream], [], [], remaining)
    if not ready:
        raise _LsTimeout()
def _flatten(locations):
    if isinstance(locations, dict):
        locations = [locations]
    return [_flat_one(loc) for loc in (locations or []) if loc]
def _flat_one(loc):
    if "uri" in loc:
        return _from_location(loc)
    return _from_location_link(loc)
def _from_location(loc):
    start = loc.get("range", {}).get("start", {})
    return {"file": _strip_file(loc["uri"]),
            "line": start.get("line", 0),
            "character": start.get("character", 0)}
def _from_location_link(loc):
    start = loc.get("targetSelectionRange", {}).get("start", {})
    return {"file": _strip_file(loc.get("targetUri", "")),
            "line": start.get("line", 0),
            "character": start.get("character", 0)}
def _strip_file(uri):
    return uri.removeprefix("file://")
def _cleanup(proc):
    _close_stdin(proc)
    _terminate_and_wait(proc)
def _close_stdin(proc):
    try:
        proc.stdin.close()
    except Exception:
        pass
def _terminate_and_wait(proc):
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        _kill_and_wait(proc)
def _kill_and_wait(proc):
    try:
        proc.kill()
        proc.wait(timeout=1)
    except Exception:
        pass
def _ok_envelope(obj):
    return {"content": [{"type": "text", "text": json.dumps(obj)}],
            "isError": False}
def _err(code, detail):
    return {"content": [{"type": "text",
                         "text": json.dumps({"error": code, "detail": detail})}],
            "isError": True}
