from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.schemas.common import USERNAME_PATTERN


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserPublic(BaseModel):
    """Public representation of a user. Never includes password material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    created_at: datetime
