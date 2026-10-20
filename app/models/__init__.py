from app.models.base import Base
from crud_database.models import (
    AcademicRecord,
    Achievement,
    InterestAssessment,
    StudentProfile,
    Subject,
    User,
)
from machine_learning_recommendation_system.models.recommendation import (
    RecommendationItem,
    RecommendationRun,
)
from machine_learning_recommendation_system.models.school import (
    AdmissionHistory,
    AdmissionTrack,
    Cost,
    Facility,
    Institution,
    Program,
    Region,
)

OWNED_TABLES = tuple(Base.metadata.sorted_tables)

__all__ = [
    "AcademicRecord",
    "Achievement",
    "InterestAssessment",
    "StudentProfile",
    "Subject",
    "User",
    "Base",
    "RecommendationItem",
    "RecommendationRun",
    "AdmissionHistory",
    "AdmissionTrack",
    "Cost",
    "Facility",
    "Institution",
    "Program",
    "Region",
    "OWNED_TABLES",
]
