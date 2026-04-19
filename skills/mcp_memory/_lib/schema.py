"""JSON Schema input definitions for the four MCP memory tools."""
from mcp_memory._lib import schema_parts as parts


def all_tools():
    return [_search(), _timeline(), _observations(), _findings()]


def _search():
    return {"name": "search_memory",
            "description": "FTS5 search over observations and scratchpad.",
            "inputSchema": {"type": "object", "required": ["query"],
                            "properties": parts.search_props()}}


def _timeline():
    return {"name": "get_timeline",
            "description": "Chronological rows ordered by timestamp ASC.",
            "inputSchema": {"type": "object",
                            "properties": parts.timeline_props()}}


def _observations():
    return _hydrate("get_observations",
                    "Hydrate full observation rows by id or hash.")


def _findings():
    return _hydrate("get_findings",
                    "Hydrate scratchpad rows by id or hash.")


def _hydrate(name, description):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object",
                            "properties": parts.hydrate_props(),
                            "oneOf": [{"required": ["ids"]},
                                      {"required": ["content_hashes"]}]}}
