import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

from ..models import RegistryEndpointModel, RepoModel

DOCKER_LOGIN: str = (
    "echo ${SCCI_TARGET_REGISTRY_PASSWORD} | "
    "docker login ${SCCI_TARGET_REGISTRY_ADDRESS} --username ${SCCI_TARGET_REGISTRY_USER} --password-stdin"
)

CommandList = List[str]


def get_commands_build_base(
    pre_docker_build_hooks: list[str], legacy_escape: bool
) -> CommandList:
    return (
        [
            "git clone --single-branch --branch ${SCCI_BRANCH} ${SCCI_REPO} ${SCCI_CLONE_DIR}",
            "cd ${SCCI_CLONE_DIR}",
            DOCKER_LOGIN,
        ]
        + (["ooil legacy-escape"] if legacy_escape else [])
        + [
            "ooil compose",
            *pre_docker_build_hooks,
            "docker compose build",
            "docker tag ${SCCI_IMAGE_NAME}:${SCCI_TAG} ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE}:${SCCI_TAG}",
            "docker push ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE}:${SCCI_TAG}",
        ]
    )


def get_commands_test_base() -> CommandList:
    return [
        "git clone --single-branch --branch ${SCCI_BRANCH} ${SCCI_REPO} ${SCCI_CLONE_DIR}",
        "cd ${SCCI_CLONE_DIR}",
        DOCKER_LOGIN,
        "docker pull ${SCCI_CI_IMAGE_NAME}:${SCCI_TAG}",
        # if user defines extra commands those will be append here
    ]


def get_commands_push() -> CommandList:
    return [
        DOCKER_LOGIN,
        "docker pull ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE}:${SCCI_TAG}",
        "docker tag ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE}:${SCCI_TAG} ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_RELEASE_IMAGE}:${SCCI_TAG}",
        "docker push ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_RELEASE_IMAGE}:${SCCI_TAG}",
    ]


def assemble_env_vars(
    repo_model: RepoModel,
    registries: Dict[str, RegistryEndpointModel],
    image_name: str,
    tag: str,
) -> Dict[str, str]:
    clone_directory: Path = Path(TemporaryDirectory().name)

    registry: RegistryEndpointModel = registries[repo_model.registry.target]
    test_image = repo_model.registry.local_to_test[image_name]
    release_image = repo_model.registry.test_to_release[test_image]

    return {
        "SCCI_BRANCH": repo_model.branch,
        "SCCI_REPO": repo_model.escaped_repo,
        "SCCI_CLONE_DIR": f"{clone_directory}",
        "SCCI_IMAGE_NAME": image_name,
        "SCCI_TAG": tag,
        "SCCI_TEST_IMAGE": test_image,
        "SCCI_RELEASE_IMAGE": release_image,
        "SCCI_TARGET_REGISTRY_ADDRESS": registry.address,
        "SCCI_TARGET_REGISTRY_PASSWORD": registry.password.get_secret_value(),
        "SCCI_TARGET_REGISTRY_USER": registry.user,
    }


def validate_commands_list(
    commands_list: CommandList, env_vars: Dict[str, str]
) -> None:
    """validation is run at runtime before assembling the gitlab ci spec"""
    for command in commands_list:
        hits = re.findall(r"\$\{(.*?)\}", command)
        for hit in hits:
            if hit.startswith("SCCI") and hit not in env_vars:
                raise ValueError(
                    f"env var '{hit}'\ndefined in '{command}'\n "
                    f"not found default injected env vars '{env_vars}'"
                )
