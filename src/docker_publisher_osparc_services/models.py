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
    local_to_test: Dict[str, str] = Field(
        ...,
        description="mapping between: `local build` image and `remote test` image",
        example={
            "simcore/services/dynamic/jupyter-math": "ci/builder/osparc-sparc-internal/master/jupyter-math"
        },
    )
    test_to_release: Dict[str, str] = Field(
        ...,
        description="mapping between: `remote test` image test image and `remote release` image",
        example={
            "ci/builder/osparc-sparc-internal/master/jupyter-math": "ci/osparc-sparc-internal/master/jupyter-math"
        },
    )

    @root_validator()
    def validate_consistency(cls, values: Dict) -> Dict:
        local_to_test = values["local_to_test"]
        test_to_release = values["test_to_release"]
        if len(local_to_test) != len(test_to_release):
            raise ValueError(
                f"Following dicts should have the same entry count {local_to_test=}, {test_to_release=}"
            )

        for test_image in local_to_test.values():
            if test_image not in test_to_release:
                raise ValueError(
                    f"Expected {test_image=} to be found in {test_to_release=}"
                )

        return values


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
    ci_stage_test_script: Optional[List[str]] = Field(
        None,
        description=(
            "if present it will enable the test stage and will execute the commands"
            "in sequence after cloning the repo and changing the directory to the"
            "clone location"
        ),
    )

    @root_validator()
    def require_access_token_for_gitlab(cls, values):
        if values["host_type"] == HostType.GITLAB and values["gitlab"] is None:
            raise ValueError(
                f"Provide a valid 'gitlab' field for {HostType.GITLAB} repo"
            )
        return values

    def _format_repo(
        self, escape_credentials: bool = False, strip_credentials: bool = False
    ) -> str:
        if self.gitlab is None:
            return self.address

        user = self.gitlab.deploy_token_username
        password = self.gitlab.deploy_token_password
        if user is None or password is None:
            return self.address

        clear_password = password.get_secret_value()
        if escape_credentials:
            user = user.replace("@", "%40")
            clear_password = clear_password.replace("@", "%40")

        protocol, url = self.address.split("://")

        if strip_credentials:
            return f"{protocol}://{url}"
        else:
            return f"{protocol}://{user}:{clear_password}@{url}"

    @property
    def repo(self) -> str:
        return self._format_repo(escape_credentials=False)

    @property
    def escaped_repo(self) -> str:
        return self._format_repo(escape_credentials=True)

    @property
    def http_url_to_repo(self) -> str:
        return self._format_repo(strip_credentials=True)


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
