from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Set

from httpx import AsyncClient, codes
from yarl import URL

from .exceptions import CouldNotFindAGitlabRepositoryRepoException
from .models import RegistryEndpointModel, RepoModel


@asynccontextmanager
async def async_client(timeout: float = 30, **kwargs) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(timeout=timeout, **kwargs) as client:
        yield client


class GreenCIMissingError(Exception):
    def __init__(self, *, repo_url: str, target_brach: str, branch_hash: str):
        super().__init__(
            f"Could not find a green CI run for {target_brach=} hash '{branch_hash}' in repository: {repo_url}. "
            "Please ensure that the repository has a passing CI run in its main"
        )


async def github_did_last_repo_run_pass(
    repo_model: RepoModel, branch_hash: str
) -> bool:
    async with async_client() as client:
        repo_path = repo_model.repo.split("github.com/")[1].replace(".git", "")
        url = f"https://api.github.com/repos/{repo_path}/actions/runs"
        headers = {"Authorization": f"Bearer {repo_model.github.github_token}"}
        params = {"per_page": "10", "branch": repo_model.branch}
        associated_run: Optional[Dict[str, Any]] = None

        while url:
            result = await client.get(url, params=params, headers=headers)
            runs = result.json()

            for run in runs.get("workflow_runs", []):
                if (
                    run["head_commit"]["id"] == branch_hash
                    and run["head_branch"] == repo_model.branch
                    and run["status"] == "completed"
                    and run["conclusion"] == "success"
                ):
                    associated_run = run
                    break

            if associated_run is not None:  # Branch hash found, exit the loop
                break

            url = result.links.get("next", {}).get("url")

        if associated_run is None:
            raise GreenCIMissingError(
                repo_url=repo_model.http_url_to_repo,
                target_brach=repo_model.branch,
                branch_hash=branch_hash,
            )

        return True


async def _gitlab_get_project_id(repo_model: RepoModel) -> str:
    async with async_client() as client:
        parsed_url = URL(repo_model.address)
        repo_name = parsed_url.path.split("/")[-1].replace(".git", "")
        host = parsed_url.host
        url = f"https://{host}/api/v4/projects?search={repo_name}"
        result = await client.get(
            url,
            headers={
                "PRIVATE-TOKEN": repo_model.gitlab.personal_access_token.get_secret_value()
            },
        )
        found_repos = result.json()
        # check for http_url_to_repo
        for repo in found_repos:
            if repo_model.http_url_to_repo == repo["http_url_to_repo"]:
                return repo["id"]

        message = f"Searching for {repo_name} did not yield the deisired result {found_repos} {parsed_url}"
        raise CouldNotFindAGitlabRepositoryRepoException(message)


async def gitlab_did_last_repo_run_pass(
    repo_model: RepoModel, branch_hash: str
) -> bool:
    project_id = await _gitlab_get_project_id(repo_model)

    async with async_client() as client:
        parsed_url = URL(repo_model.address)
        host = parsed_url.host
        url = f"https://{host}/api/v4/projects/{project_id}/pipelines?sha={branch_hash}"
        result = await client.get(
            url,
            headers={
                "PRIVATE-TOKEN": repo_model.gitlab.personal_access_token.get_secret_value()
            },
        )
        found_pipelines = result.json()

        # scan for the biggest pipeline id (most recent run)
        index_pipeline_id = [(k, x["id"]) for k, x in enumerate(found_pipelines)]
        max_pipeline_id_index_tuple = max(index_pipeline_id, key=lambda item: item[1])
        found_pipelines_index = max_pipeline_id_index_tuple[0]

        latest_run = found_pipelines[found_pipelines_index]
        return latest_run["status"] == "success"


async def _registry_request(
    registry_model: RegistryEndpointModel, url_path: str
) -> Dict[str, Any]:
    auth = (registry_model.user, registry_model.password.get_secret_value())
    async with async_client() as client:
        url = f"https://{registry_model.address}{url_path}"
        result = await client.get(url, auth=auth)

        # in case of connection to Portus registry
        if "www-authenticate" in result.headers:
            www_authenticate = result.headers["www-authenticate"]

            bearer, params = www_authenticate.split(" ")
            assert bearer == "Bearer"
            token_params = {
                k: v.strip('"') for k, v in [x.split("=") for x in params.split(",")]
            }
            realm = token_params["realm"]
            scope = token_params["scope"]
            service = token_params["service"]
            token_result = await client.get(
                f"{realm}?service={service}&scope={scope}", auth=auth
            )
            assert token_result.status_code == codes.OK

            token = token_result.json()["token"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            auth_result = await client.get(url, headers=auth_headers)
            if auth_result.status_code != codes.OK:
                print(f"[WARNING] auth request: {auth_result.text}")
                return {}
            return auth_result.json()
        else:
            if result.status_code != codes.OK:
                print(f"[WARNING] request: {result.text}")
                return {}
            return result.json()


async def get_tags_for_repo(
    registry_model: RegistryEndpointModel, registry_path: str
) -> Set[str]:
    tags_result = await _registry_request(
        registry_model, url_path=f"/v2/{registry_path}/tags/list"
    )
    return set(tags_result.get("tags", []))
