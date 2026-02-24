#!/usr/bin/env python3
"""NotebookLM Playwright video workflow automation.

This script automates the NotebookLM website flow for video generation:
1. Open/create a notebook
2. Add video heading as a source
3. Create a studio note with instructions
4. Add the note as a source
5. Click Video Overview
6. Select Custom Visual Style
7. Add additional notes and start generation

Notes:
- Uses a persistent Playwright profile so login only needs to happen once.
- NotebookLM UI changes often, so selectors are intentionally flexible.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from playwright.async_api import (
    BrowserContext,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

HOME_URL = "https://notebooklm.google.com/"
DEFAULT_PROFILE_DIR = Path.home() / ".notebooklm_playwright_profile"
DEFAULT_CUSTOM_VISUAL_STYLE = (
    "Photorealistic, documentary-style video featuring ONE real person speaking directly to camera. "
    "The speaker and setting should match the topic (job site, kitchen, classroom, clinic, office, home). "
    "Natural lighting, realistic shadows, shallow depth of field. Authentic wardrobe and props appropriate "
    "to the role. Diverse and realistic casting. Minimal motion graphics. On-screen text should be short "
    "(3-6 words), bold, high-contrast, with simple icons. No animation, no cartoon/anime, no illustrated look."
)
DEFAULT_HOST_FOCUS_NOTES = (
    "Create a 2-minute script (about 260-320 spoken words) delivered by ONE speaker talking directly to the viewer "
    "(no co-hosts, no dialogue). Choose a speaker role that fits the topic and audience.\n\n"
    "Topic: same as title\n"
    "Purpose: give practical takeaways the viewer can use today.\n\n"
    "Structure:\n"
    "1) Hook (1-2 sentences, get to the point)\n"
    "2) Three key points (short, actionable, minimal jargon)\n"
    "3) Quick example line or mini-scenario (what the viewer can say/do)\n"
    "4) One-sentence recap\n"
    '5) End with this exact line: "Come back to ok.ai for more videos on saving money and supporting your family."\n\n'
    "Keep the language respectful, motivating, and blame-free. Don't over-explain technical terms. "
    "Include 2-4 quick b-roll suggestions that match the setting and topic. Also provide minimal on-screen "
    "text prompts that match the three key points (3-6 words each)."
)
FAST_RESEARCH_TIMEOUT_S = 45
POST_IMPORT_TIMEOUT_S = 45


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("notebooklm.playwright")


@dataclass
class WorkflowConfig:
    video_title: str
    studio_note: str
    additional_notes: str = ""
    custom_visual_style: str = DEFAULT_CUSTOM_VISUAL_STYLE
    host_focus_notes: str = DEFAULT_HOST_FOCUS_NOTES
    research_query: str = ""
    notebook_id: Optional[str] = None
    notebook_name: Optional[str] = None
    force_new_notebook: bool = False
    start_url: Optional[str] = None
    profile_dir: Path = DEFAULT_PROFILE_DIR
    timeout_ms: int = 25_000
    manual_login_timeout_s: int = 180
    slow_mo_ms: int = 60
    headless: bool = False
    keep_open_seconds: int = 8
    debug_dir: Optional[Path] = None
    enable_api_fallback: bool = True
    api_storage_path: Optional[Path] = None
    enable_fast_research: bool = True
    refresh_before_video_overview: bool = True
    close_popups_on_start: bool = True
    output_json: Optional[str] = None


@dataclass
class WorkflowResult:
    status: str = "pending"
    notebook_url: Optional[str] = None
    steps_completed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class NotebookLMPlaywrightWorkflow:
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.modifier_key = "Meta" if platform.system() == "Darwin" else "Control"
        self._force_api_video_generation = False
        self._notebook_url: Optional[str] = None  # Saved notebook URL to navigate back if needed

    async def run(self) -> WorkflowResult:
        result = WorkflowResult()
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_dir),
                headless=self.config.headless,
                slow_mo=self.config.slow_mo_ms,
                viewport={"width": 1600, "height": 1000},
            )
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            self.page.set_default_timeout(self.config.timeout_ms)
            self.page.set_default_navigation_timeout(self.config.timeout_ms)

            try:
                await self._open_or_create_notebook(result)
                if self.config.close_popups_on_start:
                    await self._close_popups(result, step_label="Closed startup popups")
                    await self._ensure_on_notebook()
                if self.config.enable_fast_research:
                    await self._run_fast_research_and_import(result)
                await self._ensure_on_notebook()
                await self._add_video_title_as_source(result)
                await self._ensure_on_notebook()
                await self._create_studio_note(result)
                await self._add_note_as_source(result)
                await self._ensure_on_notebook()
                if self.config.refresh_before_video_overview:
                    await self._refresh_before_video_overview(result)
                await self._ensure_on_notebook()
                await self._open_video_overview(result)
                await self._select_custom_visual_style(result)
                await self._fill_additional_notes_and_generate(result)

                if result.errors:
                    result.status = "partial"
                else:
                    result.status = "success"

                if result.errors:
                    await self._capture_debug_artifacts("run_with_errors")

                if self.config.keep_open_seconds > 0:
                    logger.info(
                        "Keeping browser open for %ss so you can verify the UI state...",
                        self.config.keep_open_seconds,
                    )
                    await asyncio.sleep(self.config.keep_open_seconds)
            except Exception as exc:
                result.status = "error"
                result.errors.append(str(exc))
            finally:
                # Preserve the notebook URL we saved earlier, don't overwrite with current page
                # (which might be the homepage if we drifted)
                if not result.notebook_url:
                    result.notebook_url = self.page.url if self.page else None
                if self.context:
                    await self.context.close()

        return result

    async def wait_for_manual_login(self) -> str:
        """Open NotebookLM and wait for manual login in persistent profile."""
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_dir),
                headless=False,
                slow_mo=0,
                viewport={"width": 1400, "height": 920},
            )
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            self.page.set_default_timeout(self.config.timeout_ms)

            try:
                await self.page.goto(HOME_URL, wait_until="domcontentloaded")
                await self._wait_until_logged_in(self.config.manual_login_timeout_s)
                return self.page.url
            finally:
                if self.context:
                    await self.context.close()

    async def _refresh_before_video_overview(self, result: WorkflowResult) -> None:
        assert self.page is not None
        try:
            logger.info("Refreshing page before Video Overview...")
            await self.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(1.0)
            await self._close_popups(result, step_label="Closed popups after refresh")
            result.steps_completed.append("Refreshed notebook tab before Video Overview")
        except Exception as exc:
            logger.warning("Page refresh failed (continuing): %s", exc)
            # If target closed, we can't continue, but let the main loop handle the error
            if "Target page, context or browser has been closed" in str(exc):
                raise
        finally:
            self._save_progress(result)

    def _save_progress(self, result: WorkflowResult) -> None:
        if not self.config.output_json:
            return
        
        # Update result status tentatively
        current_status = result.status
        if not result.errors:
            result.status = "in_progress"
            
        try:
            output_path = Path(self.config.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save progress: %s", exc)
        finally:
            result.status = current_status

    async def _open_or_create_notebook(self, result: WorkflowResult) -> None:
        assert self.page is not None
        logger.info("STEP: Opening or creating notebook...")

        target_url, api_step = await self._resolve_notebook_target()
        if api_step:
            result.steps_completed.append(api_step)

        target_url = target_url or HOME_URL
        await self.page.goto(target_url, wait_until="domcontentloaded")
        await self._wait_until_logged_in(self.config.manual_login_timeout_s)

        if "/notebook/" in self.page.url:
            result.steps_completed.append("Opened existing notebook URL")
            result.notebook_url = self.page.url
            self._notebook_url = self.page.url
            logger.info("Notebook URL: %s", self._notebook_url)
            self._save_progress(result)
            return

        created = await self._click_labels(
            [
                "Create",
                "Create new",
                "New notebook",
                "New Notebook",
                "Create notebook",
            ],
            required=False,
        )

        if created:
            await self._wait_for_notebook_url(timeout_s=45)
            result.steps_completed.append("Created new notebook")
            result.notebook_url = self.page.url
            self._notebook_url = self.page.url
            logger.info("Notebook URL: %s", self._notebook_url)
            self._save_progress(result)
            return

        if "/notebook/" in self.page.url:
            result.steps_completed.append("Notebook already open")
            result.notebook_url = self.page.url
            self._notebook_url = self.page.url
            logger.info("Notebook URL: %s", self._notebook_url)
            self._save_progress(result)
            return

        raise RuntimeError("Could not open or create a notebook in NotebookLM UI")

    async def _resolve_notebook_target(self) -> tuple[Optional[str], Optional[str]]:
        if self.config.start_url:
            return self.config.start_url, None

        if not self.config.enable_api_fallback:
            return None, None

        try:
            from notebooklm import NotebookLMClient
        except Exception as exc:
            logger.warning("Notebook target resolution skipped; notebooklm-py unavailable: %s", exc)
            return None, None

        storage_path = str(self.config.api_storage_path) if self.config.api_storage_path else None

        try:
            async with await NotebookLMClient.from_storage(path=storage_path) as client:
                if self.config.force_new_notebook:
                    new_name = self._build_new_notebook_name()
                    notebook = await client.notebooks.create(new_name)
                    return self._build_notebook_url(notebook.id), "Created new notebook via API"

                if self.config.notebook_id:
                    notebook = await client.notebooks.get(self.config.notebook_id)
                    if notebook and notebook.id:
                        return self._build_notebook_url(notebook.id), "Resolved notebook by ID via API"

                if self.config.notebook_name:
                    notebooks = await client.notebooks.list()
                    target_name = self.config.notebook_name.strip().lower()
                    for notebook in notebooks:
                        if notebook.title.strip().lower() == target_name:
                            return self._build_notebook_url(notebook.id), "Resolved notebook by name via API"

                    notebook = await client.notebooks.create(self.config.notebook_name.strip())
                    return self._build_notebook_url(notebook.id), "Created notebook via API"
        except Exception as exc:
            logger.warning("Notebook target resolution via API failed: %s", exc)
            return None, None

        return None, None

    async def _add_video_title_as_source(self, result: WorkflowResult) -> None:
        assert self.page is not None

        # If `?addSource=true` is present, the source modal might already be open.
        if not await self._fill_source_text_input(self.config.video_title):
            clicked_add_source = await self._click_labels(
                ["Add source", "Add Source", "Sources", "Add"],
                required=False,
            )
            if not clicked_add_source:
                raise RuntimeError("Could not find Add source entry point")

            await asyncio.sleep(0.8)
            await self._click_labels(
                ["Copied text", "Paste text", "Text", "Text source"],
                required=False,
            )

            if not await self._fill_source_text_input(self.config.video_title):
                raise RuntimeError("Could not find source text input for video title")

        submitted = await self._click_labels(
            ["Insert", "Add source", "Add", "Save", "Done"],
            required=False,
        )
        if not submitted:
            await self.page.keyboard.press(f"{self.modifier_key}+Enter")

        await asyncio.sleep(1.2)
        result.steps_completed.append("Added video title as source")

    async def _create_studio_note(self, result: WorkflowResult) -> None:
        assert self.page is not None
        logger.info("STEP: Creating studio note...")
        await self._ensure_on_notebook()
        await self._close_popups(result, step_label="Closed popups before studio note")
        await self._ensure_on_notebook()

        # Click the "Add note" button specifically in the Studio panel (bottom-right).
        # IMPORTANT: Do NOT click generic "Create" which matches "Create notebook" in the navbar!
        add_note_btn = self.page.get_by_role("button", name=re.compile(r"add note", re.IGNORECASE)).first
        if await self._is_visible(add_note_btn, timeout_ms=2000):
            logger.info("Found 'Add note' button, clicking...")
            await add_note_btn.click()
            await asyncio.sleep(0.5)
        else:
            logger.info("'Add note' button not found, trying alternative labels...")
            # Only use safe labels that won't match "Create notebook"
            await self._click_labels(
                ["Add note", "New note", "Create note"],
                required=False,
            )
            await asyncio.sleep(0.5)

        filled = await self._fill_first_visible(
            [
                "textarea",
                "[contenteditable='true'][role='textbox']",
                "div[contenteditable='true']",
            ],
            self.config.studio_note,
        )
        if not filled:
            logger.info("Note editor not found on first try, retrying...")
            await self._capture_debug_artifacts("studio_note_editor_missing")
            # Try pressing Escape to dismiss any overlays, then retry
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            await self._ensure_on_notebook()
            
            # Try clicking Add note again
            add_note_btn = self.page.get_by_role("button", name=re.compile(r"add note", re.IGNORECASE)).first
            if await self._is_visible(add_note_btn, timeout_ms=2000):
                await add_note_btn.click()
                await asyncio.sleep(0.5)
            
            filled = await self._fill_first_visible(
                [
                    "textarea",
                    "[contenteditable='true'][role='textbox']",
                    "div[contenteditable='true']",
                ],
                self.config.studio_note,
            )
            
        if not filled:
            await self._capture_debug_artifacts("studio_note_still_missing")
            raise RuntimeError("Could not find note editor in Studio panel")

        logger.info("Filled note editor, saving...")
        saved = await self._click_labels(["Save", "Done"], required=False)
        if not saved:
            await self._save_with_shortcut()

        await asyncio.sleep(1.0)
        result.steps_completed.append("Created studio note")

    async def _ensure_on_notebook(self) -> None:
        """Verify we are still on the notebook page. Navigate back if we drifted."""
        assert self.page is not None
        if not self._notebook_url:
            return
        
        current_url = self.page.url
        # Check if we're still on the notebook page (URL contains /notebook/)
        if "/notebook/" not in current_url:
            logger.warning("Drifted away from notebook! Current URL: %s. Navigating back to %s",
                          current_url, self._notebook_url)
            await self.page.goto(self._notebook_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

    async def _add_note_as_source(self, result: WorkflowResult) -> None:
        assert self.page is not None

        direct_action = await self._click_labels(
            ["Add to sources", "Use as source", "Add as source"],
            required=False,
        )
        if direct_action:
            result.steps_completed.append("Added note as source")
            await asyncio.sleep(1.0)
            return

        snippet = " ".join(self.config.studio_note.split())[:32]
        if snippet:
            candidate = self.page.get_by_text(re.compile(re.escape(snippet), re.IGNORECASE)).first
            if await self._is_visible(candidate, timeout_ms=1500):
                await candidate.click(button="right")
                await asyncio.sleep(0.4)
                context_action = await self._click_labels(
                    ["Add to sources", "Use as source", "Add as source"],
                    required=False,
                )
                if context_action:
                    result.steps_completed.append("Added note as source")
                    await asyncio.sleep(1.0)
                    return

        # Fallback: add the note content as a text source if note->source UI action
        # is unavailable in this NotebookLM build.
        fallback_added = await self._add_text_source(self.config.studio_note)
        if fallback_added:
            result.steps_completed.append("Added studio note content as source (fallback)")
            return

        if self.config.enable_api_fallback:
            api_added, api_error = await self._add_note_source_via_api()
            if api_added:
                result.steps_completed.append("Added studio note content as source (API fallback)")
                return
            if api_error:
                logger.warning("API fallback for note source failed: %s", api_error)

        await self._capture_debug_artifacts("missing_note_source_action")
        result.errors.append("Could not find a UI action to add the note as a source")



    async def _open_video_overview(self, result: WorkflowResult) -> None:
        logger.info("STEP: Opening Video Overview...")
        assert self.page is not None
        await self._ensure_on_notebook()

        ready = await self._wait_for_any_label(
            ["Video Overview", "Video overview"],
            timeout_s=POST_IMPORT_TIMEOUT_S,
            initial_delay_s=2.0,
        )
        if not ready:
            logger.info("Video Overview not visible, taking debug screenshot...")
            await self._capture_debug_artifacts("video_overview_not_ready")
            raise RuntimeError("Video Overview button not found after waiting.")

        # Click the Video Overview card in the Studio panel
        opened = await self._click_labels(
            ["Video Overview", "Video overview"],
            required=False,
        )
        if not opened:
            raise RuntimeError("Could not click Video Overview")

        logger.info("Clicked Video Overview successfully.")
        await asyncio.sleep(1.2)
        result.steps_completed.append("Opened Video Overview")

    async def _select_custom_visual_style(self, result: WorkflowResult) -> None:
        selected = await self._click_labels(
            [
                "Custom Visual Style",
                "Custom visual style",
                "Custom style",
                "Custom",
            ],
            required=False,
        )
        if not selected:
            selected = await self._select_custom_style_fallback()
            if not selected:
                if self.config.enable_api_fallback:
                    self._force_api_video_generation = True
                    result.steps_completed.append(
                        "Custom Visual Style UI unavailable; will start generation via API CUSTOM style fallback"
                    )
                else:
                    await self._capture_debug_artifacts("missing_custom_visual_style")
                    result.errors.append("Could not explicitly select Custom Visual Style")
                return

        await asyncio.sleep(0.6)
        result.steps_completed.append("Selected Custom Visual Style")

    async def _fill_additional_notes_and_generate(self, result: WorkflowResult) -> None:
        assert self.page is not None

        # Removed aggressive popup closing here to avoid closing the Video Overview itself.
        # await self._close_popups(result, step_label="Closed popups in Video Overview")

        if self._force_api_video_generation:
            if self.config.host_focus_notes.strip():
                result.steps_completed.append("Prepared host focus notes for API generation")
            started, api_error = await self._start_video_generation_via_api()
            if started:
                result.steps_completed.append("Started video generation (API fallback)")
                return
            if api_error:
                result.errors.append(f"API fallback video generation failed: {api_error}")

        style_filled = await self._fill_video_field(
            labels=[
                "Describe a Custom visual style",
                "Describe a custom visual style",
                "Custom visual style",
                "Visual style",
            ],
            value=self.config.custom_visual_style,
        )
        if style_filled:
            result.steps_completed.append("Filled custom visual style description")
        else:
            result.errors.append("Could not fill custom visual style description")

        focus_filled = await self._fill_video_field(
            labels=[
                "What should the AI hosts focus on?",
                "What should the AI hosts focus on",
                "AI hosts focus",
                "hosts focus",
            ],
            value=self.config.host_focus_notes,
        )
        if focus_filled:
            result.steps_completed.append("Filled AI host focus guidance")
        else:
            result.errors.append("Could not fill AI host focus guidance")

        started = await self._click_labels(
            [
                "Generate",
                "Generate video",
                "Create video",
                "Start",
            ],
            required=False,
        )
        if not started:
            if self.config.enable_api_fallback:
                started, api_error = await self._start_video_generation_via_api()
                if started:
                    result.steps_completed.append("Started video generation (API fallback after missing Generate button)")
                    return
                if api_error:
                    result.errors.append(f"API fallback video generation failed: {api_error}")
            raise RuntimeError("Could not find Generate button")

        await asyncio.sleep(1.0)
        result.steps_completed.append("Started video generation")

    async def _run_fast_research_and_import(self, result: WorkflowResult) -> None:
        assert self.page is not None

        await self._click_labels(["Sources", "Source"], required=False)
        await asyncio.sleep(0.5)
        result.steps_completed.append("Opened Sources panel (Fast Research assumed default)")

        query = self.config.research_query.strip() or self._default_research_query()
        query_filled = await self._fill_first_visible(
            [
                "textarea[aria-label*='title' i]",
                "input[aria-label*='title' i]",
                "textarea[placeholder*='title' i]",
                "input[placeholder*='title' i]",
                "textarea[aria-label*='research' i]",
                "input[aria-label*='research' i]",
                "textarea[placeholder*='research' i]",
                "input[placeholder*='research' i]",
                "[role='textbox'][aria-label*='research' i]",
                "textarea",
                "input[type='text']",
            ],
            query,
        )
        if not query_filled:
            result.errors.append("Could not find Fast Research query input")
            return

        next_clicked = await self._click_labels(
            ["Next", "Continue", "Proceed"],
            required=False,
        )

        if not next_clicked:
            # Try to find a right arrow button (icon-only button) as requested by user
            try:
                arrow_candidates = [
                    self.page.locator("button:has(i:text-is('arrow_forward'))").first,
                    self.page.locator("button:has(span:text-is('arrow_forward'))").first,
                    self.page.locator("button:has(i:text-is('arrow_right'))").first,
                    self.page.locator("button:has(span:text-is('arrow_right'))").first,
                    self.page.locator("button[aria-label*='next' i]").first,
                    self.page.locator("button[aria-label*='submit' i]").first,
                    self.page.locator("button[aria-label*='continue' i]").first,
                    self.page.locator("button[aria-label*='send' i]").first,
                    # Fallback for generic icon button near the input if possible
                    self.page.locator("button.mat-mdc-icon-button").last, 
                ]
                for btn in arrow_candidates:
                    if await self._is_visible(btn, timeout_ms=800):
                        await btn.click()
                        next_clicked = True
                        break
            except Exception:
                pass

        if next_clicked:
            result.steps_completed.append("Entered title and clicked Next")
        else:
            started = await self._click_labels(
                [
                    "Find sources",
                    "Find Sources",
                    "Search",
                    "Research",
                    "Discover",
                ],
                required=False,
            )
            if not started:
                await self.page.keyboard.press("Enter")

        result.steps_completed.append("Started Fast Research")

        # NotebookLM can take a while to finish source discovery. Wait up to 45s.
        import_ready = await self._wait_for_any_label(
            [
                "Import",
                "Import selected",
                "Import resources",
                "Add selected",
                "Add all",
            ],
            timeout_s=FAST_RESEARCH_TIMEOUT_S,
            initial_delay_s=3.0,
        )
        if not import_ready:
            await self._capture_debug_artifacts("fast_research_import_timeout")
            result.errors.append("Fast Research did not finish within 45s")
            return

        select_all_clicked = await self._click_labels(
            ["Select all", "Select All", "All"],
            required=False,
        )
        if not select_all_clicked:
            select_all_clicked = await self._select_all_checkboxes()

        # Some accounts show a one-time permission/allow gate before import.
        await self._click_labels(
            ["Allow", "Allow access", "Continue"],
            required=False,
        )

        import_clicked = await self._click_labels(
            [
                "Import resources",
                "Import selected",
                "Import",
                "Add selected",
                "Add all",
            ],
            required=False,
        )
        if not import_clicked:
            await asyncio.sleep(1.0)
            import_clicked = await self._click_labels(
                [
                    "Import resources",
                    "Import selected",
                    "Import",
                    "Add selected",
                    "Add all",
                ],
                required=False,
            )

        if import_clicked:
            if select_all_clicked:
                logger.info("Imported all Fast Research resources")
                result.steps_completed.append("Imported all Fast Research resources")
            else:
                logger.info("Imported Fast Research resources")
                result.steps_completed.append("Imported Fast Research resources")
            
            logger.info("Waiting for resources to load (up to %ds)...", POST_IMPORT_TIMEOUT_S)
            resources_ready = await self._wait_for_any_label(
                ["Video Overview", "Video overview"],
                timeout_s=POST_IMPORT_TIMEOUT_S,
                initial_delay_s=5.0,
            )
            if resources_ready:
                logger.info("Resources loaded successfully.")
                result.steps_completed.append("Resources loaded after import")
                
                # Close persistent popups like "Create audio and video overviews"
                await asyncio.sleep(1.5)
                await self._close_popups(result, step_label="Closed post-import popups")
                await self._ensure_on_notebook()

            else:
                logger.warning("Timed out waiting for resources to load.")
                await self._capture_debug_artifacts("resources_not_ready_after_import")
                result.errors.append("Timed out waiting 45s for resources to load after import")
        else:
            logger.warning("Import button was not clicked.")
            await self._capture_debug_artifacts("missing_import_after_fast_research")
            result.errors.append("Research results found but Import action was not clicked")

    async def _add_note_source_via_api(self) -> tuple[bool, str]:
        notebook_id = self._extract_notebook_id()
        if not notebook_id:
            return False, "Notebook ID could not be derived from current URL"

        try:
            from notebooklm import NotebookLMClient
        except Exception as exc:
            return False, f"notebooklm-py unavailable: {exc}"

        storage_path = (
            str(self.config.api_storage_path)
            if self.config.api_storage_path
            else None
        )

        try:
            async with await NotebookLMClient.from_storage(path=storage_path) as client:
                source_title = f"Studio note - {self.config.video_title}".strip()
                await client.sources.add_text(
                    notebook_id,
                    source_title[:120],
                    self.config.studio_note,
                    wait=True,
                )
            return True, ""
        except Exception as exc:
            return False, str(exc)

    async def _start_video_generation_via_api(self) -> tuple[bool, str]:
        notebook_id = self._extract_notebook_id()
        if not notebook_id:
            return False, "Notebook ID could not be derived from current URL"

        instructions_parts = [
            f"Custom visual style: {self.config.custom_visual_style.strip()}".strip(),
            self.config.host_focus_notes.strip(),
            self.config.studio_note.strip(),
        ]
        instructions = "\n\n".join([part for part in instructions_parts if part])
        if not instructions:
            instructions = None

        try:
            from notebooklm import NotebookLMClient
            from notebooklm.types import VideoStyle
        except Exception as exc:
            return False, f"notebooklm-py unavailable: {exc}"

        storage_path = (
            str(self.config.api_storage_path)
            if self.config.api_storage_path
            else None
        )

        try:
            async with await NotebookLMClient.from_storage(path=storage_path) as client:
                status = await client.artifacts.generate_video(
                    notebook_id,
                    instructions=instructions,
                    video_style=VideoStyle.CUSTOM,
                )
                logger.info("API fallback video generation started with task ID: %s", status.task_id)
            return True, ""
        except Exception as exc:
            return False, str(exc)

    async def _add_text_source(self, text_value: str) -> bool:
        assert self.page is not None
        if not text_value.strip():
            return False

        if not await self._fill_source_text_input(text_value):
            opened = await self._click_labels(
                ["Add source", "Add Source", "Sources", "Add"],
                required=False,
            )
            if not opened:
                return False
            await asyncio.sleep(0.5)
            await self._click_labels(
                ["Copied text", "Paste text", "Text", "Text source"],
                required=False,
            )
            if not await self._fill_source_text_input(text_value):
                return False

        submitted = await self._click_labels(
            ["Insert", "Add source", "Add", "Save", "Done"],
            required=False,
        )
        if not submitted:
            await self.page.keyboard.press(f"{self.modifier_key}+Enter")
        await asyncio.sleep(0.8)
        return True

    async def _fill_video_field(self, labels: Sequence[str], value: str) -> bool:
        assert self.page is not None
        if not value.strip():
            return False

        for label in labels:
            regex = re.compile(re.escape(label), re.IGNORECASE)
            candidates = [
                self.page.get_by_label(regex).first,
                self.page.get_by_placeholder(regex).first,
                self.page.get_by_role("textbox", name=regex).first,
            ]
            for locator in candidates:
                if not await self._is_visible(locator, timeout_ms=900):
                    continue
                try:
                    await locator.click()
                    await locator.fill(value)
                    return True
                except Exception:
                    continue

        # Fallback: look for a visible heading and fill first textbox in its section.
        for label in labels:
            heading = self.page.get_by_text(re.compile(re.escape(label), re.IGNORECASE)).first
            if not await self._is_visible(heading, timeout_ms=700):
                continue
            container = heading.locator("xpath=ancestor::*[self::section or self::div][1]").first
            field = container.locator(
                "textarea, [role='textbox'], [contenteditable='true'], input[type='text']"
            ).first
            if not await self._is_visible(field, timeout_ms=700):
                continue
            try:
                await field.click()
                await field.fill(value)
                return True
            except Exception:
                continue

        return False

    async def _select_custom_style_fallback(self) -> bool:
        assert self.page is not None

        regex = re.compile(r"custom( visual style| style)?", re.IGNORECASE)

        # Some UIs expose style options as radio/option controls instead of buttons.
        role_locators = [
            self.page.get_by_role("radio", name=regex).first,
            self.page.get_by_role("option", name=regex).first,
            self.page.get_by_role("tab", name=regex).first,
        ]
        for locator in role_locators:
            if await self._is_visible(locator, timeout_ms=1200):
                try:
                    await locator.click()
                    return True
                except Exception:
                    continue

        label_locators = [
            self.page.get_by_label(regex).first,
            self.page.get_by_text(regex).first,
        ]
        for locator in label_locators:
            if await self._is_visible(locator, timeout_ms=1200):
                try:
                    await locator.click()
                    return True
                except Exception:
                    continue

        # If style controls are hidden behind a style menu, open it first.
        menu_opened = await self._click_labels(
            ["Visual style", "Video style", "Style", "Choose style"],
            required=False,
        )
        if menu_opened:
            await asyncio.sleep(0.4)
            for locator in role_locators + label_locators:
                if await self._is_visible(locator, timeout_ms=1200):
                    try:
                        await locator.click()
                        return True
                    except Exception:
                        continue

        return False

    async def _capture_debug_artifacts(self, label: str) -> None:
        assert self.page is not None
        if not self.config.debug_dir:
            return

        try:
            self.config.debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.config.debug_dir / f"{stamp}_{label}.png"
            html_path = self.config.debug_dir / f"{stamp}_{label}.html"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            html_path.write_text(await self.page.content(), encoding="utf-8")
            logger.info("Saved debug artifacts: %s and %s", screenshot_path, html_path)
        except Exception as exc:
            logger.warning("Failed to write debug artifacts: %s", exc)

    async def _fill_source_text_input(self, value: str) -> bool:
        assert self.page is not None

        # Prefer source dialog fields to avoid typing into chat/search boxes.
        dialog = self.page.get_by_role("dialog").last
        dialog_selectors = [
            "textarea",
            "[role='textbox']",
            "[contenteditable='true']",
            "input[type='text']",
        ]
        for selector in dialog_selectors:
            locator = dialog.locator(selector).first
            if await self._is_visible(locator, timeout_ms=1000):
                try:
                    await locator.click()
                    await locator.fill(value)
                    return True
                except Exception:
                    continue

        return await self._fill_first_visible(
            [
                "textarea[placeholder*='paste' i]",
                "textarea[placeholder*='text' i]",
                "textarea[aria-label*='source' i]",
                "textarea[aria-label*='text' i]",
                "[role='textbox'][aria-label*='source' i]",
                "[role='textbox'][aria-label*='text' i]",
                "textarea",
                "[contenteditable='true'][role='textbox']",
                "[role='textbox']",
                "input[type='text']",
            ],
            value,
        )

    async def _close_popups(self, result: WorkflowResult, step_label: str) -> None:
        """Close popups/dialogs/overlays SAFELY without navigating away from the notebook.
        
        IMPORTANT: This method must NEVER click anything that could navigate away
        from the notebook page. We only target buttons inside dialogs/overlays,
        and we verify the URL hasn't changed after each action.
        """
        assert self.page is not None
        closed_any = False
        saved_url = self.page.url

        for _ in range(3):
            closed_in_pass = False

            # Strategy 1: Look for buttons INSIDE a dialog element
            dialogs = self.page.get_by_role("dialog")
            dialog_count = await dialogs.count()
            for i in range(dialog_count):
                dialog = dialogs.nth(i)
                if not await self._is_visible(dialog, timeout_ms=300):
                    continue
                for btn_label in ["Got it", "Dismiss", "Not now", "No thanks", "Skip", "OK"]:
                    btn = dialog.get_by_role("button", name=re.compile(re.escape(btn_label), re.IGNORECASE)).first
                    if await self._is_visible(btn, timeout_ms=300):
                        try:
                            logger.info("Closing dialog with '%s' button", btn_label)
                            await btn.click()
                            closed_in_pass = True
                            closed_any = True
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass

            # Strategy 2: Look for tooltip/popover close buttons
            # These typically have aria-label containing "close" or "dismiss"
            # But ONLY inside elements that look like overlays, not the main page
            for overlay_selector in ["[role='dialog']", "[role='alertdialog']", ".popover", ".tooltip", ".overlay"]:
                overlay = self.page.locator(overlay_selector).first
                if await self._is_visible(overlay, timeout_ms=300):
                    close_btn = overlay.locator("button[aria-label*='close' i], button[aria-label*='dismiss' i]").first
                    if await self._is_visible(close_btn, timeout_ms=300):
                        try:
                            logger.info("Closing overlay via close icon")
                            await close_btn.click()
                            closed_in_pass = True
                            closed_any = True
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass

            # Strategy 3: Press Escape to dismiss any overlay
            if not closed_in_pass:
                # Only try Escape if there's something overlay-like visible
                for text in ["Create audio and video overviews", "Audio and video overviews",
                             "Get started with notebooks"]:
                    popup = self.page.locator(f"text={text}").first
                    if await self._is_visible(popup, timeout_ms=300):
                        logger.info("Found popup text '%s', pressing Escape", text)
                        await self.page.keyboard.press("Escape")
                        closed_in_pass = True
                        closed_any = True
                        await asyncio.sleep(0.5)
                        break

            # Safety check: make sure we haven't navigated away
            if self.page.url != saved_url and "/notebook/" not in self.page.url:
                logger.warning("_close_popups navigated away! Reverting to %s", saved_url)
                await self.page.goto(saved_url, wait_until="domcontentloaded")
                await asyncio.sleep(1.0)
                break  # Stop trying to close more popups

            if not closed_in_pass:
                break

        if closed_any:
            result.steps_completed.append(step_label)

    async def _select_all_checkboxes(self) -> bool:
        assert self.page is not None
        checkboxes = self.page.locator("input[type='checkbox']")
        count = await checkboxes.count()
        selected_any = False

        for idx in range(count):
            checkbox = checkboxes.nth(idx)
            if not await self._is_visible(checkbox, timeout_ms=250):
                continue
            try:
                if not await checkbox.is_checked():
                    await checkbox.click()
                    selected_any = True
            except Exception:
                continue

        return selected_any

    def _default_research_query(self) -> str:
        return self.config.video_title

    async def _wait_for_any_label(
        self,
        labels: Sequence[str],
        timeout_s: int,
        initial_delay_s: float = 0.0,
    ) -> bool:
        if initial_delay_s > 0:
            await asyncio.sleep(initial_delay_s)

        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if await self._any_visible_label(labels, timeout_ms=900):
                return True
            await asyncio.sleep(1.0)
        return False

    async def _wait_until_logged_in(self, timeout_s: int) -> None:
        assert self.page is not None
        deadline = asyncio.get_running_loop().time() + timeout_s

        while True:
            current_url = self.page.url
            if "/notebook/" in current_url:
                return

            if "accounts.google.com" not in current_url:
                if await self._any_visible_label(
                    ["Create", "New notebook", "Add source", "Notebooks"],
                    timeout_ms=800,
                ):
                    return

            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(
                    "Login timeout: complete Google login in the opened browser "
                    f"within {timeout_s} seconds."
                )

            await asyncio.sleep(1.0)

    async def _wait_for_notebook_url(self, timeout_s: int) -> None:
        assert self.page is not None
        try:
            await self.page.wait_for_url("**/notebook/**", timeout=timeout_s * 1000)
            return
        except PlaywrightTimeoutError:
            pass

        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if "/notebook/" in self.page.url:
                return
            await asyncio.sleep(0.8)

        raise RuntimeError("Timed out waiting for notebook URL after create")

    def _extract_notebook_id(self) -> Optional[str]:
        assert self.page is not None
        match = re.search(r"/notebook/([^/?#]+)", self.page.url)
        if not match:
            return None
        return match.group(1)

    def _build_notebook_url(self, notebook_id: str) -> str:
        return f"{HOME_URL}notebook/{notebook_id}"

    def _build_new_notebook_name(self) -> str:
        if self.config.notebook_name and self.config.notebook_name.strip():
            base = self.config.notebook_name.strip()
        else:
            base = self.config.video_title.strip() or "NotebookLM Video"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base} - {stamp}"

    async def _click_labels(self, labels: Sequence[str], required: bool = True) -> bool:
        assert self.page is not None

        for label in labels:
            regex = re.compile(re.escape(label), re.IGNORECASE)
            candidates = [
                self.page.get_by_role("button", name=regex).first,
                self.page.get_by_role("tab", name=regex).first,
                self.page.get_by_role("menuitem", name=regex).first,
                self.page.get_by_role("link", name=regex).first,
                self.page.get_by_text(regex).first,
            ]

            for locator in candidates:
                if await self._is_visible(locator, timeout_ms=1200):
                    try:
                        await locator.click()
                        return True
                    except Exception:
                        continue

        if required:
            raise RuntimeError(f"Could not click any label in: {labels}")
        return False

    async def _fill_first_visible(self, selectors: Sequence[str], value: str) -> bool:
        assert self.page is not None

        for selector in selectors:
            locator = self.page.locator(selector).first
            if not await self._is_visible(locator, timeout_ms=1500):
                continue

            try:
                await locator.click()
                await locator.fill(value)
                return True
            except Exception:
                try:
                    await locator.click()
                    await self.page.keyboard.press(f"{self.modifier_key}+A")
                    await self.page.keyboard.type(value, delay=1)
                    return True
                except Exception:
                    continue

        return False

    async def _save_with_shortcut(self) -> None:
        assert self.page is not None
        await self.page.keyboard.press(f"{self.modifier_key}+Enter")

    async def _is_visible(self, locator: Locator, timeout_ms: int) -> bool:
        try:
            await locator.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    async def _any_visible_label(self, labels: Sequence[str], timeout_ms: int) -> bool:
        assert self.page is not None

        for label in labels:
            regex = re.compile(re.escape(label), re.IGNORECASE)
            locators = [
                self.page.get_by_role("button", name=regex).first,
                self.page.get_by_text(regex).first,
            ]
            for locator in locators:
                if await self._is_visible(locator, timeout_ms=timeout_ms):
                    return True
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate NotebookLM website flow to generate videos."
    )

    parser.add_argument("--video-title", help="Video title added as a source")
    parser.add_argument("--studio-note", help="Instruction note content for Studio")
    parser.add_argument(
        "--additional-notes",
        default="",
        help="Legacy field (unused; visual style and host focus are hardcoded)",
    )
    parser.add_argument(
        "--custom-visual-style",
        default="",
        help="Deprecated: ignored (hardcoded global style is used)",
    )
    parser.add_argument(
        "--host-focus-notes",
        default="",
        help="Deprecated: ignored (hardcoded global host guidance is used)",
    )
    parser.add_argument(
        "--research-query",
        default="",
        help="Optional custom query for Fast Research",
    )
    parser.add_argument("--notebook-name", default=None, help="Optional notebook label")
    parser.add_argument("--notebook-id", default=None, help="Optional existing notebook ID")
    parser.add_argument(
        "--new-notebook",
        action="store_true",
        help="Always create a new notebook for this run",
    )
    parser.add_argument(
        "--start-url",
        default=None,
        help="Optional NotebookLM URL (existing notebook or addSource URL)",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Playwright profile directory",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional file to save result JSON",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=25_000,
        help="Playwright timeout in milliseconds",
    )
    parser.add_argument(
        "--login-timeout",
        type=int,
        default=180,
        help="Seconds to wait for manual Google login",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=60,
        help="Delay between UI actions in milliseconds",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--keep-open",
        type=int,
        default=8,
        help="Keep browser open for N seconds after run",
    )
    parser.add_argument(
        "--debug-dir",
        default="",
        help="Optional folder to save screenshot/HTML artifacts on selector misses",
    )
    parser.add_argument(
        "--disable-fast-research",
        action="store_true",
        help="Skip Fast Research and import flow",
    )
    parser.add_argument(
        "--disable-refresh-before-video-overview",
        action="store_true",
        help="Skip tab refresh before opening Video Overview",
    )
    parser.add_argument(
        "--disable-popup-closing",
        action="store_true",
        help="Disable popup close attempts",
    )
    parser.add_argument(
        "--disable-api-fallback",
        action="store_true",
        help="Disable notebooklm-py fallback for missing UI actions",
    )
    parser.add_argument(
        "--api-storage-path",
        default="",
        help="Optional notebooklm-py storage_state.json path for API fallback auth",
    )
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="Only open browser and wait for manual login",
    )
    return parser.parse_args()


async def run_from_cli(args: argparse.Namespace) -> int:
    if args.login_only:
        cfg = WorkflowConfig(
            video_title="login",
            studio_note="login",
            profile_dir=Path(args.profile_dir),
            timeout_ms=args.timeout_ms,
            manual_login_timeout_s=args.login_timeout,
            slow_mo_ms=0,
            headless=False,
            keep_open_seconds=0,
        )
        workflow = NotebookLMPlaywrightWorkflow(cfg)
        url = await workflow.wait_for_manual_login()
        print(json.dumps({"status": "success", "url": url}, indent=2))
        return 0

    if not args.video_title or not args.studio_note:
        raise ValueError("--video-title and --studio-note are required unless --login-only is set")

    cfg = WorkflowConfig(
        video_title=args.video_title,
        studio_note=args.studio_note,
        additional_notes=args.additional_notes,
        custom_visual_style=DEFAULT_CUSTOM_VISUAL_STYLE,
        host_focus_notes=DEFAULT_HOST_FOCUS_NOTES,
        research_query=args.research_query,
        notebook_id=args.notebook_id,
        notebook_name=args.notebook_name,
        force_new_notebook=args.new_notebook,
        start_url=args.start_url,
        profile_dir=Path(args.profile_dir),
        timeout_ms=args.timeout_ms,
        manual_login_timeout_s=args.login_timeout,
        slow_mo_ms=args.slow_mo,
        headless=args.headless,
        keep_open_seconds=max(0, args.keep_open),
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
        enable_api_fallback=not args.disable_api_fallback,
        api_storage_path=Path(args.api_storage_path) if args.api_storage_path else None,
        enable_fast_research=not args.disable_fast_research,
        refresh_before_video_overview=not args.disable_refresh_before_video_overview,
        close_popups_on_start=not args.disable_popup_closing,
        output_json=args.output_json,
    )

    workflow = NotebookLMPlaywrightWorkflow(cfg)
    result = await workflow.run()
    payload = asdict(result)
    print(json.dumps(payload, indent=2))

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved run result to %s", output_path)

    return 0 if result.status in {"success", "partial"} else 1


def main() -> int:
    args = parse_args()
    return asyncio.run(run_from_cli(args))


if __name__ == "__main__":
    raise SystemExit(main())
