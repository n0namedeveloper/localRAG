"""
Repository manager — handles cloning, updating, and walking Git repositories.
"""

import logging
import re
from pathlib import Path

from git import Repo, GitCommandError

from app.config import settings
from app.models.schemas import RepoStatus

logger = logging.getLogger(__name__)


def repo_url_to_name(repo_url: str) -> str:
    """
    Convert a GitHub URL to a safe directory name.

    Example:
        https://github.com/user/repo.git → user_repo
        git@github.com:user/repo.git       → user_repo
    """
    # Remove URL fragment
    repo_url = repo_url.split("#")[0]
    # Remove trailing .git and protocol
    cleaned = re.sub(r"^https?://github\.com/", "", repo_url)
    cleaned = re.sub(r"^git@github\.com:", "", cleaned)
    cleaned = re.sub(r"\.git$", "", cleaned)
    cleaned = cleaned.strip("/")
    # Replace / with _ for a safe folder name
    return cleaned.replace("/", "_")


def _get_repo_path(repo_url: str) -> Path:
    """Get the local path for a cloned repository."""
    name = repo_url_to_name(repo_url)
    return settings.repos_dir / name


class RepoManager:
    """
    Manages local clones of GitHub repositories.

    Supports:
      - Initial clone
      - Pull updates
      - File listing with .gitignore respect
    """

    def __init__(self):
        self.settings = settings
        settings.repos_dir.mkdir(parents=True, exist_ok=True)

    def get_repo(self, repo_url: str, branch: str | None = None, github_token: str | None = None) -> tuple[Repo, Path, RepoStatus]:
        """
        Clone or pull a repository. Returns (Repo, repo_path, status).

        Args:
            repo_url: GitHub URL.
            branch: Branch to checkout. If None, uses default branch.
            github_token: Optional GitHub PAT for private repos.

        Returns:
            Tuple of (git.Repo object, local path, status enum).
        """
        repo_url = repo_url.split("#")[0]
        repo_path = _get_repo_path(repo_url)

        if repo_path.exists():
            # If no branch specified, we'll use the repo's current head
            effective_branch = branch or repo_path.joinpath(".git/HEAD").read_text().strip().split("/")[-1] if repo_path.joinpath(".git/HEAD").exists() else "main"
            return self._update_repo(repo_path, effective_branch)
        else:
            return self._clone_repo(repo_url, repo_path, branch, github_token)

    def _clone_repo(
        self, repo_url: str, repo_path: Path, branch: str | None = None, github_token: str | None = None
    ) -> tuple[Repo, Path, RepoStatus]:
        """Clone a fresh repository."""
        logger.info(f"Cloning {repo_url} → {repo_path}")
        try:
            clone_kwargs = {
                "depth": 1,  # shallow clone for speed
                "multi_options": ["--single-branch"],  # Only clone the specified branch
            }
            if branch:
                clone_kwargs["branch"] = branch
            
            # If no branch specified, we'll use ls-remote to find default branch
            effective_url = repo_url
            if github_token:
                # Inject token into URL for authenticated clone
                effective_url = repo_url.replace(
                    "https://github.com/",
                    f"https://{github_token}:x-oauth-basic@github.com/"
                )
                logger.info("Using authenticated git URL")
            
            repo = Repo.clone_from(effective_url, str(repo_path), **clone_kwargs)
            logger.info(f"Clone complete: {repo_path}")
            return repo, repo_path, RepoStatus.READY
            
        except GitCommandError as e:
            error_msg = str(e)
            logger.error(f"Clone failed: {e}")
            
            # Provide helpful error messages based on the error type
            if "could not read Username" in error_msg or "Authentication failed" in error_msg:
                logger.error("Authentication failed. If this is a private repository, make sure GITHUB_TOKEN is set in your .env file")
            elif "Remote branch" in error_msg and "not found" in error_msg:
                logger.error(f"Branch '{branch}' not found. Try without specifying a branch to use the default branch, or verify the branch name")
            
            # Cleanup partial clone
            if repo_path.exists():
                import shutil
                shutil.rmtree(repo_path, ignore_errors=True)
            return None, repo_path, RepoStatus.ERROR

    def _update_repo(
        self, repo_path: Path, branch: str
    ) -> tuple[Repo, Path, RepoStatus]:
        """Pull latest changes from an existing clone."""
        logger.info(f"Updating {repo_path}")
        try:
            repo = Repo(str(repo_path))
            origin = repo.remotes.origin
            origin.fetch()

            # Determine the actual branch to use:
            # prefer the one passed in, but fall back to the repo's current HEAD
            available_branches = [ref.name.replace("origin/", "") for ref in origin.refs]
            effective_branch = branch if branch in available_branches else repo.active_branch.name
            logger.info(f"Checking out branch: {effective_branch} (available: {available_branches})")

            repo.git.checkout(effective_branch)
            repo.git.reset("--hard", f"origin/{effective_branch}")
            logger.info(f"Updated to {repo.head.commit.hexsha[:8]}")
            return repo, repo_path, RepoStatus.READY
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return None, repo_path, RepoStatus.ERROR

    def list_source_files(self, repo_path: Path) -> list[Path]:
        """
        List all source files in a repo, respecting .gitignore.

        Returns list of relative Paths.
        """
        files: list[Path] = []
        supported_extensions = {
            ".py", ".pyi",
            ".js", ".jsx", ".mjs", ".cjs",
            ".ts", ".tsx",
            ".go",
            ".rs",
            ".java",
            ".cpp", ".cc", ".cxx", ".hpp", ".h", ".c",
        }

        # Common dirs to skip
        skip_dirs = {
            "node_modules", "__pycache__", "venv", ".venv",
            "dist", "build", "target", ".git", ".github",
            "coverage", ".tox", ".eggs", ".mypy_cache",
            ".pytest_cache", ".ruff_cache",
        }

        for file_path in repo_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                parts = file_path.relative_to(repo_path).parts
                # Skip hidden dirs and known skip dirs
                if any(p.startswith(".") for p in parts[:-1]):
                    continue
                if any(p in skip_dirs for p in parts):
                    continue
                files.append(file_path)

        logger.info(f"Found {len(files)} source files in {repo_path}")
        return files

    def get_repo_name(self, repo_url: str) -> str:
        """Extract repo name from URL."""
        return repo_url_to_name(repo_url)

    def repo_exists(self, repo_url: str) -> bool:
        """Check if a repo is already cloned."""
        return _get_repo_path(repo_url).exists()

    def get_git_hotspots(self, repo_path: Path, days: int = 90) -> dict[str, int]:
        """Get commit count per file over the last N days."""
        import subprocess
        hotspots = {}
        try:
            result = subprocess.run(
                ["git", "log", f"--since={days} days ago", "--name-only", "--format="],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    hotspots[line] = hotspots.get(line, 0) + 1
        except Exception as e:
            logger.warning(f"Failed to get git hotspots: {e}")
        return hotspots