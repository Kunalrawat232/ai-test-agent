"""Browser automation tools — Playwright and Selenium execution."""

from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from config.settings import exec_config, paths


@tool
def playwright_run_test(script_path: str) -> dict[str, Any]:
    """Execute a Playwright test script and return structured results.

    Args:
        script_path: Absolute or relative path to the Playwright test file.
    """
    script = Path(script_path)
    if not script.exists():
        return {"success": False, "error": f"Script not found: {script_path}"}

    cmd = [
        "python", "-m", "pytest", str(script),
        "--tb=short",
        f"--timeout={exec_config.test_timeout_ms // 1000}",
        "-v",
        "--json-report",
        "--json-report-file=-",
    ]

    env_vars = {
        "BASE_URL": exec_config.target_base_url,
        "HEADLESS": str(exec_config.headless).lower(),
    }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env={**__import__("os").environ, **env_vars},
            cwd=str(paths.generated_scripts),
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-3000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Test execution timed out after 120s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool
def selenium_run_test(script_path: str) -> dict[str, Any]:
    """Execute a Selenium-based pytest script and return structured results.

    Args:
        script_path: Absolute or relative path to the Selenium test file.
    """
    script = Path(script_path)
    if not script.exists():
        return {"success": False, "error": f"Script not found: {script_path}"}

    cmd = [
        "python", "-m", "pytest", str(script),
        "--tb=short",
        "-v",
    ]

    env_vars = {
        "BASE_URL": exec_config.target_base_url,
        "HEADLESS": str(exec_config.headless).lower(),
    }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env={**__import__("os").environ, **env_vars},
            cwd=str(paths.generated_scripts),
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-3000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Test execution timed out after 120s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
