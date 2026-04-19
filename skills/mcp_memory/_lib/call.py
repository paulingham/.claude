"""Routes `tools/call` to handler functions with error mapping + MCP content."""
import json

from mcp_memory._lib import handlers, rpc

_TOOL_NAMES = ("search_memory", "get_timeline",
               "get_observations", "get_findings")


def handle(message):
    params = message.get("params") or {}
    name = params.get("name")
    if name not in _TOOL_NAMES:
        return _unknown_tool(message.get("id"), name)
    return _invoke(name, params.get("arguments") or {}, message.get("id"))


def _unknown_tool(req_id, name):
    return rpc.error(req_id, rpc.METHOD_NOT_FOUND, f"unknown tool: {name}")


def _invoke(name, arguments, req_id):
    try:
        return rpc.result(req_id, _content(_call(name, arguments)))
    except Exception as exc:
        return _map_error(exc, req_id)


def _call(name, arguments):
    return getattr(handlers, name)(arguments)


def _map_error(exc, req_id):
    if isinstance(exc, (ValueError, KeyError)):
        return rpc.error(req_id, rpc.INVALID_PARAMS, _reason(exc))
    return rpc.error(req_id, rpc.INTERNAL_ERROR,
                     f"internal error: {type(exc).__name__}")


def _reason(exc):
    if isinstance(exc, KeyError):
        return f"missing required argument: {exc.args[0]}"
    return str(exc)


def _content(env):
    text = json.dumps(env, ensure_ascii=False)
    return {"content": [{"type": "text", "text": text}],
            "isError": False, "structuredContent": env}
