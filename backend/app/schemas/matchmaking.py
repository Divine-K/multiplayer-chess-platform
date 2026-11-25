import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PlayerColor


class TimeControlInfo(BaseModel):
    time_control_seconds: int
    increment_seconds: int
    label: str


class MatchmakingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_control_seconds: int = Field(ge=1, le=10_800)
    increment_seconds: int = Field(default=0, ge=0, le=60)


class MatchmakingResponse(BaseModel):
    status: Literal["idle", "queued", "matched"]
    game_id: uuid.UUID | None = None
    color: PlayerColor | None = None
    time_control_seconds: int | None = None
    increment_seconds: int | None = None
    queued_since: datetime | None = None
