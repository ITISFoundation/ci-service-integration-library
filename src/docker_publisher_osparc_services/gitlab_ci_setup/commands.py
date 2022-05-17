import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

from ..models import RegistryEndpointyModel, RepoModel

CommandList = List[str]

DOCKER_LOGIN: str = (
    "echo ${SCCI_TARGET_REGISTRY_PASSWORD} | "
    "docker login ${SCCI_TARGET_REGISTRY_ADDRESS} --username ${SCCI_TARGET_REGISTRY_USER} --password-stdin"
)


def get_build_commands(image_count: int) -> CommandList:
    commands: CommandList = [
        "git clone ${SCCI_REPO} ${SCCI_CLONE_DIR}",
        "cd ${SCCI_CLONE_DIR}",
        "ooil compose",
        "docker-compose build",
        DOCKER_LOGIN,
    ]

    for k in range(image_count):
        commands.append(
            "docker tag ${SCCI_IMAGE_NAME_%s}:${SCCI_TAG} ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE_%s}:${SCCI_TAG}"
            % (k, k)
        )
        commands.append(
            "docker push ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE_%s}:${SCCI_TAG}"
            % (k)
        )

    return commands


def get_test_commands(image_count: int) -> CommandList:
    commands: CommandList = [
        "git clone ${SCCI_REPO} ${SCCI_CLONE_DIR}",
        "cd ${SCCI_CLONE_DIR}",
        DOCKER_LOGIN,
        "docker pull ${SCCI_CI_IMAGE_NAME}:${SCCI_TAG}",
    ]

    for k in range(image_count):
        commands.append("docker pull ${SCCI_CI_IMAGE_NAME_%s}:${SCCI_TAG}" % (k))

    return commands


def get_push_commands(image_count: int) -> CommandList:
    commands: CommandList = [
        DOCKER_LOGIN,
    ]

    for k in range(image_count):
        commands.append(
            "docker pull ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE_%s}:${SCCI_TAG}"
            % (k)
        )

        commands.append(
            "docker tag ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_TEST_IMAGE_%s}:${SCCI_TAG} ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_RELEASE_IMAGE_%s}:${SCCI_TAG}"
            % (k, k)
        )
        commands.append(
            "docker push ${SCCI_TARGET_REGISTRY_ADDRESS}/${SCCI_RELEASE_IMAGE_%s}:${SCCI_TAG}"
            % (k)
        )

    return commands


def assemble_env_vars(
    repo_model: RepoModel,
    registries: Dict[str, RegistryEndpointyModel],
    tag: str,
) -> Dict[str, str]:
    clone_directory: Path = Path(TemporaryDirectory().name)

    registry: RegistryEndpointyModel = registries[repo_model.registry.target]

    env_vars: Dict[str, str] = {
        "SCCI_REPO": repo_model.escaped_repo,
        "SCCI_CLONE_DIR": f"{clone_directory}",
        "SCCI_TAG": tag,
        "SCCI_TARGET_REGISTRY_ADDRESS": registry.address,
        "SCCI_TARGET_REGISTRY_PASSWORD": registry.password.get_secret_value(),
        "SCCI_TARGET_REGISTRY_USER": registry.user,
    }

    # for multiple image builds
    local_images: List[str] = list(repo_model.registry.local_to_test.keys())
    test_images: List[str] = list(repo_model.registry.local_to_test.values())
    release_images: List[str] = list(repo_model.registry.test_to_release.values())

    for k, image_name in enumerate(local_images):
        env_vars[f"SCCI_IMAGE_NAME_{k}"] = image_name

    for k, image_name in enumerate(test_images):
        env_vars[f"SCCI_TEST_IMAGE_{k}"] = image_name

    for k, image_name in enumerate(release_images):
        env_vars[f"SCCI_RELEASE_IMAGE_{k}"] = image_name

    return env_vars


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
