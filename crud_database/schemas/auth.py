from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import StrictModel


class RegisterIn(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    role: Literal["siswa", "orang_tua"]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.split("@", 1)[1] or " " in value:
            raise ValueError("Alamat email tidak valid")
        return value

    @field_validator("full_name")
    @classmethod
    def nonblank_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Nama wajib diisi")
        return value


class LoginIn(StrictModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str


class LoginOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    user: UserOut
