import json
import tempfile
import unittest
from pathlib import Path

from mrmemory.archiver import Archiver
from mrmemory.compactor import Compactor
from mrmemory.core import MemoryManager, MemoryTier
from mrmemory.indexer import KnowledgeIndexer
from mrmemory.initializer import Initializer


class MemoryWorkflowTests(unittest.TestCase):
    def make_project(self, runtime="codex"):
        root = Path(tempfile.mkdtemp())
        manager = MemoryManager(str(root), runtime=runtime)
        Initializer(manager).init()
        return root, manager

    def test_audit_classifies_hot_warm_and_cold_files(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        archive_dir = memory_dir / "archive" / "2026-05-07_test"
        archive_dir.mkdir(parents=True)
        (archive_dir / "old.md").write_text("# Old\nArchived decision\n", encoding="utf-8")

        report = manager.audit()

        self.assertIn("MEMORY.md", report[MemoryTier.HOT]["files"])
        self.assertIn("PROGRESS.md", report[MemoryTier.WARM]["files"])
        self.assertIn("archive/2026-05-07_test/old.md", report[MemoryTier.COLD]["files"])
        self.assertGreater(report[MemoryTier.HOT]["tokens"], 0)

    def test_compact_extracts_progress_decisions_and_gotchas(self):
        root, manager = self.make_project("claude")
        memory_dir = Path(manager.memory_dir)
        session_path = memory_dir / "sessions" / "session1.md"
        session_path.write_text(
            "- [x] Implement compact tests\n"
            "### Decision: Use unittest temp directories\n"
            "⚠️ Reset mocks between runs\n",
            encoding="utf-8",
        )

        results = Compactor(manager).sync(backup=True)

        self.assertEqual(results["status"], "success")
        self.assertEqual(set(results["updated_files"]), {"PROGRESS.md", "DECISIONS.md", "GOTCHAS.md"})
        self.assertIn("Implement compact tests [[session1]]", (memory_dir / "PROGRESS.md").read_text(encoding="utf-8"))
        self.assertIn("Use unittest temp directories [[session1]]", (memory_dir / "DECISIONS.md").read_text(encoding="utf-8"))
        self.assertIn("Reset mocks between runs [[session1]]", (memory_dir / "GOTCHAS.md").read_text(encoding="utf-8"))
        self.assertTrue(results["backed_up_files"])

    def test_compact_dry_run_does_not_write_warm_files(self):
        root, manager = self.make_project("gemini")
        memory_dir = Path(manager.memory_dir)
        progress_before = (memory_dir / "PROGRESS.md").read_text(encoding="utf-8")
        (memory_dir / "sessions" / "session1.md").write_text("- [x] Should not write\n", encoding="utf-8")

        results = Compactor(manager).sync(dry_run=True, backup=True)

        self.assertEqual(results["updated_files"], ["PROGRESS.md"])
        self.assertEqual((memory_dir / "PROGRESS.md").read_text(encoding="utf-8"), progress_before)
        self.assertFalse(results["backed_up_files"])

    def test_rotate_archives_sessions_resets_memory_and_indexes_archive(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        (memory_dir / "MEMORY.md").write_text("# MEMORY\nActive context\n", encoding="utf-8")
        (memory_dir / "sessions" / "session1.md").write_text("# Session\n**SwiftData** decision\n", encoding="utf-8")

        results = Archiver(manager).rotate()

        archive_dir = Path(results["created_dir"])
        self.assertTrue((archive_dir / "sessions" / "session1.md").exists())
        self.assertTrue((archive_dir / "MEMORY_at_rotation.md").exists())
        self.assertTrue((archive_dir / "index.json").exists())
        self.assertTrue((memory_dir / "sessions").is_dir())
        self.assertIn("Context rotated", (memory_dir / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertTrue((memory_dir / "knowledge-map.json").exists())

    def test_rotate_controls_select_session_files_safely(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        sessions_dir = memory_dir / "sessions"
        (sessions_dir / "2026-05-01_keep.md").write_text("# Keep by date\n", encoding="utf-8")
        (sessions_dir / "2026-05-02_rotate.md").write_text("# Rotate\n", encoding="utf-8")
        (sessions_dir / "2026-05-03_exclude.md").write_text("# Exclude\n", encoding="utf-8")
        (sessions_dir / "2026-05-04_latest.md").write_text("# Keep latest\n", encoding="utf-8")

        dry_results = Archiver(manager).rotate(
            dry_run=True,
            before="2026-05-05",
            keep_last=1,
            include=["*2026-05-*"],
            exclude=["*exclude*"],
        )

        self.assertIn("sessions/2026-05-02_rotate.md", dry_results["moved_files"])
        self.assertIn("sessions/2026-05-03_exclude.md", dry_results["skipped_files"])
        self.assertIn("sessions/2026-05-04_latest.md", dry_results["skipped_files"])
        self.assertTrue((sessions_dir / "2026-05-02_rotate.md").exists())

        results = Archiver(manager).rotate(
            before="2026-05-05",
            keep_last=1,
            include=["*2026-05-*"],
            exclude=["*exclude*"],
        )
        archive_dir = Path(results["created_dir"]) / "sessions"

        self.assertTrue((archive_dir / "2026-05-01_keep.md").exists())
        self.assertTrue((archive_dir / "2026-05-02_rotate.md").exists())
        self.assertTrue((sessions_dir / "2026-05-03_exclude.md").exists())
        self.assertTrue((sessions_dir / "2026-05-04_latest.md").exists())

    def test_retrieve_finds_indexed_archive_entries(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        archive_dir = memory_dir / "archive" / "2026-05-07_test"
        archive_dir.mkdir(parents=True)
        (archive_dir / "decision.md").write_text(
            "# Persistence Decision\n"
            "**SwiftData** selected for local storage\n",
            encoding="utf-8",
        )
        KnowledgeIndexer(manager).index_archive(str(archive_dir))

        results = KnowledgeIndexer(manager).search("SwiftData")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["rel_path"], "archive/2026-05-07_test/decision.md")
        self.assertIn("SwiftData", results[0]["keywords"])
        self.assertGreater(results[0]["score"], 0)
        self.assertIn("swiftdata", results[0]["matched_terms"])

    def test_index_archive_writes_rich_llm_metadata(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        archive_dir = memory_dir / "archive" / "2026-05-07_test"
        archive_dir.mkdir(parents=True)
        (archive_dir / "decision.md").write_text(
            "---\n"
            "title: Persistence Decision\n"
            "tier: cold\n"
            "tags: [swiftdata, persistence]\n"
            "---\n"
            "# Persistence Decision\n"
            "**SwiftData** selected for local storage [[session1]]\n",
            encoding="utf-8",
        )

        index_path = KnowledgeIndexer(manager).index_archive(str(archive_dir))
        index_data = json.loads(Path(index_path).read_text(encoding="utf-8"))
        global_map = json.loads((memory_dir / "knowledge-map.json").read_text(encoding="utf-8"))
        entry = index_data["entries"][0]

        self.assertEqual(index_data["schema_version"], "2.0")
        self.assertEqual(index_data["entry_count"], 1)
        self.assertGreater(index_data["total_estimated_tokens"], 0)
        self.assertEqual(global_map["schema_version"], "2.0")
        self.assertEqual(global_map["archive_count"], 1)
        self.assertEqual(global_map["entry_count"], 1)
        self.assertEqual(entry["tier"], "cold")
        self.assertEqual(entry["document_type"], "decision")
        self.assertIn("session1", entry["backlinks"])
        self.assertEqual(entry["frontmatter"]["title"], "Persistence Decision")
        self.assertIn("swiftdata", entry["frontmatter"]["tags"])
        self.assertGreater(entry["estimated_tokens"], 0)
        self.assertGreater(entry["line_count"], 0)
        self.assertIn("query_text", entry)
        self.assertEqual(entry["llm_context"]["path"], entry["rel_path"])

    def test_retrieve_scores_multi_term_queries_and_orders_results(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        archive_dir = memory_dir / "archive" / "2026-05-07_test"
        archive_dir.mkdir(parents=True)
        (archive_dir / "a_precise.md").write_text(
            "# SwiftData Migration\n"
            "**SwiftData** **Migration** selected for local storage\n",
            encoding="utf-8",
        )
        (archive_dir / "b_partial.md").write_text(
            "# SwiftData Notes\n"
            "**SwiftData** selected\n",
            encoding="utf-8",
        )
        KnowledgeIndexer(manager).index_archive(str(archive_dir))

        results = KnowledgeIndexer(manager).search("SwiftData migration")

        self.assertEqual(results[0]["rel_path"], "archive/2026-05-07_test/a_precise.md")
        self.assertGreater(results[0]["score"], results[1]["score"])
        self.assertEqual(results[0]["matched_terms"], ["migration", "swiftdata"])
        self.assertIn("bm25_score", results[0])
        self.assertIn("lexical_score", results[0])

    def test_retrieve_uses_bm25_frequency_signal(self):
        root, manager = self.make_project("codex")
        memory_dir = Path(manager.memory_dir)
        archive_dir = memory_dir / "archive" / "2026-05-07_test"
        archive_dir.mkdir(parents=True)
        (archive_dir / "a_frequent.md").write_text(
            "# Storage Notes\n"
            "cache cache cache cache cache invalidation\n",
            encoding="utf-8",
        )
        (archive_dir / "b_sparse.md").write_text(
            "# Storage Notes\n"
            "cache invalidation\n",
            encoding="utf-8",
        )
        KnowledgeIndexer(manager).index_archive(str(archive_dir))

        results = KnowledgeIndexer(manager).search("cache")

        self.assertEqual(results[0]["rel_path"], "archive/2026-05-07_test/a_frequent.md")
        self.assertGreater(results[0]["bm25_score"], results[1]["bm25_score"])

    def test_mrmemory_json_can_select_memory_dir(self):
        root = Path(tempfile.mkdtemp())
        custom_memory = root / "custom-memory"
        (root / "mrmemory.json").write_text(json.dumps({"memory_dir": "custom-memory"}), encoding="utf-8")

        manager = MemoryManager(str(root))
        Initializer(manager).init()

        self.assertEqual(Path(manager.memory_dir), custom_memory)
        self.assertTrue((custom_memory / "MEMORY.md").exists())

    def test_mrmemory_json_customizes_tiers_thresholds_and_compaction_patterns(self):
        root = Path(tempfile.mkdtemp())
        config = {
            "runtime": "codex",
            "tier_rules": {
                "hot": ["MEMORY.md", "NOW.md"],
                "warm": ["STATE.md"],
                "cold": ["archive/**", "history/**"]
            },
            "token_thresholds": {
                "hot": {"growing": 1, "bloated": 3}
            },
            "compaction_patterns": {
                "progress": [r"DONE: (.*)"],
                "decisions": [r"Decisione: (.*)"],
                "gotchas": [r"Gotcha: (.*)"]
            }
        }
        (root / "mrmemory.json").write_text(json.dumps(config), encoding="utf-8")
        manager = MemoryManager(str(root))
        Initializer(manager).init()
        memory_dir = Path(manager.memory_dir)
        (memory_dir / "NOW.md").write_text("hot custom file with enough text\n", encoding="utf-8")
        (memory_dir / "STATE.md").write_text("warm custom file\n", encoding="utf-8")
        history_dir = memory_dir / "history"
        history_dir.mkdir()
        (history_dir / "old.md").write_text("cold custom file\n", encoding="utf-8")
        (memory_dir / "sessions" / "session1.md").write_text(
            "DONE: Custom progress\n"
            "Decisione: Custom decision\n"
            "Gotcha: Custom gotcha\n",
            encoding="utf-8",
        )

        report = manager.audit()
        results = Compactor(manager).sync()

        self.assertIn("NOW.md", report[MemoryTier.HOT]["files"])
        self.assertIn("STATE.md", report[MemoryTier.WARM]["files"])
        self.assertIn("history/old.md", report[MemoryTier.COLD]["files"])
        self.assertEqual(report[MemoryTier.HOT]["status"], "bloated")
        self.assertIn("Custom progress [[session1]]", (memory_dir / "PROGRESS.md").read_text(encoding="utf-8"))
        self.assertIn("Custom decision [[session1]]", (memory_dir / "DECISIONS.md").read_text(encoding="utf-8"))
        self.assertIn("Custom gotcha [[session1]]", (memory_dir / "GOTCHAS.md").read_text(encoding="utf-8"))
        self.assertEqual(results["extracted_counts"], {"progress": 1, "decisions": 1, "gotchas": 1})


if __name__ == "__main__":
    unittest.main()
