import os
import shutil
import fnmatch
import re
from datetime import datetime
from mrmemory.core import MemoryTier

class Archiver:
    def __init__(self, manager):
        self.manager = manager
        self.memory_dir = manager.memory_dir

    def rotate(self, dry_run=False, before=None, keep_last=None, include=None, exclude=None, backup=False):
        """Esegue la rotazione della memoria: Hot/Warm -> Cold"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        archive_dir = os.path.join(self.memory_dir, "archive", timestamp)
        include = include or []
        exclude = exclude or []
        
        results = {
            "created_dir": archive_dir,
            "moved_files": [],
            "reset_files": [],
            "skipped_files": [],
            "backup_dir": None,
            "backed_up_files": [],
            "filters": {
                "before": before,
                "keep_last": keep_last,
                "include": include,
                "exclude": exclude,
            }
        }

        # 1. Identificazione dei file da ruotare
        sessions_dir = os.path.join(self.memory_dir, "sessions")
        selected_sessions = []
        if os.path.exists(sessions_dir):
            selected_sessions, skipped_sessions = self._select_session_files(
                sessions_dir,
                before=before,
                keep_last=keep_last,
                include=include,
                exclude=exclude,
            )
            results["moved_files"].extend([os.path.join("sessions", item) for item in selected_sessions])
            results["skipped_files"].extend([os.path.join("sessions", item) for item in skipped_sessions])

        memory_md = os.path.join(self.memory_dir, "MEMORY.md")
        has_memory_md = os.path.exists(memory_md)
        if has_memory_md:
            results["reset_files"].append("MEMORY.md")

        backups_dir = os.path.join(self.memory_dir, "backups")
        has_backups = os.path.exists(backups_dir)
        if has_backups:
            results["moved_files"].append("backups/")

        if dry_run:
            results["indexed"] = False
            return results

        # 2. Backup opzionale prima di procedere
        temp_backup_dir = None
        if backup:
            import tempfile
            temp_backup_dir = tempfile.mkdtemp(prefix="mrmemory_rotate_backup_")
            results["backed_up_files"] = self._perform_backup_to_dir(
                selected_sessions, has_memory_md, temp_backup_dir
            )

        # 3. Esecuzione operazioni
        try:
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)

            # Spostamento sessioni
            if selected_sessions:
                target_sessions = os.path.join(archive_dir, "sessions")
                os.makedirs(target_sessions, exist_ok=True)
                for rel_path in selected_sessions:
                    source_path = os.path.join(sessions_dir, rel_path)
                    target_path = os.path.join(target_sessions, rel_path)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.move(source_path, target_path)
                self._cleanup_empty_dirs(sessions_dir)
            elif not os.path.exists(sessions_dir):
                os.makedirs(sessions_dir)

            # Archiviazione e reset MEMORY.md
            if has_memory_md:
                archive_memory_md = os.path.join(archive_dir, "MEMORY_at_rotation.md")
                shutil.copy2(memory_md, archive_memory_md)
                
                reset_content = "# MEMORY\n\n(Context rotated to archive on {})\n".format(timestamp)
                self._atomic_write(memory_md, reset_content)

            # Spostamento backup esistenti
            if has_backups:
                target_backups = os.path.join(archive_dir, "backups")
                if os.path.exists(target_backups):
                    shutil.rmtree(target_backups)
                shutil.move(backups_dir, target_backups)
                os.makedirs(backups_dir)
            
            # 4. Spostamento del backup di sicurezza nella nuova cartella backups
            if temp_backup_dir:
                final_backup_dir = os.path.join(self.memory_dir, "backups", "rotate_{}".format(timestamp))
                os.makedirs(os.path.dirname(final_backup_dir), exist_ok=True)
                shutil.move(temp_backup_dir, final_backup_dir)
                results["backup_dir"] = final_backup_dir

            # 5. Genera l'indice per il nuovo archivio
            from mrmemory.indexer import KnowledgeIndexer
            indexer = KnowledgeIndexer(self.manager)
            indexer.index_archive(archive_dir)
            results["indexed"] = True

        except Exception:
            if temp_backup_dir and os.path.exists(temp_backup_dir):
                shutil.rmtree(temp_backup_dir)
            raise

        return results

    def _perform_backup_to_dir(self, selected_sessions, has_memory, target_dir):
        backed_up = []

        # Backup sessioni
        if selected_sessions:
            sessions_dir = os.path.join(self.memory_dir, "sessions")
            for rel_path in selected_sessions:
                src = os.path.join(sessions_dir, rel_path)
                dst = os.path.join(target_dir, "sessions", rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                backed_up.append(os.path.join("sessions", rel_path))

        # Backup MEMORY.md
        if has_memory:
            src = os.path.join(self.memory_dir, "MEMORY.md")
            dst = os.path.join(target_dir, "MEMORY.md")
            shutil.copy2(src, dst)
            backed_up.append("MEMORY.md")

        return backed_up


    def _atomic_write(self, path, content):
        import tempfile
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


    def _select_session_files(self, sessions_dir, before=None, keep_last=None, include=None, exclude=None):
        files = []
        for root, dirs, filenames in os.walk(sessions_dir):
            dirs.sort()
            for filename in sorted(filenames):
                if not filename.endswith(".md"):
                    continue
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, sessions_dir)
                files.append(rel_path)

        selected = list(files)

        if before:
            selected = [rel_path for rel_path in selected if self._date_key(rel_path) < before]

        if include:
            selected = [rel_path for rel_path in selected if self._matches_any(rel_path, include)]

        if exclude:
            selected = [rel_path for rel_path in selected if not self._matches_any(rel_path, exclude)]

        if keep_last is not None and keep_last > 0:
            sorted_files = sorted(selected, key=self._date_key)
            keep = set(sorted_files[-keep_last:])
            selected = [rel_path for rel_path in selected if rel_path not in keep]

        skipped = [rel_path for rel_path in files if rel_path not in selected]
        return selected, skipped

    def _date_key(self, rel_path):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", rel_path)
        return match.group(1) if match else "9999-99-99"

    def _matches_any(self, rel_path, patterns):
        normalized = rel_path.replace(os.sep, "/")
        return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)

    def _cleanup_empty_dirs(self, root_dir):
        for root, dirs, files in os.walk(root_dir, topdown=False):
            if root == root_dir:
                continue
            if not os.listdir(root):
                os.rmdir(root)
