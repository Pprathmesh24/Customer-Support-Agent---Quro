from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, conversations, ingest
from app.api.routes.admin import router as admin_router
from app.core.settings import settings

app = FastAPI(title="Enterprise Customer Support Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(admin_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
