"""JSON-RPC method dispatch: initialize, tools/list, tools/call."""
from mcp_memory._lib import call, rpc, schema

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "memory", "version": "0.1.0"}
_RESULT_METHODS = {
    "initialize": lambda _msg: _initialize_payload(),
    "tools/list": lambda _msg: {"tools": schema.all_tools()},
}


def dispatch(message):
    method = message.get("method")
    if method == "tools/call":
        return call.handle(message)
    handler = _RESULT_METHODS.get(method)
    if handler is None:
        return rpc.error(message.get("id"), rpc.METHOD_NOT_FOUND,
                         f"unknown method: {method}")
    return rpc.result(message.get("id"), handler(message))


def _initialize_payload():
    return {"protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}
