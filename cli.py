"""``qv`` command-line interface.

Spec reference: MASTER_DEVELOPER_SPEC.pdf Section 3 defines the CLI surface.
Built with :mod:`argparse` (Standard Library) rather than a third-party CLI
framework, per this project's "stdlib before third-party" standard.

Commands
    qv launch [--dir PATH]
        Initialize a local career dossier workspace with starter templates.
    qv sync-ast --target JD_FILE --template TEMPLATE_ID [--dir PATH] [--json]
        Parse a job description, run the Micro-Diff Matching Engine against
        the workspace dossier, and print the G-Force match score.
    qv export --bundle NAME --format {pdf,docx} [--dir PATH]
               [--target JD_FILE --template TEMPLATE_ID] [--narrative]
        Compile the dossier (optionally with a match summary and an
        LLM-generated narrative) into a PDF or DOCX bundle.
    qv template validate PATH [--fix] [--json]
        Lint a mission template YAML file; with --fix, rescale weights to
        sum to 1.00 and persist the fix.
    qv vault set-key [--dir PATH]
        Store an LLM API key in the workspace's encrypted vault. This
        command is an addition beyond the original spec's CLI table,
        necessary to make narrative generation (Stage 1 blueprint decision)
        usable at all without a plaintext key on disk.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from questvector.core import matcher, templates, workspace
from questvector.core.exporter import export_bundle
from questvector.core.llm import AnthropicNarrativeGenerator, build_narrative_prompt
from questvector.core.markdown_parser import parse_dossier
from questvector.core.models import MissionTemplate
from questvector.core.vault import VaultData, load_vault, update_vault
from questvector.exceptions import QuestVectorError

_VAULT_FILENAME = ".questvector.vault"


def _resolve_workspace_dir(raw: str | None) -> Path:
    """Resolve the ``--dir`` argument to an absolute workspace path.

    Args:
        raw: The raw ``--dir`` value, or ``None`` to use the current
            working directory.

    Returns:
        An absolute :class:`Path`.
    """
    return Path(raw).expanduser().resolve() if raw else Path.cwd()


def _find_template(workspace_dir: Path, template_id: str) -> MissionTemplate:
    """Locate and load a mission template by id from a workspace.

    Searches ``templates/starter/`` and ``templates/`` for
    ``<template_id>.yaml`` or ``.yml``.

    Args:
        workspace_dir: The workspace directory to search.
        template_id: The template's ``id`` (filename stem).

    Returns:
        The loaded :class:`MissionTemplate`.

    Raises:
        QuestVectorError: If no matching template file is found.
    """
    search_dirs = [
        workspace_dir / "templates" / "starter",
        workspace_dir / "templates",
    ]
    for directory in search_dirs:
        for extension in (".yaml", ".yml"):
            candidate = directory / f"{template_id}{extension}"
            if candidate.exists():
                return templates.load_template(candidate)

    available = sorted(
        path.stem
        for directory in search_dirs
        if directory.is_dir()
        for path in directory.glob("*.y*ml")
    )
    raise QuestVectorError(
        f"No mission template found with id '{template_id}'",
        context={"searched": [str(d) for d in search_dirs], "available": available},
    )


def _cmd_launch(args: argparse.Namespace) -> int:
    """Handle ``qv launch``.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Process exit code.
    """
    workspace_dir = _resolve_workspace_dir(args.dir)
    result = workspace.init_workspace(workspace_dir)
    if args.json:
        print(
            json.dumps(
                {
                    "workspace_dir": str(result.workspace_dir),
                    "created_files": [str(p) for p in result.created_files],
                    "skipped_files": [str(p) for p in result.skipped_files],
                }
            )
        )
    else:
        print(f"[QV] Workspace initialized: {result.workspace_dir}")
        for path in result.created_files:
            print(f"  + {path.relative_to(result.workspace_dir)}")
        for path in result.skipped_files:
            print(f"  = {path.relative_to(result.workspace_dir)} (already existed, left untouched)")
    return 0


def _cmd_sync_ast(args: argparse.Namespace) -> int:
    """Handle ``qv sync-ast``.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Process exit code.
    """
    workspace_dir = _resolve_workspace_dir(args.dir)
    dossier = parse_dossier(workspace_dir)
    jd_text = Path(args.target).expanduser().read_text(encoding="utf-8")
    job_description = matcher.parse_job_description(jd_text, source=args.target)
    template = _find_template(workspace_dir, args.template)
    result = matcher.run_match(dossier, job_description, template)

    if args.json:
        print(
            json.dumps(
                {
                    "g_force_score": result.g_force_score,
                    "alert_level": result.alert_level.value,
                    "gaps": list(result.gaps),
                    "red_flags": list(result.red_flags),
                    "categories": [
                        {
                            "name": c.name,
                            "weight": c.weight,
                            "coverage": c.coverage,
                            "matched_keywords": list(c.matched_keywords),
                            "gap_keywords": list(c.gap_keywords),
                        }
                        for c in result.category_scores
                    ],
                }
            )
        )
    else:
        print(f"[QV] G-Force Match: {result.g_force_score:.1f}%  ({result.alert_level.value.upper()})")
        for category in result.category_scores:
            print(f"  - {category.name}: {category.coverage * 100:.0f}% coverage (weight {category.weight:.2f})")
        if result.gaps:
            print(f"[QV] Gaps: {', '.join(result.gaps)}")
        if result.red_flags:
            print(f"[QV] RED FLAGS: {'; '.join(result.red_flags)}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Handle ``qv export``.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Process exit code.
    """
    workspace_dir = _resolve_workspace_dir(args.dir)
    dossier = parse_dossier(workspace_dir)

    match_result = None
    if args.target and args.template:
        jd_text = Path(args.target).expanduser().read_text(encoding="utf-8")
        job_description = matcher.parse_job_description(jd_text, source=args.target)
        template = _find_template(workspace_dir, args.template)
        match_result = matcher.run_match(dossier, job_description, template)

    narrative = None
    if args.narrative:
        if match_result is None:
            raise QuestVectorError("--narrative requires both --target and --template to be set")
        passphrase = getpass.getpass("Vault passphrase: ")
        vault_path = workspace_dir / _VAULT_FILENAME
        vault_data = load_vault(vault_path, passphrase)
        generator = AnthropicNarrativeGenerator(vault_data.llm_api_key or "")
        dossier_context = "\n".join(c.text for c in dossier.capabilities[:20])
        prompt = build_narrative_prompt(dossier_context, job_description.raw_text)
        narrative = generator.generate(prompt)

    output_dir = workspace_dir / "bundles"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.bundle}.{args.format}"
    export_bundle(
        dossier, output_path, fmt=args.format, match_result=match_result, narrative=narrative
    )
    print(f"[QV] Exported bundle: {output_path}")
    return 0


def _cmd_template_validate(args: argparse.Namespace) -> int:
    """Handle ``qv template validate``.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Process exit code: ``0`` if valid (or fixed), ``1`` if invalid and
        ``--fix`` was not requested.
    """
    result = templates.validate_template_file(Path(args.path), fix=args.fix)
    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        status = "VALID" if result.valid else "INVALID"
        print(f"[QV] Template '{result.template_id}': {status} (weight sum {result.weight_sum:.4f})")
        for issue in result.issues:
            print(f"  - {issue}")
    return 0 if result.valid else 1


def _cmd_vault_set_key(args: argparse.Namespace) -> int:
    """Handle ``qv vault set-key``.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Process exit code.
    """
    workspace_dir = _resolve_workspace_dir(args.dir)
    vault_path = workspace_dir / _VAULT_FILENAME
    passphrase = getpass.getpass("Vault passphrase: ")
    api_key = getpass.getpass("LLM API key: ")

    def _set_key(data: VaultData) -> None:
        data.llm_api_key = api_key

    update_vault(vault_path, passphrase, _set_key)
    print(f"[QV] LLM API key stored in encrypted vault: {vault_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``qv`` argument parser.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(prog="qv", description="QuestVector career navigation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch = subparsers.add_parser("launch", help="Initialize a local career dossier workspace")
    launch.add_argument("--dir", help="Workspace directory (default: current directory)")
    launch.add_argument("--json", action="store_true", help="Emit JSON output")
    launch.set_defaults(func=_cmd_launch)

    sync_ast = subparsers.add_parser("sync-ast", help="Score a job description against the dossier")
    sync_ast.add_argument("--target", required=True, help="Path to the job description text file")
    sync_ast.add_argument("--template", required=True, help="Mission template id to score against")
    sync_ast.add_argument("--dir", help="Workspace directory (default: current directory)")
    sync_ast.add_argument("--json", action="store_true", help="Emit JSON output")
    sync_ast.set_defaults(func=_cmd_sync_ast)

    export = subparsers.add_parser("export", help="Compile the dossier into a PDF or DOCX bundle")
    export.add_argument("--bundle", required=True, help="Output bundle name (without extension)")
    export.add_argument("--format", required=True, choices=("pdf", "docx"), help="Export format")
    export.add_argument("--dir", help="Workspace directory (default: current directory)")
    export.add_argument("--target", help="Optional job description file to include a match summary for")
    export.add_argument("--template", help="Mission template id (required if --target is given)")
    export.add_argument(
        "--narrative", action="store_true", help="Generate an LLM narrative summary (requires vault + --target/--template)"
    )
    export.set_defaults(func=_cmd_export)

    template = subparsers.add_parser("template", help="Mission template operations")
    template_subparsers = template.add_subparsers(dest="template_command", required=True)
    validate = template_subparsers.add_parser("validate", help="Lint a mission template YAML file")
    validate.add_argument("path", help="Path to the mission template YAML file")
    validate.add_argument("--fix", action="store_true", help="Auto-rescale weights to sum to 1.00")
    validate.add_argument("--json", action="store_true", help="Emit JSON output")
    validate.set_defaults(func=_cmd_template_validate)

    vault = subparsers.add_parser("vault", help="Encrypted local vault operations")
    vault_subparsers = vault.add_subparsers(dest="vault_command", required=True)
    set_key = vault_subparsers.add_parser("set-key", help="Store an LLM API key in the encrypted vault")
    set_key.add_argument("--dir", help="Workspace directory (default: current directory)")
    set_key.set_defaults(func=_cmd_vault_set_key)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list (excluding the program name); defaults to
            ``sys.argv[1:]`` when ``None``.

    Returns:
        The process exit code: ``0`` on success, ``1`` on a handled
        :class:`QuestVectorError`, ``2`` on an unexpected error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except QuestVectorError as exc:
        print(f"[QV] ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[QV] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
