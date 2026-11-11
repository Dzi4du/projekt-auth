from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


Role = Literal["user", "admin"]


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    role: Role
    created_at: datetime


# ----------------------- zarządzanie użytkownikami -------------------------
class ProfileIn(BaseModel):
    display_name: str | None = Field(max_length=100)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailChangeIn(BaseModel):
    new_email: EmailStr
    current_password: str


class RoleIn(BaseModel):
    role: Role


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class NoteOut(BaseModel):
    id: int
    content: str
    created_at: datetime
