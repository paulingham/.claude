"""JSON-RPC 2.0 request/response/error builders and codes."""
import json

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ParseError(ValueError):
    """Raised when a line cannot be parsed as JSON-RPC input."""


def parse(line):
    try:
        return json.loads(line)
    except (ValueError, TypeError) as exc:
        raise ParseError(str(exc)) from exc


def result(req_id, payload):
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}


def error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}
