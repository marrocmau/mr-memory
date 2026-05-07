# 🧠 mr-memory

**Tiered Memory & Knowledge Graph Plugin for Agentic Frameworks.**

`mr-memory` is a specialized plugin designed to solve "Context Bloat" and optimize token consumption in long-lived AI development sessions. It transforms a scattered "Memory Bank" into a structured, navigable **Knowledge Graph**.

## 🏛️ Tiered Memory Architecture

- **🔥 Hot Memory**: Immediate session context (`MEMORY.md`). High visibility, high token cost.
- **⛅ Warm Memory**: The distilled "Source of Truth" (`PROGRESS.md`, `DECISIONS.md`). Persistent and shared across sessions.
- **❄️ Cold Memory**: Indexed historical archives. Stored off-context to save tokens, but easily retrievable.

## 🕸️ Knowledge Graph & Obsidian Support

`mr-memory` isn't just about storage; it's about **connectivity**. 
- **Obsidian Graph Ready**: Automatically injects YAML Frontmatter and Wiki-links (`[[session_name]]`) into every file.
- **Visual History**: In Obsidian, nodes like `DECISIONS.md` are visually linked to the sessions where those decisions were made.
- **Semantic Backlinking**: Every distilled fact points back to its origin, ensuring perfect traceability.

## 🚀 Key Features

- **Bilingual Autonomous Compaction**: Automatically extracts tasks (`- [x]`, `DONE:`, `COMPLETATO:`), decisions (`ADR:`, `Decisione:`) and technical "gotchas" (`Blocked:`, `Bloccato:`) from session logs in both English and Italian.
- **Token Auditing**: Real-time estimation and classification of context weight (Lean, Growing, Bloated).
- **Rotation Safety**: Moves old sessions to Cold Memory with mandatory atomic resets and optional `--backup` flag to prevent data loss.
- **Semantic Retrieval**: Two-phase search engine. Combines BM25 lexical search (`retrieve`) with an LLM Re-ranking protocol for perfect pertinence.
- **Obsidian Graph Ready**: Automatically injects YAML Frontmatter and Wiki-links (`[[session_name]]`) into every file, including initial seed files.

## 🛠️ Quick Start

```bash
# Create memory structure with Obsidian-ready frontmatter
mr-memory init --runtime gemini --write-config

# Flexible CLI: flags can go anywhere
mr-memory audit --json --verbose

# Distill bilingue session logs into Warm Memory, with backups
mr-memory compact --backup

# Archive old sessions safely with a full backup
mr-memory rotate --backup --keep-last 2

# Search for past knowledge with Semantic Re-ranking protocol
mr-memory retrieve "SwiftData migration" --json
```

## 📦 Installation

This plugin is designed for agentic development frameworks and long-lived AI sessions.

```bash
git clone https://github.com/mr-marino/mr-memory
cd mr-memory
pip install -e .
```

## Runtime Support

`mr-memory` detects Claude Code, Codex and Gemini CLI memory folders:

- Claude Code: `.claude/memory`
- Codex: `.codex/memory`
- Gemini CLI: `.gemini/memory`

Use `--root`, `--runtime`, `--memory-dir`, `MRMEMORY_DIR` or `mrmemory.json` for explicit control.

See `USER_GUIDE.md` for the complete workflow, safety flags and troubleshooting.

Integrated projects often include `/compact` and `/retrieve` slash commands that implement the same safe compaction and semantic re-ranking workflows.

Archive indexes use schema `2.0` and include LLM-oriented metadata such as estimated tokens, frontmatter, backlinks, query text and compact `llm_context` summaries. Retrieval combines field-weighted scoring with lightweight BM25 and exposes `score`, `lexical_score`, `bm25_score` and `matched_terms`.

Use `mrmemory.json` to customize runtime, tier rules, token thresholds and compaction patterns. See `USER_GUIDE.md` for an example config.

## Tests

```bash
cd mr-memory
PYTHONPATH=src python3 -m unittest discover -s tests
```

The repository also includes a GitHub Actions gate at `.github/workflows/mr-memory-tests.yml` that runs the same suite on Python 3.9 through 3.12.

---
*Created by Mr. Marino.*
