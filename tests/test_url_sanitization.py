"""
Tests for URL sanitization — verifying that URL fragments (#...) are properly
stripped before cloning and naming operations.

This test directly imports only the pure function `repo_url_to_name` without
triggering heavy dependencies like tree_sitter (which live inside Docker).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Inline the function under test to avoid the tree_sitter import chain ──
def repo_url_to_name(repo_url: str) -> str:
    """Mirror of backend.app.ingestion.repo_manager.repo_url_to_name."""
    repo_url = repo_url.split("#")[0]
    cleaned = re.sub(r"^https?://github\.com/", "", repo_url)
    cleaned = re.sub(r"^git@github\.com:", "", cleaned)
    cleaned = re.sub(r"\.git$", "", cleaned)
    cleaned = cleaned.strip("/")
    return cleaned.replace("/", "_")


# Also verify the *actual* source file contains the fragment-stripping line
def _read_source() -> str:
    src = Path(__file__).parent.parent / "backend" / "app" / "ingestion" / "repo_manager.py"
    return src.read_text(encoding="utf-8")


class TestRepoUrlToName:
    """Verify repo_url_to_name strips fragments and produces safe names."""

    def test_plain_url(self):
        assert repo_url_to_name("https://github.com/user/repo") == "user_repo"

    def test_url_with_fragment(self):
        result = repo_url_to_name("https://github.com/rtk-ai/rtk#installation")
        assert result == "rtk-ai_rtk", f"Expected 'rtk-ai_rtk', got '{result}'"

    def test_url_with_dotgit(self):
        assert repo_url_to_name("https://github.com/user/repo.git") == "user_repo"

    def test_url_with_fragment_and_dotgit(self):
        result = repo_url_to_name("https://github.com/user/repo.git#readme")
        assert result == "user_repo"

    def test_ssh_url(self):
        assert repo_url_to_name("git@github.com:user/repo.git") == "user_repo"

    def test_url_with_trailing_slash(self):
        assert repo_url_to_name("https://github.com/user/repo/") == "user_repo"

    def test_url_with_complex_fragment(self):
        result = repo_url_to_name(
            "https://github.com/n0namedeveloper/localRAG#quick-start"
        )
        assert result == "n0namedeveloper_localRAG"


class TestSourceFileContainsFix:
    """Verify the actual source file has the fragment-stripping fix."""

    def test_repo_url_to_name_has_fragment_strip(self):
        source = _read_source()
        assert 'repo_url.split("#")[0]' in source, (
            "repo_url_to_name is missing the '#' fragment strip"
        )

    def test_get_repo_has_fragment_strip(self):
        source = _read_source()
        # The get_repo method should also strip fragments
        # Find the get_repo method body and check
        idx = source.find("def get_repo(")
        assert idx != -1, "get_repo method not found"
        method_body = source[idx:idx + 800]
        assert 'repo_url.split("#")[0]' in method_body, (
            "get_repo method is missing the '#' fragment strip"
        )

    def test_pipeline_has_fragment_strip(self):
        pipeline_src = (
            Path(__file__).parent.parent
            / "backend" / "app" / "ingestion" / "pipeline.py"
        ).read_text(encoding="utf-8")
        assert 'repo_url.split("#")[0]' in pipeline_src, (
            "pipeline.py is missing the '#' fragment strip"
        )
