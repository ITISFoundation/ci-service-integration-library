from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

import yaml

from .exceptions import BaseAppException, GITCommitHashInvalid
from .http_interface import (github_did_last_repo_run_pass,
                             gitlab_did_last_repo_run_pass)
from .models import HostType, RepoModel
from .utils import command_output


async def get_branch_hash(repo_model: RepoModel) -> str:
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


async def assemble_compose(repo_model: RepoModel) -> None:
    result = await command_output("ooil compose", cwd=f"{repo_model.clone_path}")
    print(result)


def fetch_images_from_compose_spec(repo_model: RepoModel) -> List[str]:
    assert repo_model.clone_path
    compose_file = repo_model.clone_path / "docker-compose.yml"
    parsed_spec = yaml.safe_load(compose_file.read_text())

    return [service_data["image"] for service_data in parsed_spec["services"].values()]


async def did_ci_pass(repo_model: RepoModel, branch_hash: str) -> bool:
    if repo_model.host_type == HostType.GITHUB:
        return await github_did_last_repo_run_pass(repo_model, branch_hash)

    if repo_model.host_type == HostType.GITLAB:
        return await gitlab_did_last_repo_run_pass(repo_model, branch_hash)

    raise BaseAppException("should not be here")
