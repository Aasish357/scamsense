import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.admin import router as admin_router
from .api.analysis import router as analysis_router
from .api.auth import router as auth_router
from .api.brand import router as brand_router
from .api.check import router as check_router
from .api.feedback import router as feedback_router
from .api.llm_analyze import router as llm_analyze_router
from .api.modalities import router as modalities_router
from .api.reports import router as reports_router
from .api.screenshot import router as screenshot_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)
app.include_router(check_router)
app.include_router(screenshot_router)
app.include_router(llm_analyze_router)
app.include_router(modalities_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(brand_router)
app.include_router(auth_router)
app.include_router(feedback_router)


@app.get("/")
async def root():
    return {"message": "Welcome to ScamSense API!"}


@app.get("/health")
@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
