from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_anime_service
from app.schemas.anime import AnimeDetail, AnimeRead
from app.services.anime import AnimeService

router = APIRouter()


@router.get("/", response_model=list[AnimeRead])
def list_catalog(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    anime_service: AnimeService = Depends(get_anime_service),
) -> list[AnimeRead]:
    return anime_service.list_catalog(offset=offset, limit=limit)


@router.post("/import/{external_id}", response_model=AnimeRead)
def import_anime(
    external_id: str,
    anime_service: AnimeService = Depends(get_anime_service),
) -> AnimeRead:
    try:
        anime = anime_service.import_from_provider(external_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return anime


@router.get("/{slug}", response_model=AnimeDetail)
def get_anime_detail(
    slug: str, anime_service: AnimeService = Depends(get_anime_service)
) -> AnimeDetail:
    result = anime_service.get_detail(slug)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found")
    return AnimeDetail(
        id=result.anime.id,
        slug=result.anime.slug,
        title=result.anime.title,
        poster_url=result.anime.poster_url,
        created_at=result.anime.created_at,
        synopsis=result.synopsis,
        genres=result.genres,
    )
