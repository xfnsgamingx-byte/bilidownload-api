from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
import yt_dlp

app = FastAPI(
    title="BiliDownload API",
    description="Publicly accessible Bilibili media processor"
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

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True
    }

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        formats = []

        for f in info.get("formats", []):

            format_url = f.get("url")

            if not format_url:
                continue

            formats.append({
                "format_id": f.get("format_id"),
                "quality": f.get("format_note")
                    or f.get("resolution")
                    or "Available format",
                "ext": f.get("ext"),
                "filesize": f.get("filesize"),
                "url": format_url,
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec")
            })

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "source_url": url,
            "formats": formats
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to process this video. "
                "The content may be unavailable, restricted, "
                "or unsupported. Only publicly accessible, "
                "non-DRM content can be processed."
            )
        )
