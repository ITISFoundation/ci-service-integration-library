import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

from ..models import RegistryEndpointyModel, RepoModel

PREFIX = "SCCI"  # short for simcore ci

CommandList = List[str]

COMMANDS_BUILD: CommandList = [
    "git clone ${SCCI_REPO} ${SCCI_CLONE_DIR}",
    "cd ${SCCI_CLONE_DIR}",
    "ooil compose",
    "docker-compose build",
    "docker tag ${SCCI_IMAGE_NAME}:${SCCI_TAG} ${SCCI_REMOTE_BUILD_REGISTRY}:${SCCI_TAG}",
    "docker push ${SCCI_REMOTE_BUILD_REGISTRY}:${SCCI_TAG}",
]

COMMANDS_TEST_BASE: CommandList = [
    "git clone ${SCCI_REPO} ${SCCI_CLONE_DIR}",
    "cd ${SCCI_CLONE_DIR}",
    "docker pull ${SCCI_REMOTE_BUILD_REGISTRY}:${SCCI_TAG}",
    # if user defines extra commands those will be appended here
]

COMMANDS_PUSH: CommandList = [
    "docker pull ${SCCI_REMOTE_BUILD_REGISTRY}:${SCCI_TAG}",
    "docker tag ${SCCI_REMOTE_BUILD_REGISTRY}:${SCCI_TAG} ${SCCI_REMOTE_DEPLOY_REGISTRY}:${SCCI_TAG}",
    "docker push ${SCCI_REMOTE_DEPLOY_REGISTRY}:${SCCI_TAG}",
]


def assemble_env_vars(
    registry_model: RegistryEndpointyModel,
    repo_model: RepoModel,
    image_name: str,
    remote_deploy_name: str,
    remote_build_name: str,
    tag: str,
) -> Dict[str, str]:
    clone_directory: Path = Path(TemporaryDirectory().name)

    return {
        f"{PREFIX}_REPO": repo_model.repo,
        f"{PREFIX}_CLONE_DIR": f"{clone_directory}",
        f"{PREFIX}_IMAGE_NAME": image_name,
        f"{PREFIX}_TAG": tag,
        f"{PREFIX}_CI_IMAGE_REGISTRY": f"ci-test/{image_name}",
        f"{PREFIX}_REMOTE_DEPLOY_REGISTRY": f"{registry_model.address}/{remote_deploy_name}",
        f"{PREFIX}_REMOTE_BUILD_REGISTRY": f"{registry_model.address}/{remote_build_name}",
    }


def validate_commands_list(
    commands_list: CommandList, env_vars: Dict[str, str]
) -> None:
    """validation is run at runtime before assembling the gitlab ci spec"""
    for command in commands_list:
        hits = re.findall(r"\$\{(.*?)\}", command)
        for hit in hits:
            if hit.startswith(PREFIX) and hit not in env_vars:
                raise ValueError(
                    f"env var '{hit}'\ndefined in '{command}'\n "
                    f"not found default injected env vars '{env_vars}'"
                )
