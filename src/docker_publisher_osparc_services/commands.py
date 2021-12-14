from typing import List

import yaml

from .models import RepoModel
from .utils import command_output


async def assemble_compose(repo_model: RepoModel) -> None:
    result = await command_output("ooil compose", cwd=f"{repo_model.clone_path}")
    print(result)


def fetch_images_from_compose_spec(repo_model: RepoModel) -> List[str]:
    assert repo_model.clone_path
    compose_file = repo_model.clone_path / "docker-compose.yml"
    parsed_spec = yaml.safe_load(compose_file.read_text())

    return [service_data["image"] for service_data in parsed_spec["services"].values()]


async def build_images(repo_model: RepoModel) -> None:
    result = await command_output(
        "docker-compose build", live_output=True, cwd=f"{repo_model.clone_path}"
    )
    print(result)


async def tag_and_push_image(image: str, remote_name: str, tag: str) -> None:
    result = await command_output(f"docker tag {image}:{tag} {remote_name}:{tag}")
    print(result)
    result = await command_output(f"docker push {remote_name}:{tag}")
    print(result)
