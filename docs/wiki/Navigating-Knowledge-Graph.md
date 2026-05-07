# Mastering the Obsidian Graph 🕸️

`mr-memory` is designed to transform a boring folder of markdown files into a living, breathing **Knowledge Graph**. By using **Obsidian**, you can navigate your project's history visually.

## 🧰 Setup
1.  Download and install [Obsidian](https://obsidian.md).
2.  Select **"Open folder as vault"**.
3.  Choose your memory directory (e.g., `.gemini/memory/`).

## 🖇️ The Magic of Backlinks
Every fact extracted by `mr-memory compact` includes a wiki-link like `[[2026-05-08_session]]`.
*   In Obsidian, open `DECISIONS.md`.
*   Hover over a decision to see a preview of the session where it was made.
*   Click the wiki-link to jump directly to the full session log for context.

## 🗺️ Using Graph View
Press `Ctrl + G` (or `Cmd + G`) to open the **Graph View**.

### What you will see:
*   **Central Hubs**: `DECISIONS.md`, `PROGRESS.md`, and `GOTCHAS.md` will appear as large nodes.
*   **Session Satellites**: Your session logs will be linked to these hubs.
*   **Clusters**: You will notice clusters of sessions around specific architectural milestones.

### Why this matters:
*   **Visual Impact**: Show your clients or CTO a visual representation of the project's evolution.
*   **Discoverability**: Find related sessions that you forgot existed by following the lines in the graph.
*   **Impact Analysis**: Before changing a decision, look at the graph to see how many sessions (and features) are built upon it.

## 🏷️ Tag-based Navigation
`mr-memory` automatically adds tags like `#warm`, `#hot`, and `#cold`.
*   Use the Obsidian search bar (`tag:#cold`) to find archived knowledge.
*   Combine tags with lexical search for instant answers.

---
*Transform your memory. Visualize your code. Control your context.*
