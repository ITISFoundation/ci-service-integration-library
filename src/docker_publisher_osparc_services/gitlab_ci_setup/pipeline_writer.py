from textwrap import dedent
from typing import Dict

from .commands import CommandList

TAB_SPACE = "                    "


def _format_template(template: str) -> str:
    return dedent(template)


class PipelineWriter:
    def __init__(
        self, pipeline_config: "PipelineConfig", env_vars: Dict[str, str]
    ) -> None:
        self.pipeline_config = pipeline_config
        self.env_vars: Dict[str, str] = env_vars

    @property
    def build_name(self) -> str:
        return f"{self.pipeline_config.target}-build"

    @property
    def test_name(self) -> str:
        return f"{self.pipeline_config.target}-test"

    @property
    def push_name(self) -> str:
        return f"{self.pipeline_config.target}-push"

    @property
    def formatted_env(self) -> str:
        return "\n".join(
            [""] + [f"{TAB_SPACE}{k}: {v}" for k, v in self.env_vars.items()]
        )

    @staticmethod
    def _format_commands(commands: CommandList) -> str:
        return "\n".join([""] + [f"{TAB_SPACE}- {command}" for command in commands])

    @staticmethod
    def nothing_to_do_pipeline() -> str:
        """Used when no checks are requured"""
        return _format_template(
            """
            stages:
                - info

            no-further-action-required:
                image: $CI_SERVICE_INTEGRATION_LIBRARY
                tags:
                stage: info
                tags:
                    - DOCKER_Xmodern
                script:
                    - echo "Nothing required updates. No builds scheduled."
            """
        )

    @staticmethod
    def parent_job_template() -> str:
        """This is globally shared between all jobs"""
        return _format_template(
            """
            stages:
                - build-image
                - test-image
                - deploy-image
            .basic:
                image: $CI_SERVICE_INTEGRATION_LIBRARY
                tags:
                    - DOCKER_Xmodern
            """
        )

    def build_stage(self) -> str:
        formatted_commands = self._format_commands(self.pipeline_config.build)
        return _format_template(
            f"""
            {self.build_name}:
                extends: .basic
                stage: build-image
                variables: {self.formatted_env}
                script: {formatted_commands}
            """
        )

    def test_stage(self) -> str:
        assert self.pipeline_config.test
        formatted_commands = self._format_commands(self.pipeline_config.test)
        return _format_template(
            f"""
            {self.test_name}:
                extends: .basic
                stage: test-image
                needs: [{self.build_name}]
                variables: {self.formatted_env}
                script: {formatted_commands}
            """
        )

    def push_stage(self) -> str:
        needs_entry = (
            self.build_name if self.pipeline_config.test is None else self.test_name
        )
        formatted_commands = self._format_commands(self.pipeline_config.push)
        return _format_template(
            f"""
            {self.push_name}:
                extends: .basic
                stage: deploy-image
                needs: [{needs_entry}]
                variables: {self.formatted_env}
                script: {formatted_commands}
            """
        )
