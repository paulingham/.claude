---
name: "skill-builder"
description: "Create new Claude Code Skills with proper YAML frontmatter, progressive disclosure structure, and complete directory organization. Use when you need to build custom skills for specific workflows, generate skill templates, or understand the Claude Skills specification."
---

# Skill Builder

## What This Skill Does

Creates production-ready Claude Code Skills with proper YAML frontmatter, progressive disclosure architecture, and complete file/folder structure. This skill guides you through building skills that Claude can autonomously discover and use across all surfaces (Claude.ai, Claude Code, SDK, API).

## Prerequisites

- Claude Code 2.0+ or Claude.ai with Skills support
- Basic understanding of Markdown and YAML
- Text editor or IDE

## Quick Start

### Creating Your First Skill

```bash
# 1. Create skill directory (MUST be at top level, NOT in subdirectories!)
mkdir -p ~/.claude/skills/my-first-skill

# 2. Create SKILL.md with proper format
cat > ~/.claude/skills/my-first-skill/SKILL.md << 'EOF'
---
name: "My First Skill"
description: "Brief description of what this skill does and when Claude should use it. Maximum 1024 characters."
---

# My First Skill

## What This Skill Does
[Your instructions here]

## Quick Start
[Basic usage]
EOF

# 3. Verify skill is detected
# Restart Claude Code or refresh Claude.ai
```

---

## Complete Specification

### YAML Frontmatter (REQUIRED)

Every SKILL.md **must** start with YAML frontmatter containing exactly two required fields:

```yaml
---
name: "Skill Name"                    # REQUIRED: Max 64 chars
description: "What this skill does    # REQUIRED: Max 1024 chars
and when Claude should use it."       # Include BOTH what & when
---
```

#### Field Requirements

**`name`** (REQUIRED):
- **Type**: String
- **Max Length**: 64 characters
- **Format**: Human-friendly display name
- **Best Practice**: Use Title Case, be concise and descriptive

**`description`** (REQUIRED):
- **Type**: String
- **Max Length**: 1024 characters
- **Content**: MUST include:
  1. **What** the skill does (functionality)
  2. **When** Claude should invoke it (trigger conditions)
- **Best Practice**: Front-load key trigger words, be specific about use cases

#### YAML Formatting Rules

```yaml
---
# Correct: Simple string
name: "API Builder"
description: "Creates REST APIs with Express and TypeScript."

# Correct: Multi-line description
name: "Full-Stack Generator"
description: "Generates full-stack applications with React frontend and Node.js backend. Use when starting new projects or scaffolding applications."

# Correct: Special characters quoted
name: "JSON:API Builder"
description: "Creates JSON:API compliant endpoints: pagination, filtering, relationships."

# Wrong: Missing quotes with special chars
name: API:Builder  # YAML parse error!
---
```

**Critical**: Only `name` and `description` are used by Claude. Additional fields are ignored.

---

### Directory Structure

#### Minimal Skill (Required)
```
~/.claude/skills/                    # Personal skills location
  my-skill/                          # Skill directory (MUST be at top level!)
    SKILL.md                         # REQUIRED: Main skill file
```

**IMPORTANT**: Skills MUST be directly under `~/.claude/skills/[skill-name]/`.
Claude Code does NOT support nested subdirectories or namespaces!

#### Full-Featured Skill (Recommended)
```
~/.claude/skills/
  my-skill/                          # Top-level skill directory
    SKILL.md                         # REQUIRED: Main skill file
    README.md                        # Optional: Human-readable docs
    scripts/                         # Optional: Executable scripts
      setup.sh
      validate.js
      deploy.py
    resources/                       # Optional: Supporting files
      templates/
      examples/
      schemas/
    docs/                            # Optional: Additional documentation
      ADVANCED.md
      TROUBLESHOOTING.md
      API_REFERENCE.md
```

#### Skills Locations

**Personal Skills** (available across all projects):
```
~/.claude/skills/
  [your-skills]/
```
- **Scope**: Available in all projects for this user
- **Version Control**: NOT committed to git (outside repo)

**Project Skills** (team-shared, version controlled):
```
<project-root>/.claude/skills/
  [team-skills]/
```
- **Scope**: Available only in this project
- **Version Control**: SHOULD be committed to git

---

### Progressive Disclosure Architecture

Claude Code uses a **3-level progressive disclosure system** to scale to 100+ skills without context penalty:

#### Level 1: Metadata (Name + Description)
**Loaded**: At Claude Code startup, always
**Size**: ~200 chars per skill
**Purpose**: Enable autonomous skill matching

#### Level 2: SKILL.md Body
**Loaded**: When skill is triggered/matched
**Size**: ~1-10KB typically
**Purpose**: Main instructions and procedures

#### Level 3+: Referenced Files
**Loaded**: On-demand as Claude navigates
**Size**: Variable (KB to MB)
**Purpose**: Deep reference, examples, schemas

**Benefit**: Install 100+ skills with ~6KB context. Only active skill content (1-10KB) enters context.

---

### SKILL.md Content Structure

#### Recommended 4-Level Structure

```markdown
---
name: "Your Skill Name"
description: "What it does and when to use it"
---

# Your Skill Name

## Level 1: Overview (Always Read First)
Brief 2-3 sentence description of the skill.

## Prerequisites
- Requirement 1
- Requirement 2

## What This Skill Does
1. Primary function
2. Secondary function
3. Key benefit

---

## Level 2: Quick Start (For Fast Onboarding)

### Basic Usage
[Simplest use case]

### Common Scenarios
1. **Scenario 1**: How to...
2. **Scenario 2**: How to...

---

## Level 3: Detailed Instructions (For Deep Work)

### Step-by-Step Guide
[Detailed steps with expected output]

### Advanced Options
[Configuration and integration]

---

## Level 4: Reference (Rarely Needed)

### Troubleshooting
[Common issues and solutions]

### Complete API Reference
See [API_REFERENCE.md](docs/API_REFERENCE.md)
```

---

### Content Best Practices

#### Writing Effective Descriptions

**Front-Load Keywords**:
```yaml
# Good: Keywords first
description: "Generate TypeScript interfaces from JSON schema. Use when converting schemas, creating types, or building API clients."

# Bad: Keywords buried
description: "This skill helps developers who need to work with JSON schemas by providing a way to generate TypeScript interfaces."
```

**Include Trigger Conditions**:
```yaml
# Good: Clear "when" clause
description: "Debug React performance issues using Chrome DevTools. Use when components re-render unnecessarily, investigating slow updates, or optimizing bundle size."

# Bad: No trigger conditions
description: "Helps with React performance debugging."
```

---

### Validation Checklist

Before publishing a skill, verify:

**YAML Frontmatter**:
- [ ] Starts with `---`
- [ ] Contains `name` field (max 64 chars)
- [ ] Contains `description` field (max 1024 chars)
- [ ] Description includes "what" and "when"
- [ ] Ends with `---`
- [ ] No YAML syntax errors

**File Structure**:
- [ ] SKILL.md exists in skill directory
- [ ] Directory is DIRECTLY in `~/.claude/skills/[skill-name]/` or `.claude/skills/[skill-name]/`
- [ ] Uses clear, descriptive directory name
- [ ] **NO nested subdirectories** (Claude Code requires top-level structure)

**Content Quality**:
- [ ] Level 1 (Overview) is brief and clear
- [ ] Level 2 (Quick Start) shows common use case
- [ ] Level 3 (Details) provides step-by-step guide
- [ ] Level 4 (Reference) links to advanced content
- [ ] Examples are concrete and runnable

**Progressive Disclosure**:
- [ ] Core instructions in SKILL.md (~2-5KB)
- [ ] Advanced content in separate docs/
- [ ] Large resources in resources/ directory
- [ ] Clear navigation between levels

---

## Skill Builder Templates

### Template 1: Basic Skill (Minimal)

```markdown
---
name: "My Basic Skill"
description: "One sentence what. One sentence when to use."
---

# My Basic Skill

## What This Skill Does
[2-3 sentences describing functionality]

## Quick Start
[Single command to get started]

## Step-by-Step Guide

### Step 1: Setup
[Instructions]

### Step 2: Usage
[Instructions]

### Step 3: Verify
[Instructions]

## Troubleshooting
- **Issue**: Problem description
  - **Solution**: Fix description
```

### Template 2: Intermediate Skill (With Scripts)

```markdown
---
name: "My Intermediate Skill"
description: "Detailed what with key features. When to use with specific triggers."
---

# My Intermediate Skill

## Prerequisites
- Requirement 1
- Requirement 2

## What This Skill Does
1. Primary function
2. Secondary function
3. Integration capability

## Quick Start
[Basic usage commands]

## Configuration
[Config file details]

## Step-by-Step Guide

### Basic Usage
[Steps for 80% use case]

### Advanced Usage
[Steps for complex scenarios]

## Available Scripts
- `scripts/setup.sh` - Initial setup
- `scripts/generate.sh` - Code generation
- `scripts/validate.sh` - Validation

## Resources
- Templates: `resources/templates/`
- Examples: `resources/examples/`

## Troubleshooting
[Common issues and solutions]
```

---

## Learn More

### Official Resources
- [Anthropic Agent Skills Documentation](https://docs.claude.com/en/docs/agents-and-tools/agent-skills)
- [GitHub Skills Repository](https://github.com/anthropics/skills)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)

### Advanced Topics
- Multi-file skills with complex navigation
- Skills that spawn other skills
- Integration with MCP tools
- Dynamic skill generation
