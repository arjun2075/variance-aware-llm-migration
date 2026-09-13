"""Guard: the PUBLIC artifact must contain no proprietary or internal content.

This is the public mirror of the study. Unlike the private research repository
it is derived from, it must not name the corporate execution environment at
all. The strict rules are therefore ALWAYS ON here; PUBLIC_RELEASE=1 is
accepted for compatibility but changes nothing.

Strictly forbidden, and enforced by this test:

  * production PROMPT TEXT recovered from the historical study
  * production SOURCE CODE and package paths
  * credentials of any shape
  * internal URLs, hostnames, and infrastructure identifiers
  * the corporate name, its internal execution-service name, internal
    adapter/module names, internal credential tooling, and internal
    model-catalog identifiers

Execution-environment identifiers were removed from this artifact because they
are not required to reproduce any reported statistic: every analysis reads the
persisted ledger and makes no model calls. Where a provenance field is still
needed, neutral terminology is used (``managed_execution_path``).

Public model identifiers (e.g. ``gpt-4o-2024-11-20``) ARE retained: they are
public, immutable and scientifically necessary to interpret the results.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

#: Always strict in the public mirror. The variable is retained so the
#: documented ``PUBLIC_RELEASE=1 pytest ...`` invocation keeps working.
PUBLIC_RELEASE = True
_ = os.environ.get("PUBLIC_RELEASE")

REPO = Path(__file__).resolve().parents[1]

# Substrings that must never appear. Lowercased comparison.
#: Always forbidden, private repo or not. These are the things whose presence
#: would constitute an actual IP or credential leak.
FORBIDDEN_SUBSTRINGS = [
    # Internal source hosting and the production service repo
    "github.intuit.com",
    "shaurya-service",
    "sales-core",
    # Internal serving / auth identifiers from the recovered run records
    "managed_idps_privateauth_aiservice",
    "privateauth",
    "idps",
    # Production prompt constant and its reference key
    "productionsynthesissystemprompt",
    "developer-analytics-synthesis-production",
    # Recovered production package paths
    "analytics_experiment",
    "developer-analytics-experiment",
]

#: Internal identifiers. Always forbidden in the public mirror.
#: NOTE: "intuit" is matched as a whole word only, so ordinary English words
#: such as "intuition" and "intuitively" are not false positives.
PUBLIC_RELEASE_FORBIDDEN = [
    "genos",
    "gpt-4o-2024-11-20-oai",
    "istio-envoy",
    "eiamcli",
    "genosadapter",
    "shimadapter",
]

#: Matched with word boundaries rather than as a bare substring.
FORBIDDEN_WORDS = ["intuit"]

if PUBLIC_RELEASE:
    FORBIDDEN_SUBSTRINGS = FORBIDDEN_SUBSTRINGS + PUBLIC_RELEASE_FORBIDDEN

# Distinctive phrases from the recovered proprietary synthesis prompt. If any
# appears, proprietary wording has been copied rather than newly authored.
FORBIDDEN_PROMPT_PHRASES = [
    "senior engineering manager preparing a data-driven performance review",
    "mandatory baseline citation rule",
    "cross-source pattern detection",
    "incident ↔ jira closed-loop check",
    "hand-off-and-forget",
    "company_values_examples",
    "evidence_strength",
]

# Credential-shaped patterns.
SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "OpenAI-style API key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic-style API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".pytest_cache",
             ".ruff_cache", "node_modules"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".npz", ".zip", ".gz",
                   ".parquet", ".ico", ".woff", ".woff2"}


def tracked_text_files() -> list[Path]:
    """Every git-tracked text file, plus untracked ones not yet committed."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "--cached", "--others",
         "--exclude-standard"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    files = []
    for rel in out:
        if not rel:
            continue
        p = REPO / rel
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in BINARY_SUFFIXES:
            continue
        if p.name == Path(__file__).name:  # this file names the forbidden strings
            continue
        files.append(p)
    return files


def read(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


@pytest.mark.parametrize("needle", FORBIDDEN_SUBSTRINGS)
def test_no_forbidden_identifier(needle: str):
    hits = []
    for p in tracked_text_files():
        text = read(p)
        if text and needle in text.lower():
            hits.append(str(p.relative_to(REPO)))
    assert not hits, (
        f"Proprietary/internal identifier {needle!r} found in: {hits}. "
        "This repo must not depend on or reference internal artifacts."
    )


@pytest.mark.parametrize("word", FORBIDDEN_WORDS)
def test_no_forbidden_word(word: str):
    """Whole-word match, so "intuition"/"intuitively" are not false positives."""
    pat = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    hits = []
    for p in tracked_text_files():
        text = read(p)
        if text and pat.search(text):
            hits.append(str(p.relative_to(REPO)))
    assert not hits, (
        f"Internal identifier {word!r} (whole word) found in: {hits}. "
        "The public artifact must not name the corporate execution environment."
    )


@pytest.mark.parametrize("phrase", FORBIDDEN_PROMPT_PHRASES)
def test_no_proprietary_prompt_wording(phrase: str):
    hits = []
    for p in tracked_text_files():
        text = read(p)
        if text and phrase in text.lower():
            hits.append(str(p.relative_to(REPO)))
    assert not hits, (
        f"Wording from the recovered proprietary prompt found in: {hits}. "
        "Pipeline 1 prompts must be NEWLY AUTHORED, not copied."
    )


def test_no_credential_shaped_strings():
    hits = []
    for p in tracked_text_files():
        text = read(p)
        if not text:
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{p.relative_to(REPO)}: {label}")
    assert not hits, f"Credential-shaped strings found: {hits}"


def test_env_file_is_not_tracked():
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    bad = [f for f in tracked
           if f == ".env" or (f.startswith(".env.") and f != ".env.example")]
    assert not bad, f"Environment files must never be tracked: {bad}"


def test_gitignore_covers_credentials():
    ig = (REPO / ".gitignore").read_text()
    for required in [".env", "*.pem", "*.key"]:
        assert required in ig, f".gitignore must cover {required}"


@pytest.mark.skipif(not PUBLIC_RELEASE,
                    reason="internal model catalog ids are expected in the "
                           "private repo; enforced only for public release")
def test_no_internal_model_alias_on_public_release():
    """Before publication, internal catalog aliases must be generalised."""
    hits = []
    for p in tracked_text_files():
        text = read(p)
        if text and "-oai" in text:
            hits.append(str(p.relative_to(REPO)))
    assert not hits, (
        f"Internal model catalog aliases found in {hits}. Generalise or scrub "
        "them before public release."
    )


def test_public_release_guard_is_wired():
    """The stricter rule set must actually be reachable."""
    assert PUBLIC_RELEASE_FORBIDDEN
    if PUBLIC_RELEASE:
        for needle in PUBLIC_RELEASE_FORBIDDEN:
            assert needle in FORBIDDEN_SUBSTRINGS
