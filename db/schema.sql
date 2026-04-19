-- memory.sqlite schema (claude-mem port, Story 1)
-- Derived read index built from learning/*/observations.jsonl and scratchpad findings.
-- Run: sqlite3 memory.sqlite < schema.sql

-- Observations: one row per captured tool call.
-- content_hash = sha256(session_id|timestamp|tool|file) — the dedup key.
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content_hash TEXT NOT NULL UNIQUE,
  session_id TEXT NOT NULL,
  project_hash TEXT,
  timestamp TEXT NOT NULL,
  tool TEXT NOT NULL,
  file TEXT,
  phase TEXT,
  agent_role TEXT,
  outcome TEXT,
  tool_use_id TEXT,
  arg_hash TEXT,
  is_private INTEGER NOT NULL DEFAULT 0,
  searchable_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_observations_session ON observations(session_id);
CREATE INDEX IF NOT EXISTS idx_observations_timestamp ON observations(timestamp);
CREATE INDEX IF NOT EXISTS idx_observations_project ON observations(project_hash);

-- FTS5 external-content mirror of observations.searchable_text.
-- Triggers below keep it in sync on insert/update/delete.
CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
  searchable_text,
  content='observations',
  content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
  INSERT INTO observations_fts(rowid, searchable_text)
  VALUES (new.id, new.searchable_text);
END;
CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
  INSERT INTO observations_fts(observations_fts, rowid, searchable_text)
  VALUES ('delete', old.id, old.searchable_text);
END;
CREATE TRIGGER IF NOT EXISTS observations_au AFTER UPDATE ON observations BEGIN
  INSERT INTO observations_fts(observations_fts, rowid, searchable_text)
  VALUES ('delete', old.id, old.searchable_text);
  INSERT INTO observations_fts(rowid, searchable_text)
  VALUES (new.id, new.searchable_text);
END;

-- Scratchpad findings: agent-authored discoveries, warnings, patterns.
CREATE TABLE IF NOT EXISTS scratchpad_findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content_hash TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,
  category TEXT NOT NULL,
  agent_role TEXT,
  phase TEXT,
  timestamp TEXT NOT NULL,
  body TEXT NOT NULL,
  is_private INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS scratchpad_fts USING fts5(
  body,
  content='scratchpad_findings',
  content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS scratchpad_ai AFTER INSERT ON scratchpad_findings BEGIN
  INSERT INTO scratchpad_fts(rowid, body) VALUES (new.id, new.body);
END;
CREATE TRIGGER IF NOT EXISTS scratchpad_ad AFTER DELETE ON scratchpad_findings BEGIN
  INSERT INTO scratchpad_fts(scratchpad_fts, rowid, body)
  VALUES ('delete', old.id, old.body);
END;
CREATE TRIGGER IF NOT EXISTS scratchpad_au AFTER UPDATE ON scratchpad_findings BEGIN
  INSERT INTO scratchpad_fts(scratchpad_fts, rowid, body)
  VALUES ('delete', old.id, old.body);
  INSERT INTO scratchpad_fts(rowid, body) VALUES (new.id, new.body);
END;

-- Embeddings: authoritative. Reindex preserves rows whose content_hash
-- still maps to a surviving observation/scratchpad row (see reindex.py).
CREATE TABLE IF NOT EXISTS embeddings (
  content_hash TEXT PRIMARY KEY,
  model_id TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL
);

-- Privacy allowlist: declared here so Story 6 doesn't need a migration.
CREATE TABLE IF NOT EXISTS privacy_allowlist (
  pattern TEXT PRIMARY KEY,
  note TEXT,
  added_at TEXT NOT NULL
);

-- Schema version: drift detection for reindex rebuild logic.
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL,
  notes TEXT
);
INSERT OR IGNORE INTO schema_version (version, applied_at, notes)
  VALUES (1, datetime('now'), 'initial schema — claude-mem port Story 1');
