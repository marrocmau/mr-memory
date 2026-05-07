# Complex Use Case: Database Migration 🗄️

Migrating from **Core Data to SwiftData** (or any database engine) is a high-risk, multi-step process. In agentic development, the biggest danger is the agent "forgetting" why a specific mapping or migration policy was chosen three weeks ago.

## The Challenge
*   **Duration**: 4-12 weeks.
*   **Complexity**: 50+ schemas, complex relationships, custom migration policies.
*   **Context Bloat**: Every migration script generates massive logs.

## The `mr-memory` Solution

### 1. Tracking Decision Logic (ADRs)
During the migration, every time you choose a mapping strategy, record it as a decision in your session log:
```markdown
Decisione: Use custom 'SchemaV1ToV2' migration policy for UserEntity due to unique constraint changes.
```
`mr-memory compact` moves this to `DECISIONS.md`. When the agent works on `SchemaV3` a month later, it will "know" the precedent set for `V2`.

### 2. Safeguarding "Gotchas"
Migrations are full of technical debt and hidden traps.
```markdown
⚠️ Gotcha: SwiftData @Attribute(.unique) causes silent crashes if the existing Core Data store has duplicates. Must run cleanup script first.
```
This is automatically saved to `GOTCHAS.md`. Any agent tasked with "Finalizing Production Migration" will be alerted to this risk.

### 3. The Recovery Protocol (`retrieve`)
Two months into the project, a bug appears in the production data.
**User**: *"Why did we skip the cleanup for the 'Settings' entity in Phase 2?"*
**Agent**: Runs `/retrieve Settings cleanup` -> Finds the archived session from 45 days ago where the decision was made.
**Result**: *"According to archived decision [[2026-04-12]], we skipped it because Settings are transient and reset on every launch."*

## Value for the Architect
- **100% Traceability**: No more "I think we did this because...".
- **Zero Token Waste**: You don't need the 500 lines of Schema V1 in your current prompt to work on Schema V5.
- **Onboarding**: A new developer can read `DECISIONS.md` and understand the entire migration history in 10 minutes.
