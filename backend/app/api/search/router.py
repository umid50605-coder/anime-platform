from fastapi import APIRouter, Depends, Query

from app.api.deps import get_anime_service
from app.schemas.anime import AnimeSearchResult
from app.services.anime import AnimeService

router = APIRouter()


@router.get("/", response_model=list[AnimeSearchResult])
def search_anime(
    q: str = Query(..., min_length=1, description="Free-text search query"),
    anime_service: AnimeService = Depends(get_anime_service),
) -> list[AnimeSearchResult]:
    results = anime_service.search(q)
    return [
        AnimeSearchResult(
            external_id=r.external_id,
            title=r.title,
            slug=r.slug,
            poster_url=r.poster_url,
            synopsis=r.synopsis,
            genres=r.genres,
        )
        for r in results
    ]
