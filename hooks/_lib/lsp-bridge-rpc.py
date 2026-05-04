"""JSON-RPC dispatch for the LSP-as-MCP bridge."""


def _tool(lang):
    return {"name": f"mcp_lsp_diagnostics_{lang}",
            "description": f"Query LSP diagnostics ({lang}). Advisory stub.",
            "inputSchema": {"type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"]}}


def _init(lang):
    return {"protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": f"lsp-{lang}", "version": "0.1.0"}}


def _stub():
    text = "advisory: LSP shell-out not yet implemented"
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _ok(req_id, payload):
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}


def route(msg, lang):
    method = msg.get("method")
    if method == "initialize":
        return _ok(msg["id"], _init(lang))
    if method == "tools/list":
        return _ok(msg["id"], {"tools": [_tool(lang)]})
    if method == "tools/call":
        return _ok(msg["id"], _stub())
    return None
