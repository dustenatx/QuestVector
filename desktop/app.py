"""pywebview desktop shell entry point and JS/Python bridge.

The :class:`Api` class is exposed to the front-end JavaScript
(``questvector/desktop/web/app.js``) via ``pywebview``'s ``js_api``
mechanism. Every method returns a plain, JSON-serializable dict shaped as
either ``{"ok": True, "data": ...}`` or ``{"ok": False, "error": "..."}`` —
deliberately never letting a :class:`~questvector.exceptions.QuestVectorError`
propagate as an unhandled JS-side exception, so the UI can always render a
clean error state (Lock-On Red) instead of a broken promise.

``Api`` methods are plain, dependency-injectable Python and are exercised
directly in tests without ever creating a real window — no display server,
GUI toolkit, or pywebview runtime is required to test the bridge logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from questvector.core import matcher, templates, workspace
from questvector.core.exporter import export_bundle as _export_bundle
from questvector.core.llm import AnthropicNarrativeGenerator, build_narrative_prompt
from questvector.core.markdown_parser import parse_dossier
from questvector.core.vault import VaultData, load_vault, update_vault
from questvector.exceptions import QuestVectorError

_VAULT_FILENAME = ".questvector.vault"


def _ok(data: Any = None) -> dict[str, Any]:
    """Build a successful bridge response.

    Args:
        data: The JSON-serializable payload to return to the front-end.

    Returns:
        ``{"ok": True, "data": data}``.
    """
    return {"ok": True, "data": data}


def _err(exc: Exception) -> dict[str, Any]:
    """Build a failed bridge response from an exception.

    Args:
        exc: The exception raised while handling the request.

    Returns:
        ``{"ok": False, "error": "<message>"}``.
    """
    return {"ok": False, "error": str(exc)}


class Api:
    """JS-callable bridge exposing QuestVector's core engine to the UI."""

    def launch_workspace(self, dir_path: str) -> dict[str, Any]:
        """Initialize a workspace directory (``qv launch`` equivalent).

        Args:
            dir_path: Absolute path to the workspace directory.

        Returns:
            A bridge response wrapping a
            :class:`~questvector.core.workspace.WorkspaceInitResult` summary.
        """
        try:
            result = workspace.init_workspace(Path(dir_path))
            return _ok(
                {
                    "workspace_dir": str(result.workspace_dir),
                    "created_files": [str(p) for p in result.created_files],
                    "skipped_files": [str(p) for p in result.skipped_files],
                }
            )
        except QuestVectorError as exc:
            return _err(exc)

    def get_dossier(self, dir_path: str) -> dict[str, Any]:
        """Parse and return the workspace's dossier.

        Args:
            dir_path: Absolute path to the workspace directory.

        Returns:
            A bridge response wrapping the parsed dossier's capabilities,
            chronology, and impact sections.
        """
        try:
            dossier = parse_dossier(Path(dir_path))
            return _ok(
                {
                    "capabilities": [
                        {"domain": c.domain, "text": c.text} for c in dossier.capabilities
                    ],
                    "chronology": [
                        {"heading": e.heading, "bullets": list(e.bullets)} for e in dossier.chronology
                    ],
                    "impact": [
                        {"heading": s.heading, "bullets": list(s.bullets)} for s in dossier.impact
                    ],
                }
            )
        except QuestVectorError as exc:
            return _err(exc)

    def list_templates(self, dir_path: str) -> dict[str, Any]:
        """List mission templates available in a workspace.

        Args:
            dir_path: Absolute path to the workspace directory.

        Returns:
            A bridge response wrapping a list of ``{id, title, weight_sum}``
            entries found under ``templates/`` and ``templates/starter/``.
        """
        try:
            workspace_dir = Path(dir_path)
            found: list[dict[str, Any]] = []
            for directory in (workspace_dir / "templates" / "starter", workspace_dir / "templates"):
                if not directory.is_dir():
                    continue
                for path in sorted(directory.glob("*.y*ml")):
                    template = templates.load_template(path)
                    found.append(
                        {
                            "id": template.template_id,
                            "title": template.title,
                            "weight_sum": template.weight_sum(),
                            "path": str(path),
                        }
                    )
            return _ok(found)
        except QuestVectorError as exc:
            return _err(exc)

    def sync_ast(self, dir_path: str, jd_text: str, template_id: str) -> dict[str, Any]:
        """Run the Micro-Diff Matching Engine (``qv sync-ast`` equivalent).

        Args:
            dir_path: Absolute path to the workspace directory.
            jd_text: Raw job description text pasted/loaded in the UI.
            template_id: The mission template id to score against.

        Returns:
            A bridge response wrapping the G-Force match result.
        """
        try:
            workspace_dir = Path(dir_path)
            dossier = parse_dossier(workspace_dir)
            job_description = matcher.parse_job_description(jd_text, source="ui-paste")
            template = self._load_template_by_id(workspace_dir, template_id)
            result = matcher.run_match(dossier, job_description, template)
            return _ok(
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
        except QuestVectorError as exc:
            return _err(exc)

    def validate_template(self, path: str, fix: bool) -> dict[str, Any]:
        """Validate (and optionally fix) a mission template file.

        Args:
            path: Absolute path to the mission template YAML file.
            fix: Whether to auto-rescale out-of-tolerance weights.

        Returns:
            A bridge response wrapping a
            :class:`~questvector.core.templates.TemplateValidationResult`.
        """
        try:
            result = templates.validate_template_file(Path(path), fix=fix)
            return _ok(result.to_dict())
        except QuestVectorError as exc:
            return _err(exc)

    def export_bundle(
        self,
        dir_path: str,
        bundle_name: str,
        fmt: str,
        jd_text: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        """Export the dossier bundle to PDF/DOCX (``qv export`` equivalent).

        Args:
            dir_path: Absolute path to the workspace directory.
            bundle_name: Output file name, without extension.
            fmt: ``"pdf"`` or ``"docx"``.
            jd_text: Optional job description text to include a match
                summary for.
            template_id: Mission template id (required if ``jd_text`` is
                given).

        Returns:
            A bridge response wrapping the written bundle's path.
        """
        try:
            workspace_dir = Path(dir_path)
            dossier = parse_dossier(workspace_dir)
            match_result = None
            if jd_text and template_id:
                job_description = matcher.parse_job_description(jd_text, source="ui-paste")
                template = self._load_template_by_id(workspace_dir, template_id)
                match_result = matcher.run_match(dossier, job_description, template)

            output_dir = workspace_dir / "bundles"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{bundle_name}.{fmt}"
            _export_bundle(dossier, output_path, fmt=fmt, match_result=match_result)  # type: ignore[arg-type]
            return _ok({"output_path": str(output_path)})
        except QuestVectorError as exc:
            return _err(exc)

    def generate_narrative(
        self, dir_path: str, jd_text: str, passphrase: str
    ) -> dict[str, Any]:
        """Generate an LLM narrative summary for the current dossier + JD.

        This is an explicit, user-triggered UI action rather than an
        automatic background call, since invoking it makes an outbound
        network request to the configured LLM provider (see
        :mod:`questvector.core.llm` for why that is a deliberate,
        documented departure from the spec's "Zero-Cloud" claim).

        Args:
            dir_path: Absolute path to the workspace directory.
            jd_text: Raw job description text.
            passphrase: The vault passphrase, entered by the user in the UI
                (never persisted).

        Returns:
            A bridge response wrapping the generated narrative text.
        """
        try:
            workspace_dir = Path(dir_path)
            dossier = parse_dossier(workspace_dir)
            vault_path = workspace_dir / _VAULT_FILENAME
            vault_data = load_vault(vault_path, passphrase)
            generator = AnthropicNarrativeGenerator(vault_data.llm_api_key or "")
            dossier_context = "\n".join(c.text for c in dossier.capabilities[:20])
            prompt = build_narrative_prompt(dossier_context, jd_text)
            narrative = generator.generate(prompt)
            return _ok({"narrative": narrative})
        except QuestVectorError as exc:
            return _err(exc)

    def set_llm_key(self, dir_path: str, passphrase: str, api_key: str) -> dict[str, Any]:
        """Store an LLM API key in the workspace's encrypted vault.

        Args:
            dir_path: Absolute path to the workspace directory.
            passphrase: The vault passphrase (used to derive the
                encryption key — never stored itself).
            api_key: The LLM provider API key to encrypt and persist.

        Returns:
            A bridge response indicating success.
        """
        try:
            vault_path = Path(dir_path) / _VAULT_FILENAME

            def _set_key(data: VaultData) -> None:
                data.llm_api_key = api_key

            update_vault(vault_path, passphrase, _set_key)
            return _ok({"vault_path": str(vault_path)})
        except QuestVectorError as exc:
            return _err(exc)

    @staticmethod
    def _load_template_by_id(workspace_dir: Path, template_id: str):  # noqa: ANN205
        """Load a mission template by id, searching the workspace's template dirs.

        Args:
            workspace_dir: The workspace directory to search.
            template_id: The template's ``id`` (filename stem).

        Returns:
            The loaded :class:`~questvector.core.models.MissionTemplate`.

        Raises:
            QuestVectorError: If no matching template file is found.
        """
        for directory in (workspace_dir / "templates" / "starter", workspace_dir / "templates"):
            for extension in (".yaml", ".yml"):
                candidate = directory / f"{template_id}{extension}"
                if candidate.exists():
                    return templates.load_template(candidate)
        raise QuestVectorError(f"No mission template found with id '{template_id}'")


def run() -> None:  # pragma: no cover - requires a real display/GUI runtime
    """Launch the QuestVector desktop window.

    Creates a pywebview window hosting ``questvector/desktop/web/index.html``
    with an :class:`Api` instance bridged in as ``window.pywebview.api``.
    Not exercised by the automated test suite, since it requires a real
    display server / native GUI runtime; the bridge logic it depends on
    (:class:`Api`) is fully covered independently.
    """
    import webview  # Imported lazily so headless test/CI environments never
    # need the native GUI runtime installed just to import this module.

    web_dir = Path(__file__).parent / "web"
    api = Api()
    webview.create_window(
        "QuestVector — Tactical Flight Deck",
        url=str(web_dir / "index.html"),
        js_api=api,
        width=1280,
        height=860,
        min_size=(960, 640),
        background_color="#0b0f19",
    )
    webview.start()


if __name__ == "__main__":  # pragma: no cover
    run()
