"""JSON-RPC method dispatch: initialize, tools/list, tools/call."""
from mcp_memory._lib import rpc, schema

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "memory", "version": "0.1.0"}
_METHODS = {
    "initialize": lambda _msg: _initialize_payload(),
    "tools/list": lambda _msg: {"tools": schema.all_tools()},
}


def dispatch(message):
    handler = _METHODS.get(message.get("method"))
    if handler is None:
        return rpc.error(message.get("id"), rpc.METHOD_NOT_FOUND,
                         f"unknown method: {message.get('method')}")
    return rpc.result(message.get("id"), handler(message))


def _initialize_payload():
    return {"protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}
