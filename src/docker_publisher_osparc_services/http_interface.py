from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Set

from httpx import AsyncClient, codes
from yarl import URL

from .exceptions import CouldNotFindAGitlabRepositoryRepoException
from .models import RegistryEndpointyModel, RepoModel


@asynccontextmanager
async def async_client(timeout: float = 30, **kwargs) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(timeout=timeout, **kwargs) as client:
        yield client


async def github_did_last_repo_run_pass(
    repo_model: RepoModel, branch_hash: str
) -> bool:
    async with async_client() as client:
        repo_path = repo_model.repo.split("github.com/")[1].replace(".git", "")
        url = f"https://api.github.com/repos/{repo_path}/actions/runs"
        result = await client.get(url, params={"per_page": "10"})
        runs = result.json()
        associated_run: Optional[Dict[str, Any]] = None
        for run in runs["workflow_runs"]:
            if run["head_commit"]["id"] == branch_hash:
                associated_run = run
                break
        if associated_run is None:
            raise Exception(f"Could not find associated run to commit {branch_hash}")

        return (
            associated_run["status"] == "completed"
            and associated_run["conclusion"] == "success"
        )


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
    registry_model: RegistryEndpointyModel, url_path: str
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
    registry_model: RegistryEndpointyModel, registry_path: str
) -> Set[str]:
    tags_result = await _registry_request(
        registry_model, url_path=f"/v2/{registry_path}/tags/list"
    )
    return set(tags_result.get("tags", []))
