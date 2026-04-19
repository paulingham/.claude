"""Reusable JSON Schema fragments for MCP memory tool input schemas."""
SOURCE_ENUM = ["both", "observations", "scratchpad"]
LIMIT = {"type": "integer", "minimum": 1, "maximum": 500}
DB_PATH = {"type": "string",
           "description": "Optional DB path; defaults to ~/.claude/db/memory.sqlite"}
HASH_LIST = {"type": "array", "items": {"type": "string"}, "maxItems": 100}
ID_LIST = {"type": "array", "items": {"type": "integer"}, "maxItems": 100}


def search_props():
    return {"query": {"type": "string"},
            "source": {"type": "string", "enum": SOURCE_ENUM, "default": "both"},
            "limit": {**LIMIT, "default": 20}, "db_path": DB_PATH}


def timeline_props():
    return {"source": {"type": "string", "enum": SOURCE_ENUM,
                       "default": "observations"},
            "limit": {**LIMIT, "default": 50}, "db_path": DB_PATH}


def hydrate_props():
    return {"ids": ID_LIST, "content_hashes": HASH_LIST, "db_path": DB_PATH}
