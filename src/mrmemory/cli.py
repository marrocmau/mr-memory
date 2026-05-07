import argparse
import json
import os
import sys

from mrmemory.archiver import Archiver
from mrmemory.compactor import Compactor
from mrmemory.core import MemoryManager, MemoryTier
from mrmemory.initializer import Initializer
from mrmemory.indexer import KnowledgeIndexer

try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class SimpleConsole:
    def print(self, text):
        clean_text = str(text)
        for token in (
            "[bold blue]", "[/bold blue]", "[cyan]", "[/cyan]",
            "[magenta]", "[/magenta]", "[green]", "[/green]",
            "[yellow]", "[/yellow]", "[red]", "[/red]",
            "[bold]", "[/bold]", "[bold green]", "[/bold green]",
            "[bold yellow]", "[/bold yellow]", "[bold red]", "[/bold red]",
        ):
            clean_text = clean_text.replace(token, "")
        print(clean_text)


def main(argv=None):
    args = build_parser().parse_args(argv)
    manager = MemoryManager(
        args.root,
        memory_dir=args.memory_dir,
        runtime=args.runtime,
    )

    try:
        if args.command == "init":
            payload = init_payload(
                manager,
                dry_run=args.dry_run,
                force=args.force,
                write_config=args.write_config,
            )
            emit_init(payload, args)
            return 0
        if args.command == "audit":
            payload = audit_payload(manager)
            emit_audit(payload, args)
            return 0
        if args.command == "compact":
            payload = compact_payload(manager, dry_run=args.dry_run, backup=args.backup)
            emit_compact(payload, args)
            return 0 if payload["status"] in ("success", "idle") else 2
        if args.command == "rotate":
            payload = rotate_payload(
                manager,
                dry_run=args.dry_run,
                before=args.before,
                keep_last=args.keep_last,
                include=args.include,
                exclude=args.exclude,
                backup=args.backup,
            )
            emit_rotate(payload, args)
            return 0
        if args.command == "retrieve":
            query = " ".join(args.query)
            payload = retrieve_payload(manager, query)
            emit_retrieve(payload, args)
            return 0 if payload["results"] else 1
    except Exception as e:
        emit_error(str(e), args)
        return 2

    return 2


def build_parser():
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("--root", default=os.getcwd(), help="Project root to inspect.")
    shared_parser.add_argument("--memory-dir", help="Explicit memory directory path.")
    shared_parser.add_argument(
        "--runtime",
        choices=("claude", "codex", "gemini"),
        help="Resolve memory directory for a specific runtime.",
    )
    shared_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    shared_parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    shared_parser.add_argument("--verbose", action="store_true", help="Print extra diagnostic details.")

    parser = argparse.ArgumentParser(
        prog="mr-memory",
        description="Tiered memory management for agentic projects.",
        parents=[shared_parser],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    
    init_parser = subparsers.add_parser("init", help="Create the memory directory skeleton.", parents=[shared_parser])
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing seed files.")
    init_parser.add_argument("--write-config", action="store_true", help="Write mrmemory.json in the project root.")
    
    subparsers.add_parser("audit", help="Analyze current memory weight.", parents=[shared_parser])
    
    compact_parser = subparsers.add_parser("compact", help="Distill session logs into warm memory.", parents=[shared_parser])
    compact_parser.add_argument("--backup", action="store_true", help="Save backups before writing warm memory files.")
    
    rotate_parser = subparsers.add_parser("rotate", help="Move hot/session context into cold storage.", parents=[shared_parser])
    rotate_parser.add_argument("--before", help="Only rotate session files dated before YYYY-MM-DD.")
    rotate_parser.add_argument("--keep-last", type=int, help="Keep the newest N selected session files in place.")
    rotate_parser.add_argument("--include", action="append", default=[], help="Only rotate session files matching this glob. Repeatable.")
    rotate_parser.add_argument("--exclude", action="append", default=[], help="Skip session files matching this glob. Repeatable.")
    rotate_parser.add_argument("--backup", action="store_true", help="Save backups before rotating context.")
    
    retrieve_parser = subparsers.add_parser("retrieve", help="Search cold memory.", parents=[shared_parser])
    retrieve_parser.add_argument("query", nargs="+", help="Search query.")

    return parser


def console_for(args):
    if args.json:
        return None
    return Console() if HAS_RICH else SimpleConsole()


def emit_json(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def audit_payload(manager):
    report = manager.audit()
    tiers = {}
    total_tokens = 0
    for tier, data in report.items():
        tokens = data["tokens"]
        files = data["files"]
        tiers[tier] = {
            "tokens": tokens,
            "file_count": len(files),
            "files": files,
        }
        total_tokens += tokens
    return {
        "command": "audit",
        "root": manager.root_path,
        "memory_dir": manager.memory_dir,
        "total_tokens": total_tokens,
        "tiers": tiers,
    }


def init_payload(manager, dry_run=False, force=False, write_config=False):
    initializer = Initializer(manager)
    results = initializer.init(
        dry_run=dry_run,
        force=force,
        write_config=write_config,
    )
    return {
        "command": "init",
        "root": manager.root_path,
        "memory_dir": manager.memory_dir,
        "dry_run": dry_run,
        "force": force,
        "write_config": write_config,
        **results,
    }


def compact_payload(manager, dry_run=False, backup=False):
    compactor = Compactor(manager)
    results = compactor.sync(dry_run=dry_run, backup=backup)
    return {
        "command": "compact",
        "root": manager.root_path,
        "memory_dir": manager.memory_dir,
        "dry_run": dry_run,
        "backup": backup,
        **results,
    }


def rotate_payload(manager, dry_run=False, before=None, keep_last=None, include=None, exclude=None, backup=False):
    archiver = Archiver(manager)
    results = archiver.rotate(
        dry_run=dry_run,
        before=before,
        keep_last=keep_last,
        include=include,
        exclude=exclude,
        backup=backup,
    )
    return {
        "command": "rotate",
        "root": manager.root_path,
        "memory_dir": manager.memory_dir,
        "dry_run": dry_run,
        "backup": backup,
        **results,
    }


def retrieve_payload(manager, query):
    indexer = KnowledgeIndexer(manager)
    results = indexer.search(query)
    return {
        "command": "retrieve",
        "root": manager.root_path,
        "memory_dir": manager.memory_dir,
        "query": query,
        "count": len(results),
        "results": results,
    }


def emit_init(payload, args):
    if args.json:
        emit_json(payload)
        return

    console = console_for(args)
    title = "🧱 mr-memory: Dry Run Memory Init" if payload["dry_run"] else "🧱 mr-memory: Memory Init"
    console.print(f"[bold blue]{title}[/bold blue]")
    console.print(f"[cyan]Memory directory:[/cyan] {payload['memory_dir']}")

    dir_label = "Would create dirs" if payload["dry_run"] else "Created dirs"
    file_label = "Would create files" if payload["dry_run"] else "Created files"
    overwrite_label = "Would overwrite" if payload["dry_run"] else "Overwritten"
    console.print(f"[green]{dir_label}:[/green] {len(payload['created_dirs'])}")
    console.print(f"[green]{file_label}:[/green] {len(payload['created_files'])}")
    console.print(f"[yellow]Skipped existing files:[/yellow] {len(payload['skipped_files'])}")
    console.print(f"[yellow]{overwrite_label}:[/yellow] {len(payload['overwritten_files'])}")

    if args.verbose:
        for key in ("created_dirs", "created_files", "skipped_files", "overwritten_files"):
            console.print(f"[cyan]{key}:[/cyan] {payload[key]}")


def emit_audit(payload, args):
    if args.json:
        emit_json(payload)
        return

    console = console_for(args)
    console.print("[bold blue]🧠 mr-memory: Context Audit[/bold blue]")
    console.print(f"[cyan]Memory directory:[/cyan] {payload['memory_dir']}")

    if HAS_RICH:
        table = Table(title=f"Memory Bank Analysis: {os.path.basename(payload['root'])}")
        table.add_column("Tier", style="cyan")
        table.add_column("Files Count", justify="center", style="magenta")
        table.add_column("Est. Tokens", justify="right", style="green")
        labels = {
            MemoryTier.HOT: "🔥 Hot",
            MemoryTier.WARM: "⛅ Warm",
            MemoryTier.COLD: "❄️ Cold",
        }
        for tier, label in labels.items():
            data = payload["tiers"][tier]
            table.add_row(label, str(data["file_count"]), f"{data['tokens']:,}")
        table.add_section()
        table.add_row("[bold]TOTAL[/bold]", "", f"[bold]{payload['total_tokens']:,}[/bold]")
        console.print(table)
    else:
        print(f"\nAnalysis for: {os.path.basename(payload['root'])}")
        print(f"TOTAL TOKENS: {payload['total_tokens']:,}")

    if args.verbose:
        for tier, data in payload["tiers"].items():
            console.print(f"[cyan]{tier} files:[/cyan] {', '.join(data['files']) or '-'}")


def emit_compact(payload, args):
    if args.json:
        emit_json(payload)
        return

    console = console_for(args)
    title = "♻️ mr-memory: Dry Run Knowledge Sync" if payload["dry_run"] else "♻️ mr-memory: Autonomous Knowledge Sync"
    console.print(f"[bold blue]{title}[/bold blue]")
    if payload["status"] == "success":
        action = "Would sync" if payload["dry_run"] else "Synced"
        console.print(f"✅ {action} [magenta]{payload['synced_sessions']}[/magenta] sessions.")
        for f in payload["updated_files"]:
            label = "Would update" if payload["dry_run"] else "Updated"
            console.print(f"  [green]» {label}:[/green] {f}")
    else:
        console.print(f"[yellow]{payload['message']}[/yellow]")

    if args.verbose:
        console.print(f"[cyan]Memory directory:[/cyan] {payload['memory_dir']}")
        console.print(f"[cyan]Extracted:[/cyan] {payload.get('extracted_counts', {})}")
        console.print(f"[cyan]Backup dir:[/cyan] {payload.get('backup_dir') or '-'}")


def emit_rotate(payload, args):
    if args.json:
        emit_json(payload)
        return

    console = console_for(args)
    title = "❄️ mr-memory: Dry Run Context Rotation" if payload["dry_run"] else "❄️ mr-memory: Context Rotation"
    console.print(f"[bold blue]{title}[/bold blue]")
    if payload["dry_run"]:
        console.print(f"Would create archive: [cyan]{os.path.basename(payload['created_dir'])}[/cyan]")
    else:
        console.print(f"✅ Created archive: [cyan]{os.path.basename(payload['created_dir'])}[/cyan]")
        if payload.get("backup_dir"):
            console.print(f"🛡️  [green]Backup created:[/green] {os.path.basename(payload['backup_dir'])}")
        console.print("[yellow]Knowledge index updated.[/yellow]")

    if args.verbose:
        console.print(f"[cyan]Memory directory:[/cyan] {payload['memory_dir']}")
        console.print(f"[cyan]Moved files:[/cyan] {payload['moved_files']}")
        console.print(f"[cyan]Skipped files:[/cyan] {payload.get('skipped_files', [])}")
        console.print(f"[cyan]Reset files:[/cyan] {payload['reset_files']}")
        console.print(f"[cyan]Backup dir:[/cyan] {payload.get('backup_dir') or '-'}")


def emit_retrieve(payload, args):
    if args.json:
        emit_json(payload)
        return

    console = console_for(args)
    console.print(f"[bold blue]🔍 mr-memory: Retrieving knowledge for '{payload['query']}'[/bold blue]")
    if not payload["results"]:
        console.print(f"[yellow]No results found for '{payload['query']}' in Cold Memory.[/yellow]")
        return

    if HAS_RICH:
        table = Table(title=f"Search Results for '{payload['query']}'")
        table.add_column("Date", style="cyan")
        table.add_column("File Path", style="magenta")
        table.add_column("Key Topics", style="green")
        for entry in payload["results"]:
            topics = ", ".join(entry["keywords"][:3])
            table.add_row(entry["date"], entry["rel_path"], topics)
        console.print(table)
    else:
        for entry in payload["results"]:
            print(f"{entry['date']}  {entry['rel_path']}  {', '.join(entry['keywords'][:3])}")

    console.print(f"\n[bold green]Found {payload['count']} relevant file(s).[/bold green]")
    console.print("Instruction: You can read these specific files to recover full context.")


def emit_error(message, args):
    payload = {"status": "error", "message": message}
    if getattr(args, "json", False):
        emit_json(payload)
    else:
        console = console_for(args)
        console.print(f"[red]Error: {message}[/red]")


if __name__ == "__main__":
    raise SystemExit(main())
