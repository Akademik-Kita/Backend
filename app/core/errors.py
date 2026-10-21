import logging

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


def error_response(status, message, headers=None):
    return JSONResponse(
        status_code=status,
        content={"success": False, "data": None, "message": message},
        headers=headers,
    )


def install_error_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_error(_, error):
        return error_response(error.status_code, str(error.detail), error.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, error):
        messages = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in error.errors()]
        return error_response(422, "; ".join(messages))

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_, error):
        # Log cukup jenis error; SQL dan parameternya bisa berisi data siswa.
        logger.error("Database failure: %s", type(error).__name__)
        return error_response(503, "Database belum siap atau operasi database gagal")

    @app.exception_handler(Exception)
    async def unexpected_error(_, error):
        logger.error("Unexpected failure: %s", type(error).__name__)
        return error_response(500, "Terjadi kesalahan internal")
