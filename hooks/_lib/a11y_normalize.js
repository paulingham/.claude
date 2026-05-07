// Per-snapshot JSON normaliser — converts MCP YAML payloads and
// Playwright library JSON output to the canonical shape expected by
// the Python assertion engine. Both adapters MUST produce byte-equal
// JSON for fixtures representing the same DOM (AC15).
//
// Boundary contract: the canonical fields (and only those) appear on
// every node. MCP-only fields (e.g., `ref`) are present but may be set
// to null when the source path is library API.

'use strict';

const SNAPSHOT_SCHEMA_VERSION = 1;

const ARIA_KEYS = ['checked', 'expanded', 'hidden', 'level',
                   'pressed', 'selected'];

function normalize_library_json(node, viewport, route, capturedAt) {
  if (typeof node !== 'object' || node === null) {
    throw new TypeError('normalize_library_json: node must be an object');
  }
  return _envelope(_canon(node), viewport, route, capturedAt);
}

function normalize_mcp_yaml(yamlStr, viewport, route, capturedAt) {
  if (typeof yamlStr !== 'string') {
    throw new TypeError('normalize_mcp_yaml: input must be a string');
  }
  const parsed = _parseMinimalYaml(yamlStr);
  const root = Array.isArray(parsed) ? parsed[0] : parsed;
  return _envelope(_canon(root), viewport, route, capturedAt);
}

function _envelope(tree, viewport, route, capturedAt) {
  return {
    captured_at: capturedAt,
    route,
    schema_version: SNAPSHOT_SCHEMA_VERSION,
    tree,
    viewport,
  };
}

function _canon(node) {
  return {
    aria: _canonAria(node),
    children: (node.children || []).map(_canon),
    disabled: Boolean(node.disabled || false),
    interactive: Boolean(node.interactive || false),
    name: typeof node.name === 'string' ? node.name : '',
    ref: null,
    role: node.role || '',
    tag: node.tag || '',
  };
}

function _canonAria(node) {
  const aria = node.aria && typeof node.aria === 'object' ? node.aria : node;
  const out = {};
  for (const key of ARIA_KEYS) {
    out[key] = (key in aria) ? aria[key] : null;
  }
  return out;
}

// --- Minimal YAML parser sufficient for our fixture shape only. ---
// The fixture grammar: list items (`- key: value`), nested mappings,
// children: [], scalars (string/number/null/bool). Indent = 2 spaces.
// We deliberately do NOT depend on a YAML library — node 24 has none
// built-in and the fixture schema is fully under our control.

function _parseMinimalYaml(src) {
  const lines = src.split('\n').filter((l) => l.trim() !== '' &&
    !l.trim().startsWith('#'));
  const parser = new _YamlParser(lines);
  return parser.parse();
}

class _YamlParser {
  constructor(lines) { this.lines = lines; this.i = 0; }

  parse() { return this._block(0); }

  _block(indent) {
    const out = this._isListItem(indent) ? [] : {};
    while (this.i < this.lines.length) {
      const line = this.lines[this.i];
      const lead = _leadingSpaces(line);
      if (lead < indent) break;
      if (lead > indent) {
        // Should have been consumed by a child node.
        this.i += 1;
        continue;
      }
      this._consumeOne(out, line, indent);
    }
    return out;
  }

  _consumeOne(out, line, indent) {
    const trimmed = line.trim();
    if (trimmed.startsWith('- ')) {
      this._consumeListItem(out, trimmed, indent);
    } else {
      this._consumeMapEntry(out, trimmed, indent);
    }
  }

  _consumeListItem(out, trimmed, indent) {
    const inner = trimmed.slice(2);
    const item = {};
    this.i += 1;
    this._consumeInline(item, inner, indent + 2);
    while (this.i < this.lines.length &&
           _leadingSpaces(this.lines[this.i]) === indent + 2) {
      const nextLine = this.lines[this.i].trim();
      this._consumeMapEntry(item, nextLine, indent + 2);
    }
    out.push(item);
  }

  _consumeMapEntry(out, trimmed, indent) {
    const idx = trimmed.indexOf(':');
    const key = trimmed.slice(0, idx).trim();
    const rest = trimmed.slice(idx + 1).trim();
    this.i += 1;
    if (rest === '') {
      out[key] = this._block(indent + 2);
    } else if (rest === '[]') {
      out[key] = [];
    } else {
      out[key] = _scalar(rest);
    }
  }

  _consumeInline(item, inner, indent) {
    const idx = inner.indexOf(':');
    if (idx === -1) return;
    const key = inner.slice(0, idx).trim();
    const rest = inner.slice(idx + 1).trim();
    if (rest === '') {
      item[key] = this._block(indent);
    } else if (rest === '[]') {
      item[key] = [];
    } else {
      item[key] = _scalar(rest);
    }
  }

  _isListItem(indent) {
    if (this.i >= this.lines.length) return false;
    return this.lines[this.i].trim().startsWith('- ') &&
      _leadingSpaces(this.lines[this.i]) === indent;
  }
}

function _leadingSpaces(line) {
  let n = 0;
  while (n < line.length && line[n] === ' ') n += 1;
  return n;
}

function _scalar(s) {
  if (s === 'null') return null;
  if (s === 'true') return true;
  if (s === 'false') return false;
  if (/^-?\d+$/.test(s)) return parseInt(s, 10);
  if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
  return s;
}

module.exports = {
  normalize_library_json,
  normalize_mcp_yaml,
  SNAPSHOT_SCHEMA_VERSION,
};
