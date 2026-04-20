"""Parsers that turn raw test output into structured failure reports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

from langchain_core.tools import tool


@dataclass
class TestResult:
    name: str
    status: str  # "passed", "failed", "error", "skipped"
    duration_s: float = 0.0
    error_message: str = ""
    traceback: str = ""


@dataclass
class TestReport:
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    results: list[dict] = field(default_factory=list)
    raw_summary: str = ""

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_pytest_verbose(output: str) -> TestReport:
    """Parse pytest -v output into a TestReport."""
    report = TestReport()

    # Match lines like: test_file.py::test_name PASSED/FAILED
    result_pattern = re.compile(
        r"^([\w/\\.]+::\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)",
        re.MULTILINE,
    )
    for m in result_pattern.finditer(output):
        name, status = m.group(1), m.group(2).lower()
        tr = TestResult(name=name, status=status)
        report.results.append(asdict(tr))
        report.total += 1
        if status == "passed":
            report.passed += 1
        elif status == "failed":
            report.failed += 1
        elif status == "error":
            report.errors += 1
        elif status == "skipped":
            report.skipped += 1

    # Extract failure tracebacks
    failure_blocks = re.findall(
        r"_{5,} ([\w:]+) _{5,}\n(.*?)(?=\n_{5,}|\n={5,}|\Z)",
        output,
        re.DOTALL,
    )
    for test_id, tb_text in failure_blocks:
        for r in report.results:
            if r["name"].endswith(test_id.split("::")[-1]):
                r["traceback"] = tb_text.strip()[-2000:]
                # Extract the last assertion / error line
                lines = tb_text.strip().splitlines()
                for line in reversed(lines):
                    if line.strip().startswith(("AssertionError", "E ", "assert", "Error", "Exception")):
                        r["error_message"] = line.strip()
                        break

    # Summary line: "= 3 passed, 1 failed in 2.45s ="
    summary_match = re.search(r"=+\s+(.+?)\s+=+\s*$", output, re.MULTILINE)
    if summary_match:
        report.raw_summary = summary_match.group(1)

    return report


@tool
def parse_pytest_output(raw_output: str) -> dict[str, Any]:
    """Parse raw pytest verbose output into a structured test report.

    Args:
        raw_output: The full stdout from a pytest -v run.
    """
    report = _parse_pytest_verbose(raw_output)
    return report.to_dict()


@tool
def parse_playwright_output(raw_output: str) -> dict[str, Any]:
    """Parse Playwright test runner output into a structured report.

    Playwright tests run via pytest-playwright so the format is
    the same as standard pytest.

    Args:
        raw_output: The full stdout from a playwright test run.
    """
    report = _parse_pytest_verbose(raw_output)
    return report.to_dict()
