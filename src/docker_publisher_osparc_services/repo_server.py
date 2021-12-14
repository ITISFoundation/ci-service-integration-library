from .models import HostType, RepoModel
from .exceptions import BaseAppException
from .http_interface import github_did_last_repo_run_pass, gitlab_did_last_repo_run_pass


async def did_ci_pass(repo_model: RepoModel, branch_hash: str) -> bool:
    if repo_model.host_type == HostType.GITHUB:
        return await github_did_last_repo_run_pass(repo_model, branch_hash)

    if repo_model.host_type == HostType.GITLAB:
        return await gitlab_did_last_repo_run_pass(repo_model, branch_hash)

    raise BaseAppException("should not be here")
