import json
import os
from datetime import datetime


def get_seed_content(title, tier="warm"):
    return f"""---
title: {title}
tier: {tier}
tags: [mr-memory, {tier}]
created: {datetime.now().strftime("%Y-%m-%d")}
---

# {title}

"""

MEMORY_FILES = {
    "MEMORY.md": get_seed_content("MEMORY", "hot") + "Active session context goes here.\n",
    "PROGRESS.md": get_seed_content("PROGRESS") + "## Completed Tasks\n",
    "DECISIONS.md": get_seed_content("DECISIONS") + "## Log\n",
    "GOTCHAS.md": get_seed_content("GOTCHAS") + "## Technical Knowledge\n",
    "BACKLOG.md": get_seed_content("BACKLOG"),
    "FEATURE_STATUS.md": get_seed_content("FEATURE_STATUS"),
    "BUILD_RECIPES.md": get_seed_content("BUILD_RECIPES"),
    "UX_NOTES.md": get_seed_content("UX_NOTES"),
    "RELEASES.md": get_seed_content("RELEASES"),
}

MEMORY_DIRS = [
    "sessions",
    "private",
    "backups",
    "archive",
]


class Initializer:
    def __init__(self, manager):
        self.manager = manager
        self.memory_dir = manager.memory_dir

    def init(self, dry_run=False, force=False, write_config=False):
        created_dirs = []
        created_files = []
        skipped_files = []
        overwritten_files = []

        all_dirs = [self.memory_dir] + [
            os.path.join(self.memory_dir, rel_path) for rel_path in MEMORY_DIRS
        ]

        for path in all_dirs:
            if os.path.isdir(path):
                continue
            created_dirs.append(path)
            if not dry_run:
                os.makedirs(path, exist_ok=True)

        for filename, content in MEMORY_FILES.items():
            path = os.path.join(self.memory_dir, filename)
            exists = os.path.exists(path)
            if exists and not force:
                skipped_files.append(path)
                continue
            if exists:
                overwritten_files.append(path)
            else:
                created_files.append(path)
            if not dry_run:
                self._write_file(path, content)

        scratch_path = os.path.join(self.memory_dir, "private", "scratch.md")
        if os.path.exists(scratch_path) and not force:
            skipped_files.append(scratch_path)
        else:
            if os.path.exists(scratch_path):
                overwritten_files.append(scratch_path)
            else:
                created_files.append(scratch_path)
            if not dry_run:
                self._write_file(scratch_path, "# Scratch\n\nPrivate working notes.\n")

        config_path = os.path.join(self.manager.root_path, "mrmemory.json")
        if write_config:
            config_content = {
                "memory_dir": os.path.relpath(self.memory_dir, self.manager.root_path),
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if os.path.exists(config_path) and not force:
                skipped_files.append(config_path)
            else:
                if os.path.exists(config_path):
                    overwritten_files.append(config_path)
                else:
                    created_files.append(config_path)
                if not dry_run:
                    self._write_file(config_path, json.dumps(config_content, indent=2) + "\n")

        return {
            "status": "success",
            "created_dirs": created_dirs,
            "created_files": created_files,
            "skipped_files": skipped_files,
            "overwritten_files": overwritten_files,
        }

    def _write_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
