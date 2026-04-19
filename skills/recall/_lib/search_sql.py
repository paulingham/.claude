"""FTS5 search SQL templates with {priv} and {where} placeholders."""

OBS = (
    "SELECT o.id AS id, substr(o.content_hash, 1, 16) AS content_hash, "
    "o.timestamp AS timestamp, o.tool AS tool, o.file AS file, "
    "snippet(observations_fts, 0, '[', ']', '…', 8) AS snippet "
    "FROM observations_fts "
    "JOIN observations o ON o.id = observations_fts.rowid "
    "WHERE observations_fts MATCH ?{priv} {where}"
    "ORDER BY bm25(observations_fts) LIMIT ?")

SP = (
    "SELECT s.id AS id, substr(s.content_hash, 1, 16) AS content_hash, "
    "s.timestamp AS timestamp, s.category AS category, "
    "snippet(scratchpad_fts, 0, '[', ']', '…', 8) AS snippet, "
    "'scratchpad' AS source "
    "FROM scratchpad_fts "
    "JOIN scratchpad_findings s ON s.id = scratchpad_fts.rowid "
    "WHERE scratchpad_fts MATCH ?{priv} {where}"
    "ORDER BY bm25(scratchpad_fts) LIMIT ?")
