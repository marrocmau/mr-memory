import os
import re
import shutil
import tempfile
from datetime import datetime

class Compactor:
    def __init__(self, manager):
        self.manager = manager
        self.memory_dir = manager.memory_dir
        self.patterns = manager.compaction_patterns

    def sync(self, dry_run=False, backup=False):
        """Esegue la sincronizzazione autonoma: estrae dai log e aggiorna i file Warm Tier"""
        sessions_dir = os.path.join(self.memory_dir, "sessions")
        if not os.path.exists(sessions_dir):
            return {"status": "error", "message": "No sessions found to sync."}

        # Cambiato in list per mantenere il riferimento alla sessione di origine
        extracted_data = {
            "progress": [],
            "decisions": [],
            "gotchas": []
        }

        # 1. Estrazione dati da tutte le sessioni non ancora archiviate
        session_files = [f for f in os.listdir(sessions_dir) if f.endswith(".md")]
        if not session_files:
            return {"status": "idle", "message": "Nothing to sync."}

        for file in session_files:
            content = self._read_file(os.path.join(sessions_dir, file))
            # Passiamo il nome del file per creare il backlink
            session_name = file.replace(".md", "")
            self._parse_content(content, extracted_data, session_name)

        # 2. Prepara un piano di aggiornamento prima di toccare il filesystem.
        update_plan = []
        if extracted_data["progress"]:
            plan = self._prepare_markdown_update(os.path.join(self.memory_dir, "PROGRESS.md"), extracted_data["progress"], "## Completed Tasks", "warm")
            if plan:
                update_plan.append(plan)
        
        if extracted_data["decisions"]:
            plan = self._prepare_markdown_update(os.path.join(self.memory_dir, "DECISIONS.md"), extracted_data["decisions"], "## Log", "warm")
            if plan:
                update_plan.append(plan)

        if extracted_data["gotchas"]:
            plan = self._prepare_markdown_update(os.path.join(self.memory_dir, "GOTCHAS.md"), extracted_data["gotchas"], "## Technical Knowledge", "warm")
            if plan:
                update_plan.append(plan)

        updates = [plan["rel_path"] for plan in update_plan]
        backup_dir = None
        backed_up_files = []
        rolled_back = False

        if update_plan and not dry_run:
            try:
                backup_dir, backed_up_files = self._apply_update_plan(update_plan, backup=backup)
            except Exception:
                rolled_back = True
                raise

        return {
            "status": "success", 
            "synced_sessions": len(session_files),
            "updated_files": updates,
            "extracted_counts": {key: len(value) for key, value in extracted_data.items()},
            "backup_dir": backup_dir,
            "backed_up_files": backed_up_files,
            "rolled_back": rolled_back
        }

    def _read_file(self, path):
        if not os.path.exists(path): return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_content(self, content, data, session_name):
        for key in ("progress", "decisions", "gotchas"):
            for pattern in self.patterns.get(key, []):
                for match in re.findall(pattern, content, re.MULTILINE):
                    if isinstance(match, tuple):
                        match = next((part for part in match if part), "")
                    if match:
                        data[key].append(f"{match.strip()} [[{session_name}]]")

    def _get_yaml_frontmatter(self, title, tier):
        from datetime import datetime
        return f"""---
title: {title}
tier: {tier}
created: {datetime.now().strftime("%Y-%m-%d")}
updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
tags: [mr-memory, {tier}]
---

"""

    def _prepare_markdown_update(self, file_path, new_items, section_header, tier):
        """Aggiorna un file Markdown aggiungendo nuovi item in una sezione senza duplicati"""
        content = self._read_file(file_path)
        filename = os.path.basename(file_path).replace(".md", "")
        
        if not content:
            content = self._get_yaml_frontmatter(filename, tier) + "# " + filename + "\n\n" + section_header + "\n"
        
        # Filtra solo i nuovi item che non sono già presenti nel file (senza contare il backlink per il check duplicati)
        to_add = []
        for item in new_items:
            # Rimuove il backlink [[...]] per controllare se la sostanza dell'item esiste già
            clean_item = re.sub(r" \[\[.*\]\]$", "", item)
            if clean_item not in content:
                to_add.append(item)
        
        if not to_add:
            return None

        # Se la sezione esiste, aggiunge sotto, altrimenti appende in fondo
        if section_header in content:
            addition = "\n".join(["- " + item for item in to_add]) + "\n"
            new_content = content.replace(section_header, section_header + "\n" + addition)
        else:
            new_content = content + "\n\n" + section_header + "\n" + "\n".join(["- " + item for item in to_add]) + "\n"

        # Aggiorna il timestamp nell'header
        new_content = re.sub(r"updated: .*", f'updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', new_content)

        return {
            "path": file_path,
            "rel_path": os.path.relpath(file_path, self.memory_dir),
            "old_content": self._read_file(file_path) if os.path.exists(file_path) else None,
            "new_content": new_content,
        }

    def _apply_update_plan(self, update_plan, backup=False):
        snapshots = {plan["path"]: plan["old_content"] for plan in update_plan}
        backup_dir = None
        backed_up_files = []

        if backup:
            backup_dir = os.path.join(
                self.memory_dir,
                "backups",
                "compact_{}".format(datetime.now().strftime("%Y-%m-%d_%H%M%S"))
            )
            os.makedirs(backup_dir, exist_ok=True)
            for plan in update_plan:
                if plan["old_content"] is None:
                    continue
                backup_path = os.path.join(backup_dir, plan["rel_path"])
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(plan["path"], backup_path)
                backed_up_files.append(os.path.relpath(backup_path, self.memory_dir))

        try:
            for plan in update_plan:
                self._atomic_write(plan["path"], plan["new_content"])
        except Exception:
            self._rollback(snapshots)
            raise

        return backup_dir, backed_up_files

    def _atomic_write(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=".{}.tmp.".format(os.path.basename(path)),
            dir=os.path.dirname(path),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _rollback(self, snapshots):
        for path, content in snapshots.items():
            if content is None:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
            else:
                self._atomic_write(path, content)
