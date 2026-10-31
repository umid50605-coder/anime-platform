from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_user, get_watch_service
from app.models.user import User
from app.schemas.episode import StreamInfo
from app.schemas.watch import WatchHistoryEntry, WatchProgressRead, WatchProgressUpdate
from app.services.watch import (
    EpisodeNotFoundError,
    VideoFileNotFoundError,
    WatchService,
)

router = APIRouter()


@router.get("/{episode_id}/progress", response_model=WatchProgressRead)
def get_progress(
    episode_id: str,
    current_user: User = Depends(get_current_user),
    watch_service: WatchService = Depends(get_watch_service),
) -> WatchProgressRead:
    progress = watch_service.get_progress(current_user.id, episode_id)
    if progress is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No progress recorded yet"
        )
    return progress


@router.put("/{episode_id}/progress", response_model=WatchProgressRead)
def update_progress(
    episode_id: str,
    data: WatchProgressUpdate,
    current_user: User = Depends(get_current_user),
    watch_service: WatchService = Depends(get_watch_service),
) -> WatchProgressRead:
    try:
        return watch_service.update_progress(current_user.id, episode_id, data.position_seconds)
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/history", response_model=list[WatchHistoryEntry])
def get_history(
    current_user: User = Depends(get_current_user),
    watch_service: WatchService = Depends(get_watch_service),
) -> list[WatchHistoryEntry]:
    items = watch_service.list_history(current_user.id)
    return [
        WatchHistoryEntry(
            episode_id=item.episode_id,
            anime_id=item.anime_id,
            position_seconds=item.position_seconds,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/{episode_id}/content", name="get_stream_content")
def get_stream_content(
    episode_id: str,
    watch_service: WatchService = Depends(get_watch_service),
) -> FileResponse:
    """Public local video endpoint. FileResponse handles HTTP Range requests."""
    try:
        path = watch_service.get_stream_file_path(episode_id)
    except (EpisodeNotFoundError, VideoFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return FileResponse(path, media_type="video/mp4")


@router.get("/{episode_id}/stream", response_model=StreamInfo)
def get_stream(
    episode_id: str,
    request: Request,
    watch_service: WatchService = Depends(get_watch_service),
) -> StreamInfo:
    """Public - watching an episode never requires an account. See PROJECT_RULES.md."""
    try:
        stream = watch_service.get_stream(episode_id)
    except EpisodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    stream_url = stream.stream_url
    if stream.provider == "local":
        stream_url = str(
            request.url_for("get_stream_content", episode_id=episode_id)
        )

    return StreamInfo(stream_url=stream_url, provider=stream.provider)
