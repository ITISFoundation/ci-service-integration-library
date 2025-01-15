import json
from asyncio import Lock
from collections import deque
from io import TextIOWrapper
from types import TracebackType
from typing import Deque, Dict, Optional, Tuple, Type

from pydantic import field_validator, BaseModel, Field

from .commands import CommandList
from .constants import GENERATED_PIPELINE_PATH, PIPELINE_CONFIGS
from .pipeline_writer import PipelineWriter

HEADER = "=" * 50


class PipelineConfig(BaseModel):
    target: str
    build: CommandList = Field(..., description="commands used to build the image")
    test: Optional[CommandList] = Field(
        None, description="optional stage where to add all tests and checks"
    )
    push: CommandList = Field(..., description="commands used to push the image")

    @field_validator("target")
    @classmethod
    def escape_name(cls, v):
        return f"{v}".replace("/", "-")

    def write_config(self) -> None:
        PIPELINE_CONFIGS.mkdir(parents=True, exist_ok=True)
        file = PIPELINE_CONFIGS / f"{self.target}.pipeline_config"
        file.write_text(json.dumps(self.dict()))


class PipelineGenerator:
    def __init__(self) -> None:
        self.child_gitlab_config: Optional[TextIOWrapper] = None

        self._lock = Lock()
        self._pipeline_info: Deque[Tuple[PipelineConfig, Dict[str, str]]] = deque()

    async def __aenter__(self):
        self.child_gitlab_config = open(GENERATED_PIPELINE_PATH, "w+")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ):
        if not self.child_gitlab_config:
            return None

        if len(self._pipeline_info) == 0:
            # write empty pipeline with a job that says ok
            self.child_gitlab_config.write(PipelineWriter.nothing_to_do_pipeline())
        else:
            self.child_gitlab_config.write(PipelineWriter.parent_job_template())
            for pipeline_config, env_vars in self._pipeline_info:
                pipeline_writer = PipelineWriter(pipeline_config, env_vars)

                assert self.child_gitlab_config

                self.child_gitlab_config.write(pipeline_writer.build_stage())

                if pipeline_config.test is not None:
                    self.child_gitlab_config.write(pipeline_writer.test_stage())

                self.child_gitlab_config.write(pipeline_writer.push_stage())

        self.child_gitlab_config.close()
        print(HEADER)
        print("GENERATED PIPELINE")
        print(HEADER)
        print(GENERATED_PIPELINE_PATH.read_text())
        print(HEADER)

    async def add_pipeline_from(
        self, pipeline_config: PipelineConfig, env_vars: Dict[str, str]
    ) -> None:
        async with self._lock:
            self._pipeline_info.append((pipeline_config, env_vars))
