"""
skillsctl – main CLI entry point.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler

console = Console()

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, markup=True)],
    )


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="skillsctl")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """skillsctl – multi-repo skill/prompt cleanup & migration tool."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--repo",
    "repos",
    multiple=True,
    metavar="OWNER/REPO",
    help="Remote repo to scan (repeatable). Accepts owner/repo or full URL.",
)
@click.option(
    "--local",
    "local_paths",
    multiple=True,
    metavar="PATH",
    help="Local directory to scan (repeatable).",
)
@click.option(
    "--output",
    "-o",
    default="scan-manifest.json",
    show_default=True,
    help="Output manifest file path.",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
    help="Dry-run mode (scan is always read-only; this flag is for consistency).",
)
@click.pass_context
def scan(
    ctx: click.Context,
    repos: tuple[str, ...],
    local_paths: tuple[str, ...],
    output: str,
    dry_run: bool,
) -> None:
    """Clone/fetch repos and detect candidate skill/prompt files."""
    from .scan import run_scan

    if not repos and not local_paths:
        console.print("[yellow]No repos or local paths provided. Pass --repo or --local.[/yellow]")
        raise SystemExit(1)

    console.print(
        f"[bold]Scanning[/bold] {len(repos)} remote repo(s), {len(local_paths)} local path(s)…"
    )
    manifest = run_scan(
        list(repos),
        local_paths=list(local_paths),
        output_path=output,
        dry_run=dry_run,
    )
    n = len(manifest.get("candidates", []))
    console.print(f"[green]Found {n} candidate file(s).[/green] Manifest: [bold]{output}[/bold]")


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--manifest",
    "-m",
    default="scan-manifest.json",
    show_default=True,
    help="Scan manifest file to audit.",
)
@click.option(
    "--file",
    "files",
    multiple=True,
    metavar="PATH",
    help="Audit specific files directly (repeatable).",
)
@click.option(
    "--output",
    "-o",
    default="audit-report.json",
    show_default=True,
    help="JSON report output path.",
)
@click.option(
    "--report-md",
    default="audit-report.md",
    show_default=True,
    help="Markdown report output path.",
)
@click.option("--offline", is_flag=True, default=False, help="Use built-in baseline rules only.")
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
)
@click.pass_context
def audit(
    ctx: click.Context,
    manifest: str,
    files: tuple[str, ...],
    output: str,
    report_md: str,
    offline: bool,
    dry_run: bool,
) -> None:
    """Audit skill files against the best-practices rule set."""
    from .audit import run_audit

    if files:
        source: Any = list(files)
        console.print(f"[bold]Auditing[/bold] {len(files)} file(s)…")
    else:
        manifest_path = Path(manifest)
        if not manifest_path.exists():
            console.print(f"[red]Manifest not found: {manifest}[/red]")
            raise SystemExit(1)
        source = json.loads(manifest_path.read_text())
        console.print(f"[bold]Auditing[/bold] manifest: [bold]{manifest}[/bold]…")

    report = run_audit(
        source,
        output_path=output,
        report_md_path=report_md,
        offline=offline,
        dry_run=dry_run,
    )
    s = report.get("summary", {})
    bsev = s.get("by_severity", {})
    console.print(
        f"[green]Audit complete.[/green] "
        f"{s.get('files_audited', 0)} files · "
        f"{s.get('total_findings', 0)} findings "
        f"([red]{bsev.get('error', 0)} errors[/red], "
        f"[yellow]{bsev.get('warning', 0)} warnings[/yellow], "
        f"[blue]{bsev.get('info', 0)} info[/blue])"
    )
    console.print(f"Reports: [bold]{output}[/bold], [bold]{report_md}[/bold]")


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--audit-report",
    "-a",
    default="audit-report.json",
    show_default=True,
    help="Audit report JSON to build a plan from.",
)
@click.option(
    "--output",
    "-o",
    default="improvement-plan.json",
    show_default=True,
    help="JSON plan output path.",
)
@click.option(
    "--report-md",
    default="improvement-plan.md",
    show_default=True,
    help="Markdown plan output path.",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
)
@click.pass_context
def plan(
    ctx: click.Context,
    audit_report: str,
    output: str,
    report_md: str,
    dry_run: bool,
) -> None:
    """Produce a prioritised improvement plan from audit findings."""
    from .plan import run_plan

    audit_path = Path(audit_report)
    if not audit_path.exists():
        console.print(f"[red]Audit report not found: {audit_report}[/red]")
        raise SystemExit(1)

    ar = json.loads(audit_path.read_text())
    p = run_plan(ar, output_path=output, report_md_path=report_md, dry_run=dry_run)
    s = p.get("summary", {})
    console.print(
        f"[green]Plan generated.[/green] "
        f"{s.get('total_items', 0)} items · "
        f"{s.get('fixable_items', 0)} auto-fixable"
    )
    console.print(f"Reports: [bold]{output}[/bold], [bold]{report_md}[/bold]")


# ---------------------------------------------------------------------------
# fix
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--plan-file",
    "-p",
    default="improvement-plan.json",
    show_default=True,
    help="Improvement plan JSON.",
)
@click.option(
    "--apply",
    "apply_flag",
    is_flag=True,
    default=False,
    help="Write changes to disk.  Without this flag, nothing is written.",
)
@click.option("--offline", is_flag=True, default=False)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
    help="Dry-run (default). Pass --no-dry-run together with --apply to write.",
)
@click.pass_context
def fix(
    ctx: click.Context,
    plan_file: str,
    apply_flag: bool,
    offline: bool,
    dry_run: bool,
) -> None:
    """Apply safe, deterministic fixes in-place (requires --apply)."""
    from .fix import run_fix

    plan_path = Path(plan_file)
    if not plan_path.exists():
        console.print(f"[red]Plan file not found: {plan_file}[/red]")
        raise SystemExit(1)

    p = json.loads(plan_path.read_text())

    if apply_flag and dry_run:
        console.print(
            "[yellow]--apply was given but --dry-run is still set. "
            "Pass --no-dry-run to actually write files.[/yellow]"
        )

    report = run_fix(p, apply=apply_flag, offline=offline, dry_run=dry_run)
    applied = report.get("applied", False)
    status = "[green]Applied[/green]" if applied else "[yellow]Dry-run[/yellow]"
    console.print(
        f"{status}: {report.get('actions_count', 0)} fix action(s). "
        f"Post-fix audit summary: {report.get('post_fix_audit_summary', {})}"
    )


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--manifest",
    "-m",
    default="scan-manifest.json",
    show_default=True,
    help="Scan manifest JSON.",
)
@click.option(
    "--skills-root",
    default=None,
    help="Target skills directory (default: skills/ in this repo).",
)
@click.option(
    "--apply",
    "apply_flag",
    is_flag=True,
    default=False,
    help="Write migrated files to disk.",
)
@click.option(
    "--allow-delete",
    is_flag=True,
    default=False,
    help="Delete source files after migration (requires --apply).",
)
@click.option(
    "--no-pointer",
    is_flag=True,
    default=False,
    help="Skip writing pointer stubs in source repos.",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    show_default=True,
)
@click.pass_context
def migrate(
    ctx: click.Context,
    manifest: str,
    skills_root: str | None,
    apply_flag: bool,
    allow_delete: bool,
    no_pointer: bool,
    dry_run: bool,
) -> None:
    """
    Migrate skill files into this repo under skills/<domain>/...

    Requires --apply to write any files.
    Deletion requires both --apply and --allow-delete.
    """
    from .migrate import run_migrate

    manifest_path = Path(manifest)
    if not manifest_path.exists():
        console.print(f"[red]Manifest not found: {manifest}[/red]")
        raise SystemExit(1)

    if allow_delete and not apply_flag:
        console.print("[red]--allow-delete requires --apply.[/red]")
        raise SystemExit(1)

    m = json.loads(manifest_path.read_text())
    report = run_migrate(
        m,
        skills_root=skills_root,
        apply=apply_flag,
        allow_delete=allow_delete,
        dry_run=dry_run,
        write_pointer=not no_pointer,
    )
    s = report.get("summary", {})
    status = "[green]Applied[/green]" if report.get("applied") else "[yellow]Dry-run[/yellow]"
    console.print(
        f"{status}: {s.get('total', 0)} skill(s) · "
        f"{s.get('applied', 0)} migrated · "
        f"{s.get('pointers_written', 0)} pointers · "
        f"{s.get('deleted', 0)} deleted."
    )
