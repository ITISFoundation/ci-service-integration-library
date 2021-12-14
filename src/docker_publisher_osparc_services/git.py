from pathlib import Path
from tempfile import TemporaryDirectory

from .models import RepoModel
from .exceptions import GITCommitHashInvalid
from .utils import command_output


async def get_branch_hash(repo_model: RepoModel) -> str:
    print(await command_output("env"))
    result = await command_output(
        f"git ls-remote {repo_model.repo} refs/heads/{repo_model.branch} -q",
    )
    # since multiple lines might be present in the output, fetch from the end
    commit_hash = result.split()[-2]
    if len(commit_hash) != 40:
        raise GITCommitHashInvalid(f"Commit hash {commit_hash} is not valid!")

    return commit_hash


async def clone_repo(repo_model: RepoModel) -> None:
    """clones and stores the cloned_dir"""
    target_dir: Path = Path(TemporaryDirectory().name)
    await command_output(f"git clone {repo_model.repo} {target_dir}")
    repo_model.clone_path = target_dir
