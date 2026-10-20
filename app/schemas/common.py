from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")
Ownership = Literal["negeri", "swasta"]
DIMENSIONS = ("realistic", "investigative", "artistic", "social", "enterprising", "conventional")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str = ""


class ErrorEnvelope(BaseModel):
    success: Literal[False] = False
    data: None = None
    message: str


class InterestScores(StrictModel):
    realistic: float = Field(ge=0, le=100)
    investigative: float = Field(ge=0, le=100)
    artistic: float = Field(ge=0, le=100)
    social: float = Field(ge=0, le=100)
    enterprising: float = Field(ge=0, le=100)
    conventional: float = Field(ge=0, le=100)


def envelope(data, message=""):
    return {"success": True, "data": data, "message": message}
