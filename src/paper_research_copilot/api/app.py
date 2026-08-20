"""FastAPI application for asynchronous research tasks and SSE events."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from paper_research_copilot.agent import build_agent_runtime
from paper_research_copilot.api.models import (
    ClarificationResponse,
    HealthResponse,
    ResearchRequest,
    ResearchTaskAccepted,
    ResearchTaskView,
)
from paper_research_copilot.api.service import (
    ResearchTaskService,
    TaskClarificationError,
    TaskResumeError,
)
from paper_research_copilot.config import PROJECT_ROOT, Settings, get_settings
from paper_research_copilot.storage import (
    SqliteCheckpointStore,
    SqliteResearchRepository,
)

API_PREFIX = "/api/v1"
CORPUS_VERSION = 3
DEFAULT_COLLECTION = "agent_seed_v3_bge_m3_chunking_v1"
DEFAULT_FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"
RESERVED_FRONTEND_PREFIXES = frozenset({"api", "docs", "health", "openapi.json", "redoc"})


def create_app(
    *,
    task_service: ResearchTaskService | None = None,
    settings: Settings | None = None,
    frontend_dir: Path | None = DEFAULT_FRONTEND_DIR,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    if task_service is None:
        repository = SqliteResearchRepository(
            resolved_settings.resolved_app_database_path()
        )
        checkpoint_store = SqliteCheckpointStore(
            resolved_settings.resolved_checkpoint_database_path()
        )
        service = ResearchTaskService(
            lambda: build_agent_runtime(
                resolved_settings,
                version=CORPUS_VERSION,
                collection_name=DEFAULT_COLLECTION,
                checkpointer=checkpoint_store.saver,
                repository=repository,
            ),
            repository=repository,
            checkpoint_store=checkpoint_store,
        )
    else:
        service = task_service

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await asyncio.to_thread(service.close)

    application = FastAPI(
        title="Paper Research Copilot API",
        version="2.0.0",
        lifespan=lifespan,
    )
    application.state.task_service = service

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        runtime_ready, runtime_error = await asyncio.to_thread(service.probe_runtime)
        checkpoint_ready, checkpoint_error = service.probe_checkpoint()
        queued, running, completed = service.task_counts()
        return HealthResponse(
            status=(
                "ok"
                if runtime_ready
                and (service.task_store_name == "memory" or checkpoint_ready)
                else "degraded"
            ),
            runtime_ready=runtime_ready,
            runtime_error=runtime_error,
            corpus_version=CORPUS_VERSION,
            qdrant_collection=DEFAULT_COLLECTION,
            dynamic_qdrant_collection=resolved_settings.dynamic_qdrant_collection,
            dynamic_acquisition_enabled=(
                resolved_settings.agent_dynamic_acquisition_enabled
            ),
            claim_verification_enabled=(
                resolved_settings.agent_claim_verification_enabled
            ),
            task_store=service.task_store_name,
            checkpoint_ready=checkpoint_ready,
            checkpoint_error=checkpoint_error,
            queued_tasks=queued,
            running_tasks=running,
            completed_tasks=completed,
        )

    @application.post(
        f"{API_PREFIX}/research",
        response_model=ResearchTaskAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_research_task(payload: ResearchRequest) -> ResearchTaskAccepted:
        try:
            task = service.submit(payload.question)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        task_url = f"{API_PREFIX}/research/{task.task_id}"
        return ResearchTaskAccepted(
            task_id=task.task_id,
            status=task.status,
            created_at=task.created_at,
            task_url=task_url,
            events_url=f"{task_url}/events",
        )

    @application.get(
        f"{API_PREFIX}/research/{{task_id}}",
        response_model=ResearchTaskView,
    )
    async def get_research_task(task_id: str) -> ResearchTaskView:
        return _get_task_or_404(service, task_id)

    @application.post(
        f"{API_PREFIX}/research/{{task_id}}/resume",
        response_model=ResearchTaskAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def resume_research_task(task_id: str) -> ResearchTaskAccepted:
        _get_task_or_404(service, task_id)
        try:
            task = service.resume(task_id)
        except TaskResumeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        task_url = f"{API_PREFIX}/research/{task.task_id}"
        return ResearchTaskAccepted(
            task_id=task.task_id,
            status=task.status,
            created_at=task.created_at,
            task_url=task_url,
            events_url=f"{task_url}/events",
        )

    @application.post(
        f"{API_PREFIX}/research/{{task_id}}/clarify",
        response_model=ResearchTaskAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def clarify_research_task(
        task_id: str,
        payload: ClarificationResponse,
    ) -> ResearchTaskAccepted:
        _get_task_or_404(service, task_id)
        try:
            task = service.clarify(task_id, payload.response)
        except TaskClarificationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        task_url = f"{API_PREFIX}/research/{task.task_id}"
        return ResearchTaskAccepted(
            task_id=task.task_id,
            status=task.status,
            created_at=task.created_at,
            task_url=task_url,
            events_url=f"{task_url}/events",
        )

    @application.get(f"{API_PREFIX}/research/{{task_id}}/events")
    async def stream_research_events(
        request: Request,
        task_id: str,
        after: Annotated[int, Query(ge=0)] = 0,
    ) -> StreamingResponse:
        _get_task_or_404(service, task_id)

        async def event_stream() -> AsyncIterator[str]:
            cursor = after
            while True:
                if await request.is_disconnected():
                    return
                events, terminal = await asyncio.to_thread(
                    service.wait_for_events,
                    task_id,
                    cursor,
                    15.0,
                )
                if not events:
                    if terminal:
                        return
                    yield ": heartbeat\n\n"
                    continue
                for event in events:
                    cursor = event.sequence
                    yield (
                        f"id: {event.sequence}\n"
                        f"event: {event.event_type}\n"
                        f"data: {event.model_dump_json()}\n\n"
                    )
                if terminal:
                    return

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    if frontend_dir is not None:
        _mount_frontend(application, frontend_dir)

    return application


def _get_task_or_404(service: ResearchTaskService, task_id: str) -> ResearchTaskView:
    try:
        return service.get(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Research task not found") from exc


def _mount_frontend(application: FastAPI, frontend_dir: Path) -> None:
    """Serve a Vite production build without hiding invalid API requests."""
    root = frontend_dir.resolve()
    index_file = root / "index.html"
    if not index_file.is_file():
        return

    assets_dir = root / "assets"
    if assets_dir.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="frontend-assets",
        )

    @application.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(index_file)

    @application.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend_fallback(frontend_path: str) -> FileResponse:
        first_segment = frontend_path.split("/", maxsplit=1)[0]
        if first_segment in RESERVED_FRONTEND_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")

        requested_file = (root / frontend_path).resolve()
        try:
            requested_file.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not Found") from exc
        if requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(index_file)


def main() -> None:
    uvicorn.run(
        "paper_research_copilot.api.app:app",
        host="127.0.0.1",
        port=8000,
    )


app = create_app()
