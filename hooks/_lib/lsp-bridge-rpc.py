"""JSON-RPC dispatch for the LSP-as-MCP bridge."""
import importlib.util
import json
import subprocess
from pathlib import Path
def _load_lsp():
    path = Path(__file__).parent / "lsp-bridge-lsp.py"
    spec = importlib.util.spec_from_file_location("_lsp_lsp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def _stdio_factory(binary):
    return subprocess.Popen(
        [binary, "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
def _diag_tool(lang):
    return {"name": f"mcp_lsp_diagnostics_{lang}",
            "description": f"Query LSP diagnostics ({lang}). Advisory stub.",
            "inputSchema": {"type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"]}}
def _def_schema():
    props = {"path": {"type": "string"},
             "line": {"type": "integer"},
             "character": {"type": "integer"}}
    return {"type": "object", "properties": props,
            "required": ["path", "line", "character"]}
def _def_tool(lang):
    return {"name": f"mcp_lsp_definition_{lang}",
            "description": f"Go-to-definition via LSP ({lang}).",
            "inputSchema": _def_schema()}
def _tools(lang):
    return [_diag_tool(lang), _def_tool(lang)]
def _init(lang):
    return {"protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": f"lsp-{lang}", "version": "0.1.0"}}
def _stub():
    text = "advisory: LSP shell-out not yet implemented"
    return {"content": [{"type": "text", "text": text}], "isError": False}
def _ok(req_id, payload):
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}
def _err_envelope(code, detail):
    body = json.dumps({"error": code, "detail": detail})
    return {"content": [{"type": "text", "text": body}], "isError": True}
def _unsupported(name):
    return _err_envelope("unsupported", f"Unknown tool: {name}")
def _validate_def_args(args):
    for key in ("path", "line", "character"):
        if key not in args:
            return _err_envelope("bad-args", f"Missing required arg: {key}")
    return None
def _definition(args, lang):
    err = _validate_def_args(args)
    if err:
        return err
    lsp = _load_lsp()
    pos = lsp.Position(path=args["path"], line=args["line"],
                       character=args["character"])
    return lsp.run_definition(_stdio_factory, lang, pos)
def _call(msg, lang):
    name = msg.get("params", {}).get("name", "")
    args = msg.get("params", {}).get("arguments", {})
    if name == f"mcp_lsp_diagnostics_{lang}":
        return _stub()
    if name == f"mcp_lsp_definition_{lang}":
        return _definition(args, lang)
    return _unsupported(name)
def route(msg, lang):
    method = msg.get("method")
    if method == "initialize":
        return _ok(msg["id"], _init(lang))
    if method == "tools/list":
        return _ok(msg["id"], {"tools": _tools(lang)})
    if method == "tools/call":
        return _ok(msg["id"], _call(msg, lang))
    return None
