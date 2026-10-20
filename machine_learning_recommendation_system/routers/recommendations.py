from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas import Envelope, ErrorEnvelope, GenerateRequest, RunOut, StudentContext
from machine_learning_recommendation_system.dependencies import get_student, get_student_id
from machine_learning_recommendation_system.services.recommendation import generate, latest

router = APIRouter(
    prefix="/recommendations",
    tags=["Rekomendasi"],
    responses={status: {"model": ErrorEnvelope} for status in (401, 404, 409, 422, 500, 503)},
)


@router.post("/generate", response_model=Envelope[RunOut])
def generate_recommendations(
    body: GenerateRequest | None = None,
    db: Session = Depends(get_db),
    student: StudentContext = Depends(get_student),
):
    request = body or GenerateRequest()
    data, message = generate(db, student, request.weights, settings().hard_filters)
    return {"data": data, "message": message}


@router.get("/latest", response_model=Envelope[RunOut])
def latest_recommendations(
    db: Session = Depends(get_db),
    student_id: UUID = Depends(get_student_id),
):
    data, message = latest(db, student_id)
    return {"data": data, "message": message}
