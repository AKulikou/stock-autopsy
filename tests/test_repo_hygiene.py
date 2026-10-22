"""
What may be in the repository at all: the tracked files only, read through git, so a log,
a run folder, a console capture or a local path never reaches a commit unnoticed. Runs in CI.
"""

import gzip
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_TOP_LEVEL = {
    ".env.example", ".gitattributes", ".github", ".gitignore", "CLAUDE.md", "LICENSE", "README.md",
    "analysis", "config.py", "core", "datalayer", "docs", "eval", "evaluators", "examples", "main.py",
    "perspectives", "pyproject.toml", "pytest.ini", "reporting", "requirements.txt",
    "requirements-dev.txt", "scripts", "synthesis", "tests", "translate", "valuation", "web",
}
FORBIDDEN_PARTS = {"logs", "results", "data_cache", "private", ".claude", "venv", "__pycache__"}
MAX_BYTES = 250 * 1024

# Built from pieces, so this file does not flag itself.
_DRIVE = r"(?<![A-Za-z])[A-Za-z]:[\\/]"
_HOME = "/" + "home/" + r"|/" + "Users/"
LOCAL_PATH = re.compile(rf"{_DRIVE}|{_HOME}")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ALLOWED_EMAIL = re.compile(
    r"@(?:example\.com|example\.org|users\.noreply\.github\.com)$|^noreply@anthropic\.com$", re.IGNORECASE
)
API_KEY = re.compile("sk-" + r"ant-[A-Za-z0-9_\-]+")
ALLOWED_KEYS = {"sk-" + "ant-ci-placeholder", "sk-" + "ant-test-key-not-used"}


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [name for name in out.decode("utf-8").split("\0") if name]


def text_of(name: str) -> str:
    """The file as text: a gzip fixture is decoded first. Raises UnicodeDecodeError if not UTF-8."""
    data = (ROOT / name).read_bytes()
    if name.endswith(".gz"):
        data = gzip.decompress(data)
    return data.decode("utf-8")


def problems(names: list[str]) -> list[str]:
    found = []
    for name in names:
        parts = Path(name).parts
        if parts[0] not in ALLOWED_TOP_LEVEL:
            found.append(f"{name}: not an allowed top-level path")
        if FORBIDDEN_PARTS & set(parts):
            found.append(f"{name}: under a folder that is never tracked")
        if not (ROOT / name).exists():
            continue  # deleted in the working tree, not yet committed
        if (ROOT / name).stat().st_size > MAX_BYTES:
            found.append(f"{name}: larger than {MAX_BYTES // 1024} KB")
        try:
            text = text_of(name)
        except UnicodeDecodeError:
            found.append(f"{name}: not UTF-8")
            continue
        if name == "tests/test_repo_hygiene.py":
            continue
        for match in LOCAL_PATH.finditer(text):
            found.append(f"{name}: local path {match.group(0)!r}")
        for email in EMAIL.findall(text):
            if not ALLOWED_EMAIL.search(email):
                found.append(f"{name}: email address {email}")
        for key in API_KEY.findall(text):
            if key not in ALLOWED_KEYS:
                found.append(f"{name}: something like an API key ({key[:12]}...)")
    return found


def test_every_tracked_file_belongs_in_the_repository():
    assert problems(tracked_files()) == []


def test_the_check_catches_what_must_not_be_committed(tmp_path, monkeypatch):
    bad = {
        "notes_console.txt": "run log".encode("utf-16"),  # a console capture: not UTF-8, wrong place
        "logs/run.log": b"ok",
        "core/leak.py": ("path = r'" + "C:" + "\\Users\\someone'\n"
                         "who = 'someone@" + "gmail.com'\n"
                         "key = 'sk-" + "ant-api03-abcdef'\n").encode(),
    }
    for name, data in bad.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(data)
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    found = "\n".join(problems(list(bad)))
    assert "notes_console.txt: not an allowed top-level path" in found
    assert "notes_console.txt: not UTF-8" in found
    assert "logs/run.log: under a folder that is never tracked" in found
    assert "local path" in found and "email address" in found and "API key" in found
