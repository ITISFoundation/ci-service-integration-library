import asyncio
from pathlib import Path

import click

from . import __version__
from .gitlab_ci_setup.commands import (
    COMMANDS_BUILD,
    COMMANDS_PUSH,
    COMMANDS_TEST_BASE,
    assemble_env_vars,
    validate_commands_list,
)
from .gitlab_ci_setup.pipeline_config import PipelineConfig, PipelineGenerator
from .http_interface import get_tags_for_repo
from .models import ConfigModel
from .operations import (
    assemble_compose,
    clone_repo,
    did_ci_pass,
    fetch_images_from_compose_spec,
    get_branch_hash,
)


async def run_command(config: Path) -> None:
    cfg = ConfigModel.from_cfg_path(config)
    print(cfg)

    # TODO: start in parallel??
    # yes to avoid issues with failing missconfigured repositories

    async with PipelineGenerator() as pipeline_generator:
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
                print(
                    f"Checking tag '{tag}' for '{image}' was pushed at '{remote_name}'. "
                    f"List of remote tags {[t for t in tags]}"
                )

                # if tag not in tags:
                if True:
                    print(f"Assembling pipeline for image {image}")
                    # write pipeline configuration here in the folder or append it as a result of this job
                    # just have some scripts to be generated with commands or something!
                    # how do I determine if there is a test stage?

                    # build commands validation
                    env_vars = assemble_env_vars(
                        repo_model, image_name, remote_name, tag
                    )
                    validate_commands_list(COMMANDS_BUILD, env_vars)

                    # check if test stage is required
                    test_commands = None
                    if repo_model.ci_stage_test_script is not None:
                        # test commands assembly and validation
                        test_commands = (
                            COMMANDS_TEST_BASE + repo_model.ci_stage_test_script
                        )
                        validate_commands_list(test_commands, env_vars)

                    # deploy stage validation
                    validate_commands_list(COMMANDS_PUSH, env_vars)

                    pipeline_config = PipelineConfig(
                        target=image_name,
                        build=COMMANDS_BUILD,
                        test=test_commands,
                        push=COMMANDS_PUSH,
                    )
                    pipeline_config.write_config()
                    await pipeline_generator.add_pipeline_from(
                        pipeline_config, env_vars
                    )
                else:
                    print(
                        f"No pipline will be generated, tag '{tag}' for image "
                        f"'{image}' already present."
                    )


@click.command()
@click.version_option(version=__version__)
@click.argument("config", type=Path)
def main(config: Path):
    """Interface to be used in CI"""
    asyncio.get_event_loop().run_until_complete(run_command(config))


if __name__ == "__main__":
    main()
