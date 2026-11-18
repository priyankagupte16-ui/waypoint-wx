from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import Base, engine
from app.errors import AppError
from app.routes import router
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.4.1",
    description=f"Weather lookup API by {settings.author_name} for the PM Accelerator backend assessment.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error(request: Request, exc: AppError):
    body = {"error": exc.message}
    if exc.extra:
        body.update(exc.extra)
    return JSONResponse(status_code=exc.status, content=body)


app.include_router(router)
