"""JSON-RPC 2.0 dispatch for the gh-cache MCP server."""
import json


_TOOL = {
    "name": "prefetch_pr",
    "description": "Prefetch PR view/diff/files into cache.",
    "inputSchema": {"type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"]}}


def make_dispatch(lib, fetch, prefetch):
    """Build a dispatcher closure over module dependencies."""
    def dispatch(message):
        return _route(message, lib, fetch, prefetch)
    return dispatch


def _route(message, lib, fetch, prefetch):
    method = message.get("method")
    if method == "initialize":
        return _ok(message.get("id"), _init_payload())
    if method == "tools/list":
        return _ok(message.get("id"), {"tools": [_TOOL]})
    if method == "tools/call":
        return _call(message, lib, fetch, prefetch)
    return None


def _init_payload():
    return {"protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "gh-cache", "version": "0.1.0"}}


def _call(message, lib, fetch, prefetch):
    args = (message.get("params") or {}).get("arguments") or {}
    return _ok(message.get("id"),
               _envelope(prefetch.prefetch(args, lib, fetch)))


def _envelope(data):
    text = json.dumps(data, ensure_ascii=False)
    return {"content": [{"type": "text", "text": text}],
            "isError": False, "structuredContent": data}


def _ok(req_id, payload):
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}
