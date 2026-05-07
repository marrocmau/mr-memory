# 🧠 User Guide: mr-memory

`mr-memory` is a specialized tiered memory management system for agentic coding workflows. It solves "Context Bloat" by transforming scattered session logs into a structured, navigable **Knowledge Graph**, ensuring your AI agents remain fast, precise, and cost-effective.

---

## 🏛️ How Memory Management Works

LLMs have a finite context window. Loading every session log into every prompt leads to high costs, slower responses, and "hallucinations" due to information noise. `mr-memory` solves this by splitting project knowledge into three distinct tiers.

### The Three Tiers

| Tier | Visibility | Purpose | Default Files |
| :--- | :--- | :--- | :--- |
| 🔥 **Hot** | **High** | Immediate working context for the current session. High token cost. | `MEMORY.md`, `private/scratch.md` |
| ⛅ **Warm** | **Medium** | The distilled "Source of Truth". Persistent across sessions. High value. | `PROGRESS.md`, `DECISIONS.md`, `GOTCHAS.md`, `BACKLOG.md`, etc. |
| ❄️ **Cold** | **Indexed** | Historical archives. Stored off-context to save tokens but searchable. | `archive/`, `knowledge-map.json` |

### 💰 How to Save Tokens (The Strategy)

1.  **Summarize Often**: Instead of letting `MEMORY.md` or logs grow indefinitely, use `compact` to move completed tasks and decisions to the **Warm Tier**.
2.  **Offload History**: Once a milestone is reached or a session ends, use `rotate` to move logs to the **Cold Tier**. This clears the "Hot" context completely.
3.  **Targeted Retrieval**: Use `retrieve` to find specific past facts. Instead of loading 50 historical files, the agent only reads the 3 most relevant ones.
4.  **Audit Regularly**: Use `audit` to see exactly where your "token weight" is. If the Warm tier is too big (>20k tokens), it's time to archive.

---

## 🚀 Installation & Setup

### Official Package
```bash
pip install mrmemory
```

### From GitHub (Latest Version)
```bash
pip install git+https://github.com/marrocmau/mr-memory.git
```

### For Integrated Projects
If `mr-memory` is bundled in your project:
```bash
# Run locally using PYTHONPATH
PYTHONPATH=./mr-memory/src python3 -m mrmemory.cli audit
```

---

## 🧱 Bootstrapping a Project

Use the `init` command to create the memory skeleton in a new project.

```bash
# Initialize for a specific runtime (claude, codex, or gemini)
mr-memory init --runtime gemini

# Create mrmemory.json configuration file at the same time
mr-memory init --write-config

# Force regeneration of seed files (warning: overwrites defaults)
mr-memory init --force
```

**What happens?** `init` creates a `.gemini/memory/` (or similar) folder with YAML frontmatter-enabled files, ready for tools like **Obsidian**.

---

## 🛠️ Command Reference

### 1. `audit` (Measure Context Weight)
Analyzes the memory directory and classifies files into tiers, estimating token usage.

*   **Action**: Scans all `.md` files, calculates tokens (1 token ≈ 4 chars), and checks against thresholds.
*   **Examples**:
    ```bash
    mr-memory audit            # Human-readable table
    mr-memory audit --json     # Machine-readable (for hooks)
    mr-memory audit --verbose  # Shows list of files per tier
    ```

### 2. `compact` (Distill Knowledge)
Extracts facts from session logs and writes them into **Warm Tier** files (`PROGRESS.md`, `DECISIONS.md`, `GOTCHAS.md`).

*   **Action**: Scans `memory/sessions/*.md`, looks for patterns (IT/EN), deduplicates, and updates Warm files with backlinks.
*   **Bilingual Patterns**: Identifies `Decisione:`, `ADR:`, `DONE:`, `COMPLETATO:`, `✅`, `Gotcha:`, `Blocked:`, etc.
*   **Examples**:
    ```bash
    mr-memory compact --dry-run   # Preview what would be extracted
    mr-memory compact --backup    # Run and create a safety snapshot before writing
    ```

### 3. `rotate` (Archive and Reset)
Moves "Hot" and "Warm" data into the **Cold Tier** (archives) and resets the active context.

*   **Action**: Creates a dated folder in `archive/`, moves selected session logs, archives `MEMORY.md`, resets it, and rebuilds the search index.
*   **Safety**: Uses atomic writes for resets and supports full backups.
*   **Examples**:
    ```bash
    mr-memory rotate --backup                 # Move everything and reset
    mr-memory rotate --before 2026-05-01      # Only archive older files
    mr-memory rotate --keep-last 3            # Archive all but the 3 newest sessions
    mr-memory rotate --include "*FeatureA*"    # Selective archiving
    ```

### 4. `retrieve` (Intelligent Search)
Searches the indexed Cold Memory using a hybrid BM25 / LLM protocol.

*   **Action**: Phase A uses fast lexical matching (BM25). Phase B (handled by the AI agent) performs a semantic re-ranking of the results.
*   **Examples**:
    ```bash
    mr-memory retrieve "SwiftData migration"
    mr-memory retrieve "error handling" --json
    ```

---

## 🔄 Recommended Workflow

Follow this cycle to maintain a perfect knowledge graph:

1.  **Session Start**: Run `mr-memory audit`. Check if the context is "Lean".
2.  **During Work**: Write your activity in `memory/sessions/session_name.md` using markers:
    - `- [x] Task finished`
    - `Decisione: We are using a modular architecture`
    - `⚠️ Gotcha: API requires HTTPS`
3.  **Pause/Sync**: Run `mr-memory compact --backup`. Your `PROGRESS.md` and `DECISIONS.md` are now up to date.
4.  **Session End**: Run `mr-memory rotate --backup`. The logs are archived, `MEMORY.md` is reset, and you start the next task with 0 token bloat.

---

## ⚙️ Configuration (`mrmemory.json`)

Customize how `mr-memory` behaves by placing this file in your project root:

```json
{
  "runtime": "gemini",
  "memory_dir": ".gemini/memory",
  "token_thresholds": {
    "hot": { "growing": 3000, "bloated": 5000 },
    "warm": { "growing": 15000, "bloated": 25000 }
  },
  "compaction_patterns": {
    "progress": ["^- \\\\[x\\\\] (.*)", "(?i)^DONE: (.*)"],
    "decisions": ["(?i)^### Decisione?: (.*)", "(?i)^ADR: (.*)"],
    "gotchas": ["^⚠️ (.*)", "(?i)^Gotcha: (.*)"]
  }
}
```

---

## 🕸️ Obsidian Integration

`mr-memory` is designed to be visual.
1.  Open your memory folder (`.gemini/memory`) as an **Obsidian Vault**.
2.  `mr-memory` automatically adds **YAML Frontmatter** and **Wiki-links** (`[[session_name]]`).
3.  Use the **Graph View** to see how your architectural decisions link back to specific development days.

---

## 🧪 Development & Tests

```bash
cd mr-memory
PYTHONPATH=src python3 -m unittest discover -s tests
```
*Validated on Python 3.9, 3.10, 3.11, 3.12.*
