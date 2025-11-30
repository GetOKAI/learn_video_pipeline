"""Simple Mux uploader using the installed `mux` CLI.

This module provides a small wrapper around the `mux` CLI to upload
local video files into Mux. It intentionally uses the CLI so there's
no extra Python package dependency. The CLI must be installed and
authenticated (see README / Mux docs).

Usage:
    from mux_uploader import MuxUploader
    uploader = MuxUploader()                # requires MUX_TOKEN_ID/SECRET in env or logged in via mux login
    res = uploader.upload_video("/path/to/video.mp4", title="Ladder Safety Guide")
    print(res)
"""
import os
import json
import shlex
import subprocess
from typing import Any, Dict, Optional


class MuxUploader:
    """Upload local videos to Mux using the `mux` CLI.

    Notes:
    - Requires the `mux` CLI to be installed and available in PATH.
    - The CLI must be authenticated (via `mux login`) or the
      environment variables `MUX_TOKEN_ID` and `MUX_TOKEN_SECRET`
      should be exported before running.
    """

    def __init__(self) -> None:
        self.token_id = os.getenv("MUX_TOKEN_ID")
        self.token_secret = os.getenv("MUX_TOKEN_SECRET")

    def _ensure_cli_available(self) -> Optional[str]:
        """Return path to mux CLI or None if not available."""
        try:
            p = subprocess.run(["mux", "--version"], capture_output=True, text=True)
            if p.returncode == 0:
                return p.stdout.strip()
        except FileNotFoundError:
            return None
        return None

    def upload_video(self, file_path: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Upload a single video file to Mux.

        Returns a dictionary with either status == "success" and the
        parsed CLI JSON under `mux_response`, or status == "error" and
        an `error` message.
        """
        if not os.path.exists(file_path):
            return {"status": "error", "error": f"file not found: {file_path}"}

        cli_ver = self._ensure_cli_available()
        if not cli_ver:
            return {"status": "error", "error": "mux CLI not found in PATH"}

        # If tokens are present in env, the CLI will use them, otherwise
        # assume the user has run `mux login` previously.

        # Build CLI command: mux assets:upload --json <file>
        cmd = ["mux", "assets:upload", "--json", file_path]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                # CLI failed; return stderr and stdout for debugging
                return {"status": "error", "error": stderr or stdout}

            # Try to parse JSON output. The CLI prints JSON when --json is used,
            # but some CLIs may include extra lines; try the last non-empty line.
            parsed = None
            if stdout:
                lines = [l for l in stdout.splitlines() if l.strip()]
                for candidate in reversed(lines):
                    try:
                        parsed = json.loads(candidate)
                        break
                    except Exception:
                        continue

            if parsed is None:
                # Fall back to returning raw output
                return {"status": "success", "mux_response": {"raw_output": stdout}}

            # Attach title if provided
            result = {"status": "success", "mux_response": parsed}
            if title:
                result["title"] = title
            return result

        except Exception as e:
            return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload a video file to Mux via mux CLI")
    parser.add_argument("file", help="Path to local video file")
    parser.add_argument("--title", help="Optional title to attach", default=None)
    args = parser.parse_args()

    uploader = MuxUploader()
    out = uploader.upload_video(args.file, title=args.title)
    print(json.dumps(out, indent=2))
