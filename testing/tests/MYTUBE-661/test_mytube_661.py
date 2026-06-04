#!/usr/bin/env python3
"""
MYTUBE-661 — Hero and Header unit tests pass with new copy.

Runs the existing Jest unit tests for:
  - web/src/__tests__/components/HeroSection.test.tsx
  - web/src/__tests__/components/SiteHeader.test.tsx
  - web/src/__tests__/app/home/page.test.tsx

This test acts as an orchestrator: it invokes Jest for each target file,
captures pass/fail, and reports accordingly.
"""

import subprocess
import sys
import os

# Paths relative to the repo root
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
WEB_DIR = os.path.join(REPO_ROOT, "web")

TEST_FILES = [
    "src/__tests__/components/HeroSection.test.tsx",
    "src/__tests__/components/SiteHeader.test.tsx",
    "src/__tests__/app/home/page.test.tsx",
]


def run_jest(test_file: str) -> tuple[bool, str]:
    """Run Jest for a single test file; return (passed, output)."""
    result = subprocess.run(
        ["npx", "jest", "--no-coverage", "--testPathPatterns", test_file],
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def main() -> int:
    print(f"Running Jest unit tests from: {WEB_DIR}\n")
    all_passed = True
    results: list[dict] = []

    for test_file in TEST_FILES:
        print(f"  Running: {test_file}")
        passed, output = run_jest(test_file)
        status = "PASS" if passed else "FAIL"
        print(f"  Status:  {status}\n")
        if not passed:
            all_passed = False
            print("  --- Jest output ---")
            print(output)
            print("  -------------------\n")
        results.append({"file": test_file, "passed": passed, "output": output})

    print("=" * 60)
    if all_passed:
        print("✅  All unit tests PASSED")
        return 0
    else:
        failed = [r["file"] for r in results if not r["passed"]]
        print(f"❌  FAILED test files: {failed}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
