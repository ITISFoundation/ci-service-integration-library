from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from envyaml import EnvYAML
from pydantic import BaseModel, Field, SecretStr, root_validator


class HostType(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"


class RegistryEndpointyModel(BaseModel):
    address: str
    user: str
    password: SecretStr


class ImageSrcDstModel(BaseModel):
    local_name: str
    remote_name: str


class RegistryTargetModel(BaseModel):
    target: str
    local_to_remote: Dict[str, str] = Field(
        ...,
        description="mapping between locally built image name and remote name in registry",
        example={
            "simcore/services/dynamic/jupyter-math": "ci/osparc-sparc-internal/master/jupyter-math"
        },
    )


class GitLabModel(BaseModel):
    personal_access_token: SecretStr
    deploy_token_username: str
    deploy_token_password: SecretStr


class RepoModel(BaseModel):
    address: str = Field(..., description="clone address https")
    gitlab: Optional[GitLabModel] = Field(
        None, description="GitLab credentials to clone and access the v4 API"
    )
    branch: str
    host_type: HostType
    registry: RegistryTargetModel
    clone_path: Optional[Path] = Field(
        None, description="Used internally to specify directory where to clone"
    )

    @root_validator()
    def require_access_token_for_gitlab(cls, values):
        if values["host_type"] == HostType.GITLAB and values["gitlab"] is None:
            raise ValueError(
                f"Provide a valid 'gitlab' field for {HostType.GITLAB} repo"
            )
        return values

    @property
    def repo(self) -> str:
        if self.gitlab is None:
            return self.address

        user = self.gitlab.deploy_token_username
        password = self.gitlab.deploy_token_password
        if user is None or password is None:
            return self.address

        protocol, url = self.address.split("://")
        return f"{protocol}://{user}:{password.get_secret_value()}@{url}"


class ConfigModel(BaseModel):
    registries: Dict[str, RegistryEndpointyModel]
    repositories: List[RepoModel]

    @root_validator()
    @classmethod
    def check_registry_target_defined(cls, values: Dict) -> Dict:
        registries: Dict[str, RegistryEndpointyModel] = values["registries"]
        repositories: List[RepoModel] = values["repositories"]
        for repo in repositories:
            if repo.registry.target not in registries:
                raise ValueError(
                    f"Repo {repo}:\n- registry.target={repo.registry.target} not found in registries={registries}"
                )
        return values

    @classmethod
    def from_cfg_path(cls, config_path: Path) -> "ConfigModel":
        config_dict = EnvYAML(config_path)
        return cls.parse_obj(config_dict)
