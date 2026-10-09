"""Command Line Interface for GitHub Daily Status Reporter."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ghtoolkit import GitHubClient

from processing.ai_enhancer import AIEnhancer
from collection.collector import ActivityCollector
from config.loader import (
    add_project,
    filter_projects,
    load_projects,
    remove_project,
    resolve_config_path,
)
from shared.demo_data import (
    get_demo_report_1,
    get_demo_report_2,
    get_demo_report_3,
)
from presentation.formatter import StatusReportFormatter
from shared.utils import parse_target_date


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="status-reporter",
        description="Daily GitHub Commit, PR, Review & Contribution Status Reporter",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # --- Subcommand: projects ---
    proj_parser = subparsers.add_parser(
        "projects", help="Manage dynamic project configurations in projects.json"
    )
    proj_sub = proj_parser.add_subparsers(dest="projects_action", help="Action to perform")

    # projects list
    list_p = proj_sub.add_parser("list", help="List all configured projects")
    list_p.add_argument("-c", "--config", type=str, help="Path to projects.json")

    # projects add
    add_p = proj_sub.add_parser("add", help="Add or update a project in projects.json")
    add_p.add_argument("--name", required=True, help="Project group name (e.g. HR-Tool)")
    add_p.add_argument("--owner", required=True, help="GitHub repository owner / org")
    add_p.add_argument("--repo", required=True, help="GitHub repository name")
    add_p.add_argument(
        "--category", default="Backend", help="Category: Backend or Frontend (default: Backend)"
    )
    add_p.add_argument("--author", default=None, help="Contributor username (default: Volcann)")
    add_p.add_argument("-c", "--config", type=str, help="Path to projects.json")

    # projects remove
    rem_p = proj_sub.add_parser("remove", help="Remove a project from projects.json")
    rem_p.add_argument("--owner", required=True, help="GitHub repository owner / org")
    rem_p.add_argument("--repo", required=True, help="GitHub repository name")
    rem_p.add_argument("-c", "--config", type=str, help="Path to projects.json")

    # --- Subcommand: clean-reports ---
    clean_p = subparsers.add_parser(
        "clean-reports",
        help="Remove unused, old, or all generated reports from reports/",
    )
    clean_p.add_argument(
        "--keep",
        "-k",
        type=str,
        default=None,
        help="Date or name of report to keep (e.g. '24-SEP-2026', 'latest'). Defaults to keeping most recent active report.",
    )
    clean_p.add_argument(
        "--all",
        "-a",
        action="store_true",
        default=False,
        help="Remove all generated reports in reports/ directory",
    )
    clean_p.add_argument(
        "--reports-dir",
        type=str,
        default="reports",
        help="Path to reports directory (default: reports)",
    )
    clean_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview files that would be removed without deleting them",
    )

    # --- Root arguments for report generation ---
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        default="today",
        help="Target date (e.g. '11-SEP-2026', '2026-09-11', 'today', 'yesterday')",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to projects.json config file",
    )
    parser.add_argument(
        "-p",
        "--project",
        type=str,
        default=None,
        help="Filter activity by project name (e.g. 'HR-Tool')",
    )
    parser.add_argument(
        "-r",
        "--repo",
        type=str,
        default=None,
        help="Filter activity by repository name",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter activity by category (e.g. 'Backend' or 'Frontend')",
    )
    parser.add_argument(
        "-a",
        "--author",
        type=str,
        default=None,
        help="Override author / contributor username",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Custom text file output path for saving the generated report",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        default=True,
        help="Enable Gemini AI summarization if GEMINI_API_KEY is available (default: enabled)",
    )
    parser.add_argument(
        "--no-ai",
        action="store_false",
        dest="use_ai",
        help="Disable Gemini AI and use deterministic rule-based summary generation",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash-lite",
        help="Gemini model for AI summarization (default: gemini-2.5-flash-lite [free tier])",
    )
    parser.add_argument(
        "--gemini-api-key",
        type=str,
        default=None,
        help="Google Gemini API key (defaults to GEMINI_API_KEY environment variable)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress live progress logs and only output the final report",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Sleep pacing interval (seconds) between operations to preserve API quota",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Run validation pipeline to verify claims against Git evidence and strip hallucinations (default: enabled)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_false",
        dest="validate",
        help="Disable the validation pipeline",
    )
    parser.add_argument(
        "--demo",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help="Run with canonical demo dataset (1, 2, or 3) reproducing prompt examples",
    )

    return parser


def handle_projects_command(args: argparse.Namespace) -> int:
    """Handle project configuration subcommands."""
    action = getattr(args, "projects_action", "list")
    config_path = getattr(args, "config", None)

    if action == "list" or action is None:
        projects = load_projects(config_path)
        resolved_path = resolve_config_path(config_path)
        print(f"\nConfigured Projects ({len(projects)}) from: {resolved_path}")
        print("=" * 80)
        print(f"{'PROJECT':<16} {'CATEGORY':<12} {'REPO':<35} {'AUTHOR':<15}")
        print("-" * 80)
        for p in projects:
            full_repo = f"{p.owner}/{p.repo}"
            print(f"{p.name:<16} {p.category:<12} {full_repo:<35} {p.author:<15}")
        print("=" * 80 + "\n")
        return 0

    if action == "add":
        new_p = add_project(
            name=args.name,
            owner=args.owner,
            repo=args.repo,
            category=args.category,
            author=args.author,
            config_path=config_path,
        )
        print(
            f"✅ Successfully added/updated project '{new_p.name}' ({new_p.full_name}) in projects.json"
        )
        return 0

    if action == "remove":
        removed = remove_project(owner=args.owner, repo=args.repo, config_path=config_path)
        if removed:
            print(f"✅ Removed project '{args.owner}/{args.repo}' from projects.json")
            return 0
        print(f"⚠️ Project '{args.owner}/{args.repo}' not found in projects.json")
        return 1

    return 0


def handle_clean_reports_command(args: argparse.Namespace) -> int:
    """Handle clean-reports subcommand."""
    from shared.utils import clean_reports_directory

    reports_dir = getattr(args, "reports_dir", "reports")
    keep = getattr(args, "keep", None)
    remove_all = getattr(args, "all", False)
    dry_run = getattr(args, "dry_run", False)

    deleted, kept = clean_reports_directory(
        reports_dir=reports_dir,
        keep=keep,
        remove_all=remove_all,
        dry_run=dry_run,
    )

    action_word = "Would remove" if dry_run else "Removed"
    if not deleted:
        print(f"ℹ️ No unused reports to remove in '{reports_dir}'.")
        if kept:
            print(f"   Currently active: {', '.join(p.name for p in kept)}")
        return 0

    prefix = "[dry-run] " if dry_run else ""
    print(f"\n🧹 {prefix}{action_word} {len(deleted)} unused report(s) from '{reports_dir}':")
    for p in sorted(deleted):
        print(f"   • {p.name}")

    if kept:
        print("\n✅ Kept active report(s):")
        for p in sorted(kept):
            print(f"   • {p.name}")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "projects":
        return handle_projects_command(args)

    if args.subcommand == "clean-reports":
        return handle_clean_reports_command(args)

    # 1. Parse target date
    try:
        target_date = parse_target_date(args.date)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1

    formatter = StatusReportFormatter()

    # 2. Check for demo mode
    if args.demo:
        if args.demo == 1:
            report = get_demo_report_1()
        elif args.demo == 2:
            report = get_demo_report_2()
        else:
            report = get_demo_report_3()
    else:
        # Load and filter projects
        projects = load_projects(args.config)
        if args.author:
            for p in projects:
                p.author = args.author

        filtered = filter_projects(
            projects,
            project_name=args.project,
            category=args.category,
            repo=args.repo,
        )

        if not filtered:
            print(
                f"⚠️ No active projects found matching filters (project={args.project}, "
                f"category={args.category}, repo={args.repo}).\n"
                f"Run 'status-reporter projects list' to view configured projects.",
                file=sys.stderr,
            )
            return 1

        print(
            f"🔍 Querying GitHub for {target_date} across {len(filtered)} project(s)...",
            file=sys.stderr,
        )

        client = GitHubClient()
        gemini_key = args.gemini_api_key or os.getenv("GEMINI_API_KEY")
        ai = AIEnhancer(api_key=gemini_key, model=args.model)
        if args.use_ai and ai.is_available:
            print(f"✨ Gemini Free API enabled (model: {args.model})", file=sys.stderr)
        collector = ActivityCollector(
            github_client=client,
            ai_enhancer=ai,
            use_ai=args.use_ai,
            verbose=not args.quiet,
        )
        report = collector.collect_for_date(filtered, target_date)

    # 2.5. Pass through Validation Pipeline
    val_result = None
    if getattr(args, "validate", True):
        from config.validator import StatusValidator

        validator = StatusValidator(
            sleep_interval=getattr(args, "sleep", 0.0),
            verbose=not args.quiet,
        )
        val_result = validator.validate_report(report)
        if val_result.has_removals:
            print("\n" + val_result.format_summary() + "\n", file=sys.stderr)

    # 3. Format report
    rendered_output = formatter.format_report(report)

    # 4. Print report to stdout
    print("\n" + rendered_output)

    # 5. Determine and write to separate .txt file
    if args.output:
        out_file = Path(args.output)
    else:
        # Default report file
        safe_date_str = report.date_display.replace("-", "_")
        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_file = reports_dir / f"status_report_{safe_date_str}.txt"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(rendered_output)
        print(f"📄 Report saved separately at: {out_file.resolve()}", file=sys.stderr)
    except OSError as e:
        print(f"⚠️ Warning: Could not write report to {out_file}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
