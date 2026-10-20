from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_engine
from app.core.errors import error_response, install_error_handlers
from crud_database.routers import auth, profile
from machine_learning_recommendation_system.routers import recommendations, schools


def create_app():
    app = FastAPI(title="AkademikKita Backend", version="2.0.0")
    cors_origins = settings().cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for router in (auth.router, profile.router, schools.router, recommendations.router):
        app.include_router(router, prefix="/api")
    install_error_handlers(app)

    @app.get("/health", tags=["Operasional"])
    def health():
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            return error_response(503, "Database tidak terhubung")
        return {"success": True, "data": {"database": "connected"}, "message": "Backend berjalan"}

    return app


app = create_app()
