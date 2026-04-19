"""JSON-RPC method dispatch: initialize, tools/list, tools/call."""
from mcp_memory._lib import rpc

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "memory", "version": "0.1.0"}


def dispatch(message):
    method = message.get("method")
    req_id = message.get("id")
    if method == "initialize":
        return rpc.result(req_id, _initialize_payload())
    return rpc.error(req_id, rpc.METHOD_NOT_FOUND, f"unknown method: {method}")


def _initialize_payload():
    return {"protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}
