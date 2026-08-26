from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import re

app = FastAPI(title="BiliDownload API")

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
    return {"status": "healthy"}


@app.post("/api/process")
def process_video(data: VideoRequest):

    url = data.url.strip()

    if not url:
        raise HTTPException(
            status_code=400,
            detail="Please provide a video URL."
        )

    bilibili_patterns = [
        r"bilibili\.com",
        r"b23\.tv"
    ]

    if not any(re.search(pattern, url, re.IGNORECASE) for pattern in bilibili_patterns):
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid Bilibili URL."
        )

    return {
        "success": True,
        "message": "Valid Bilibili link received.",
        "source_url": url,
        "note": "Media processing for publicly accessible, non-DRM content will be added to this endpoint."
    }
