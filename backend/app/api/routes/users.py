from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic, summary="Return the authenticated user's profile")
def read_current_user(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)
