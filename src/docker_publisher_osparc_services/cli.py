import asyncio
from pathlib import Path

import click

from . import __version__
from .http_interface import get_tags_for_repo
from .models import ConfigModel
from .operations import (
    assemble_compose,
    build_images,
    clone_repo,
    did_ci_pass,
    fetch_images_from_compose_spec,
    get_branch_hash,
    tag_and_push_image,
)


async def run_command(config: Path) -> None:
    cfg = ConfigModel.from_cfg_path(config)
    print(cfg)

    # TODO: start in parallel??
    # yes to avoid issues with failing missconfigured repositories
    for repo_model in cfg.repositories:
        branch_hash = await get_branch_hash(repo_model)
        target = f"'{repo_model.repo}@{repo_model.branch}#{branch_hash}'"

        if not await did_ci_pass(repo_model, branch_hash):
            print(f"CI FAILED for {target}, no build will be triggered!")
            continue

        print(f"CI OK for {target}")

        await clone_repo(repo_model)
        # invoke ooil to generate docker-compose.yml
        # extract tags from the images build in docker-compose.yaml
        # check if tags exist
        await assemble_compose(repo_model)
        images = fetch_images_from_compose_spec(repo_model)

        # check if image is present in repository
        for image in images:
            image_name, tag = image.split(":")
            if image_name not in repo_model.registry.local_to_remote:
                raise ValueError(
                    (
                        f"Image={image_name} expected to be defined in "
                        f"local_to_remote={repo_model.registry.local_to_remote}"
                    )
                )
            remote_name = repo_model.registry.local_to_remote[image_name]
            tags = await get_tags_for_repo(
                cfg.registries[repo_model.registry.target], remote_name
            )
            print(f"Built image '{image}' checking tags for '{remote_name}' {tags}")

            if tag not in tags:
                # write pipeline configuration here in the folder or append it as a result of this job
                # just have some scripts to be generated with commands or something!
                # how do I determine if there is a test stage?
                print(f"Will Assemble pipeline for {image}")
                # TODO: launch this as CI JOB
                await build_images(repo_model)
                # to build we git-clone, ooil-compose, docker-compose-build, push-for-next-stage
                await tag_and_push_image(image=image, remote_name=remote_name, tag=tag)
            else:
                print(f"Image already present, skipping pipeline for {image}")


@click.command()
@click.version_option(version=__version__)
@click.argument("config", type=Path)
def main(config: Path):
    """Interface to be used in CI"""
    asyncio.get_event_loop().run_until_complete(run_command(config))


if __name__ == "__main__":
    main()
