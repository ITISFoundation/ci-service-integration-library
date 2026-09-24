import httpx
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Mapping, Optional, Set, Tuple

from httpx import AsyncClient, Response, codes
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from yarl import URL

from .exceptions import (
    CouldNotFindAGitlabRepositoryRepoException,
    GithubRequestUnexpectedStatusCodeError,
    GithubRequestUnparseableJsonError,
    GitlabRequestUnexpectedStatusCodeError,
    GitlabRequestUnparseableJsonError,
    RegistryRepoNotFoundError,
    RegistryRequestUnexpectedStatusCodeError,
    RegistryRequestUnparseableJsonError,
    RegistryUnavailableError,
)
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


@retry(
    retry=retry_if_exception_type(
        (
            httpx.TransportError,
            GithubRequestUnexpectedStatusCodeError,
            GithubRequestUnparseableJsonError,
        )
    ),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _github_request(
    url: str, *, headers: Dict[str, str], params=None, expected_status: int = 200
) -> Tuple[Any, "Response"]:
    async with async_client() as client:
        result: Response = await client.get(url, params=params, headers=headers)
        if result.status_code != expected_status:
            raise GithubRequestUnexpectedStatusCodeError(
                url,
                result.status_code,
                expected_status,
                result.text,
            )
        try:
            return result.json(), result
        except ValueError as exc:
            raise GithubRequestUnparseableJsonError(
                url,
                result.status_code,
                result.headers.get("content-type", ""),
                result.text,
            ) from exc


async def github_did_last_repo_run_pass(
    repo_model: RepoModel, branch_hash: str
) -> bool:
    repo_path = repo_model.http_url_to_repo.split("github.com/")[1].replace(".git", "")
    url: Optional[str] = f"https://api.github.com/repos/{repo_path}/actions/runs"
    headers = {
        "Authorization": f"Bearer {repo_model.github.github_token.get_secret_value()}"
    }
    params = {"per_page": "10", "branch": repo_model.branch}
    associated_run: Optional[Dict[str, Any]] = None

    while url:
        # each page request is status-checked and retried on transient failures
        runs, result = await _github_request(url, headers=headers, params=params)
        # the first page used params; next links already contain them
        params = None

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


@retry(
    retry=retry_if_exception_type((GitlabRequestUnexpectedStatusCodeError, GitlabRequestUnparseableJsonError)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _gitlab_request(
    url: str, *, headers: Dict[str, str], expected_status: int = 200
) -> Any:
    async with async_client() as client:
        result: Response = await client.get(url, headers=headers)
        if result.status_code != expected_status:
            raise GitlabRequestUnexpectedStatusCodeError(
                url,
                result.status_code,
                expected_status,
                result.text,
            )
        try:
            return result.json()
        except ValueError as exc:
            raise GitlabRequestUnparseableJsonError(
                url,
                result.status_code,
                result.headers.get("content-type", ""),
                result.text,
            ) from exc


async def _gitlab_get_project_id(repo_model: RepoModel) -> str:
    parsed_url = URL(repo_model.address)
    repo_name = parsed_url.path.split("/")[-1].replace(".git", "")
    host = parsed_url.host
    url = f"https://{host}/api/v4/projects?search={repo_name}"
    headers = {
        "PRIVATE-TOKEN": repo_model.gitlab.personal_access_token.get_secret_value()
    }

    found_repos = await _gitlab_request(url, headers=headers)

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

    parsed_url = URL(repo_model.address)
    host = parsed_url.host
    url = f"https://{host}/api/v4/projects/{project_id}/pipelines?sha={branch_hash}"
    headers = {
        "PRIVATE-TOKEN": repo_model.gitlab.personal_access_token.get_secret_value()
    }

    found_pipelines = await _gitlab_request(url, headers=headers)

    # scan for the biggest pipeline id (most recent run)
    index_pipeline_id = [(k, x["id"]) for k, x in enumerate(found_pipelines)]
    max_pipeline_id_index_tuple = max(index_pipeline_id, key=lambda item: item[1])
    found_pipelines_index = max_pipeline_id_index_tuple[0]

    latest_run = found_pipelines[found_pipelines_index]
    return latest_run["status"] == "success"




# registry v2 error codes that unambiguously mean "this repository/manifest
# does not exist" as answered directly by the registry (not a gateway/proxy)
_REPO_MISSING_ERROR_CODES = {"NAME_UNKNOWN", "MANIFEST_UNKNOWN", "NOT_FOUND"}


def _is_registry_repo_missing_payload(body: Any) -> bool:
    """True only for a well-formed Docker Registry v2 error envelope reporting
    a missing repository/manifest. Flaky networks, timeouts, and proxy/gateway
    error pages never produce this structured payload."""
    if not isinstance(body, dict):
        return False
    errors = body.get("errors")
    if not isinstance(errors, list) or not errors:
        return False
    return any(
        isinstance(err, dict) and err.get("code") in _REPO_MISSING_ERROR_CODES
        for err in errors
    )


@retry(
    retry=retry_if_exception_type((
        httpx.TransportError,
        RegistryRequestUnexpectedStatusCodeError,
        RegistryRequestUnparseableJsonError,
    )),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _registry_raw_get(
    url: str,
    *,
    client: AsyncClient,
    auth=None,
    headers=None,
    acceptable_statuses: Set[int]
) -> Tuple[Optional[Any], Mapping[str, str]]:
    result: Response = await client.get(url, auth=auth, headers=headers)
    if result.status_code == codes.NOT_FOUND:
        # a 404 carrying the registry's own error envelope is a definitive
        # "repository does not exist (yet)" verdict, e.g. before an image's
        # first push -> raise a non-retried, explicitly-handled error instead
        try:
            error_payload = result.json()
        except ValueError:
            error_payload = None
        if _is_registry_repo_missing_payload(error_payload):
            raise RegistryRepoNotFoundError(url, result.text)
    if result.status_code not in acceptable_statuses:
        raise RegistryRequestUnexpectedStatusCodeError(
            url,
            result.status_code,
            result.text,
        )
    # don't attempt JSON parsing for non-OK responses (e.g. 401 Portus auth)
    if result.status_code != codes.OK:
        return None, result.headers
    try:
        return result.json(), result.headers
    except ValueError as exc:
        raise RegistryRequestUnparseableJsonError(
            url,
            result.status_code,
            result.headers.get("content-type", ""),
            result.text,
        ) from exc


async def _registry_request(
    registry_model: RegistryEndpointModel, url_path: str
) -> Dict[str, Any]:
    auth = (registry_model.user, registry_model.password.get_secret_value())
    async with async_client() as client:
        url = f"https://{registry_model.address}{url_path}"
        body, response_headers = await _registry_raw_get(
            url, client=client, auth=auth, acceptable_statuses={200, 401}
        )

        # in case of connection to Portus registry
        if body is None and "www-authenticate" in response_headers:
            www_authenticate = response_headers["www-authenticate"]

            bearer, params = www_authenticate.split(" ")
            assert bearer == "Bearer"
            token_params = {
                k: v.strip('"')
                for k, v in [x.split("=") for x in params.split(",")]
            }
            realm = token_params["realm"]
            scope = token_params["scope"]
            service = token_params["service"]
            token_url = f"{realm}?service={service}&scope={scope}"
            token_data, _ = await _registry_raw_get(
                token_url, client=client, auth=auth, acceptable_statuses={200}
            )
            if "token" not in token_data:
                raise RuntimeError(
                    f"Failed to obtain bearer token from {token_url!r}: "
                    f"response body: {token_data!r}"
                )

            token = token_data["token"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            body, _ = await _registry_raw_get(
                url, client=client, headers=auth_headers, acceptable_statuses={200}
            )
            return body or {}

        return body or {}


async def get_tags_for_repo(
    registry_model: RegistryEndpointModel, registry_path: str
) -> Set[str]:
    try:
        tags_result = await _registry_request(
            registry_model, url_path=f"/v2/{registry_path}/tags/list"
        )
    except RegistryRepoNotFoundError:
        # the registry itself confirms the repository does not exist yet
        # (typical for an image's very first push): that is a valid answer
        # meaning "no tags", so the caller can proceed to build & push,
        # which will create the repository on the registry
        print(
            f"[INFO] Repository '{registry_path}' does not exist on the "
            "registry yet, treating it as having no tags."
        )
        return set()
    except (
        httpx.TransportError,
        RegistryRequestUnexpectedStatusCodeError,
        RegistryRequestUnparseableJsonError,
        RuntimeError,
    ) as exc:
        print(f"[WARNING] {exc}")
        raise RegistryUnavailableError(registry_path, exc) from exc
    return set(tags_result.get("tags", []))
