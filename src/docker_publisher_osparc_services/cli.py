import asyncio
from pathlib import Path

import click

from . import __version__
from .gitlab_ci_setup.commands import (
    assemble_env_vars,
    get_commands_test_base,
    get_commands_push,
    get_commands_build_base,
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


async def run_command(config: Path, legacy_escape: bool) -> None:
    cfg = ConfigModel.from_cfg_path(config)
    print(cfg)

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

                if image_name in repo_model.registry.skip_images:
                    print(
                        f"Skipping {image_name}, used as a dependency by other images"
                    )
                    continue

                if image_name not in repo_model.registry.local_to_test:
                    raise ValueError(
                        (
                            f"Image={image_name} expected to be defined in "
                            f"local_to_test={repo_model.registry.local_to_test}"
                        )
                    )
                test_name = repo_model.registry.local_to_test[image_name]
                release_name = repo_model.registry.test_to_release[test_name]
                tags = await get_tags_for_repo(
                    cfg.registries[repo_model.registry.target], release_name
                )
                print(
                    f"Checking tag '{tag}' for '{image}' was pushed at '{release_name}'. "
                    f"List of remote tags {[t for t in tags]}"
                )

                if tag not in tags:
                    print(f"Assembling pipeline for image {image}")
                    # write pipeline configuration here in the folder or append it as a result of this job
                    # just have some scripts to be generated with commands or something!
                    # how do I determine if there is a test stage?

                    # build commands validation
                    env_vars = assemble_env_vars(
                        repo_model=repo_model,
                        image_name=image_name,
                        registries=cfg.registries,
                        tag=tag,
                    )

                    build_commands = get_commands_build_base(
                        repo_model.pre_docker_build_hooks, legacy_escape
                    )
                    validate_commands_list(build_commands, env_vars)

                    # check if test stage is required
                    test_commands = None
                    if repo_model.ci_stage_test_script is not None:
                        # test commands assembly and validation
                        test_commands = (
                            get_commands_test_base() + repo_model.ci_stage_test_script
                        )
                        validate_commands_list(test_commands, env_vars)

                    # deploy stage validation
                    push_commands = get_commands_push()
                    validate_commands_list(push_commands, env_vars)

                    pipeline_config = PipelineConfig(
                        target=image_name,
                        build=build_commands,
                        test=test_commands,
                        push=push_commands,
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
@click.option(
    "--legacy-escape",
    is_flag=True,
    default=False,
    help="Enable legacy escape for ooil commands.",
)
def main(config: Path, legacy_escape: bool = False) -> None:
    """Interface to be used in CI"""
    asyncio.get_event_loop().run_until_complete(run_command(config, legacy_escape))


if __name__ == "__main__":
    main()
