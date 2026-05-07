# Complex Use Case: Massive Project Refactoring 🛠️

Refactoring a legacy codebase is like performing surgery while the patient is running. When using AI agents, the lack of "muscle memory" of the codebase can lead to massive regressions.

## The Challenge
*   **Legacy Debt**: Thousands of lines of unoptimized code.
*   **Hidden Dependencies**: Changing a function in `Networking` breaks a feature in `Settings`.
*   **Information Overload**: Passing the entire legacy codebase to the agent burns tokens and confuses the model.

## The `mr-memory` Solution

### 1. Incremental Context Rotation
Instead of refactoring everything at once, use **Small Session Cycles**:
1.  **Work on Module A**.
2.  `mr-memory compact` (Extracts what was changed).
3.  `mr-memory rotate` (Clears the "surgery room").
4.  **Move to Module B**.

This ensures the agent always has a "Fresh Brain" for each module, without the baggage of the previous one.

### 2. Building the "Dependency Gotchas" List
As the agent discovers hidden dependencies, mark them immediately:
```markdown
⚠️ Blocked: UserProfile modification depends on the internal 'AuthCache' singleton. Cannot move to SPM package without refactoring AuthCache first.
```
This stays in `GOTCHAS.md` (Warm Tier). When you eventually start refactoring `AuthCache`, the agent will proactively warn you about the `UserProfile` dependency.

### 3. The "Why did this break?" Retrieval
If a regression occurs in `Settings` while refactoring `Networking`:
**Action**: `/retrieve Networking Settings connection`
**Agent**: Finds that 10 days ago, a specific protocol was modified to "improve performance" [[2026-04-20]].
**Solution**: The Knowledge Graph points exactly to the line and the session that caused the regression.

## Value for the Architect
- **Precision over Volume**: You only load the *diff* and the *summarized decisions*, not the 5000 lines of legacy code.
- **Risk Mitigation**: `GOTCHAS.md` becomes a "Technical Minefield Map".
- **Semantic Re-ranking**: The agent filters out lexical matches and finds the *semantic* root cause of regressions using the historical index.
