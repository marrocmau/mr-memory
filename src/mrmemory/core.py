import os
import json
from typing import Optional

class MemoryTier:
    HOT = "hot"     # Context immediato (MEMORY.md, scratch.md)
    WARM = "warm"   # Stato del progetto (PROGRESS.md, DECISIONS.md, etc.)
    COLD = "cold"   # Archivio storico

class TokenEstimator:
    """Stima i token: 1 token ~= 4 caratteri per il testo inglese/codice"""
    @staticmethod
    def estimate(text: str) -> int:
        return len(text) // 4

    @staticmethod
    def estimate_file(path: str) -> int:
        if not os.path.exists(path):
            return 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return TokenEstimator.estimate(f.read())
        except Exception:
            return 0

class MemoryManager:
    RUNTIME_MEMORY_DIRS = {
        "claude": os.path.join(".claude", "memory"),
        "codex": os.path.join(".codex", "memory"),
        "gemini": os.path.join(".gemini", "memory"),
    }

    DEFAULT_TIER_RULES = {
        MemoryTier.HOT: ["MEMORY.md", "private/scratch.md"],
        MemoryTier.WARM: [
            "PROGRESS.md", "DECISIONS.md", "FEATURE_STATUS.md",
            "GOTCHAS.md", "BACKLOG.md", "RELEASES.md",
            "UX_NOTES.md", "BUILD_RECIPES.md"
        ],
        MemoryTier.COLD: ["archive/**", "backups/**"],
    }
    DEFAULT_TOKEN_THRESHOLDS = {
        MemoryTier.HOT: {"growing": 3000, "bloated": 5000},
        MemoryTier.WARM: {"growing": 12000, "bloated": 20000},
        MemoryTier.COLD: {"growing": 50000, "bloated": 100000},
    }
    DEFAULT_COMPACTION_PATTERNS = {
        "progress": [
            r"^- \[[xX]\] (.*)",
            r"(?i)^DONE: (.*)",
            r"(?i)^COMPLETATO: (.*)",
            r"^✅ (.*)"
        ],
        "decisions": [
            r"(?i)^### Decisione?: (.*)",
            r"(?i)^Decisione?: (.*)",
            r"(?i)^ADR: (.*)"
        ],
        "gotchas": [
            r"^⚠️ (.*)",
            r"(?i)^Gotcha: (.*)",
            r"(?i)^Blocked: (.*)",
            r"(?i)^Bloccato: (.*)"
        ],
    }

    def __init__(self, root_path: str = ".", memory_dir: Optional[str] = None, runtime: Optional[str] = None):
        self.root_path = os.path.abspath(root_path)
        self.runtime = runtime
        self.config = self._load_config()
        self.memory_dir = self._resolve_memory_dir(memory_dir, runtime)
        self.tier_rules = self._merge_config_section("tier_rules", self.DEFAULT_TIER_RULES)
        self.token_thresholds = self._merge_config_section("token_thresholds", self.DEFAULT_TOKEN_THRESHOLDS)
        self.compaction_patterns = self._merge_config_section("compaction_patterns", self.DEFAULT_COMPACTION_PATTERNS)

    def audit(self):
        """Analizza fisicamente la cartella memory rilevata e calcola i pesi"""
        report = {
            MemoryTier.HOT: {"tokens": 0, "files": []},
            MemoryTier.WARM: {"tokens": 0, "files": []},
            MemoryTier.COLD: {"tokens": 0, "files": []}
        }

        if not os.path.exists(self.memory_dir):
            return report

        # Scansione ricorsiva della memoria
        for root, dirs, files in os.walk(self.memory_dir):
            dirs.sort()
            for file in files:
                if not file.endswith(".md"):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.memory_dir)
                tokens = TokenEstimator.estimate_file(full_path)

                # Classificazione basata sulle regole
                tier = self._classify_tier(rel_path)
                report[tier]["tokens"] += tokens
                report[tier]["files"].append(rel_path)

        for tier, data in report.items():
            data["files"].sort()
            data["status"] = self._tier_status(tier, data["tokens"])

        return report

    def _classify_tier(self, rel_path: str) -> str:
        for tier in (MemoryTier.HOT, MemoryTier.WARM, MemoryTier.COLD):
            for pattern in self.tier_rules.get(tier, []):
                if self._path_matches(rel_path, pattern):
                    return tier
        
        # Default per nuovi file sconosciuti: Warm
        return MemoryTier.WARM

    def _resolve_memory_dir(self, memory_dir: Optional[str], runtime: Optional[str]) -> str:
        if memory_dir:
            return self._absolute_path(memory_dir)

        env_memory_dir = os.environ.get("MRMEMORY_DIR")
        if env_memory_dir:
            return self._absolute_path(env_memory_dir)

        configured_memory_dir = self.config.get("memory_dir")
        if configured_memory_dir:
            return self._absolute_path(configured_memory_dir)

        configured_runtime = runtime or os.environ.get("MRMEMORY_RUNTIME") or self.config.get("runtime")
        if configured_runtime:
            runtime_dir = self._memory_dir_for_runtime(configured_runtime)
            if runtime_dir:
                return runtime_dir

        detected = self._detect_memory_dir()
        if detected:
            return detected

        return self._memory_dir_for_runtime("gemini")

    def _absolute_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self.root_path, path))

    def _load_config(self) -> dict:
        config_path = os.path.join(self.root_path, "mrmemory.json")
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _memory_dir_for_runtime(self, runtime: str) -> Optional[str]:
        rel_path = self.RUNTIME_MEMORY_DIRS.get(runtime.lower())
        if not rel_path:
            return None
        return os.path.join(self.root_path, rel_path)

    def _detect_memory_dir(self) -> Optional[str]:
        for rel_path in self.RUNTIME_MEMORY_DIRS.values():
            candidate = os.path.join(self.root_path, rel_path)
            if os.path.isdir(candidate):
                return candidate
        return None

    def _merge_config_section(self, section_name, defaults):
        merged = dict(defaults)
        override = self.config.get(section_name, {})
        if not isinstance(override, dict):
            return merged
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                nested = dict(merged[key])
                nested.update(value)
                merged[key] = nested
            else:
                merged[key] = value
        return merged

    def _path_matches(self, rel_path, pattern):
        normalized_path = rel_path.replace(os.sep, "/")
        normalized_pattern = pattern.replace(os.sep, "/")
        if normalized_pattern.endswith("/**"):
            return normalized_path.startswith(normalized_pattern[:-3] + "/")
        if normalized_pattern.endswith("/*"):
            prefix = normalized_pattern[:-1]
            return normalized_path.startswith(prefix) and "/" not in normalized_path[len(prefix):].strip("/")
        return normalized_path == normalized_pattern

    def _tier_status(self, tier, tokens):
        thresholds = self.token_thresholds.get(tier, {})
        growing = thresholds.get("growing")
        bloated = thresholds.get("bloated")
        if bloated is not None and tokens >= bloated:
            return "bloated"
        if growing is not None and tokens >= growing:
            return "growing"
        return "lean"
