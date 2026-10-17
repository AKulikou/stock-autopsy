"""
The page's own logic (web/static/*.js) under Node's test runner: tests/js/*.test.mjs.

Skipped where Node 22 or newer is not installed (it loads the page's ES modules
without a build step or a package.json).
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS_TESTS = Path(__file__).parent / "js"
MIN_NODE = 22


def node_major(node: str) -> int:
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout
    return int(re.match(r"v(\d+)", version.strip()).group(1))


def test_the_page_scripts_pass_their_node_tests():
    node = shutil.which("node")
    if node is None or node_major(node) < MIN_NODE:
        pytest.skip(f"Node {MIN_NODE}+ is not installed")
    files = sorted(str(p) for p in JS_TESTS.glob("*.test.mjs"))
    assert files, "no JS tests found"
    result = subprocess.run([node, "--test", *files], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
