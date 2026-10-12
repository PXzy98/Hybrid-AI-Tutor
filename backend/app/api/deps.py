from typing import Annotated

from fastapi import Depends, Request

from app.core.services import Services
from app.pipeline.runner import PipelineRunner


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_runner(request: Request) -> PipelineRunner:
    return request.app.state.runner


ServicesDep = Annotated[Services, Depends(get_services)]
RunnerDep = Annotated[PipelineRunner, Depends(get_runner)]
