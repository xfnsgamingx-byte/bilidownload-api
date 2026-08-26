from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re

app = FastAPI(
    title="BiliDownload API",
    description="Bilibili link validation API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VideoRequest(BaseModel):
    url: str


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "BiliDownload API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/api/process")
def process_video(data: VideoRequest):

    url = data.url.strip()

    if not url:
        raise HTTPException(
            status_code=400,
            detail="Please provide a Bilibili video URL."
        )

    bilibili_patterns = [
        r"(^|//)(www\.)?bilibili\.com/",
        r"(^|//)b23\.tv/"
    ]

    is_valid = any(
        re.search(pattern, url, re.IGNORECASE)
        for pattern in bilibili_patterns
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid Bilibili URL."
        )

    return {
        "success": True,
        "message": "Bilibili link received successfully.",
        "source_url": url,
        "downloads": [],
        "note": (
            "This API currently validates and receives the link. "
            "Download options can only be returned when publicly accessible, "
            "non-DRM media URLs are available to the server."
        )
    }
