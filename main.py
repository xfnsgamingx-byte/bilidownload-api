from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse
import yt_dlp


app = FastAPI(
    title="BiliDownload API",
    description="Processor for publicly accessible, non-DRM Bilibili media"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class VideoRequest(BaseModel):
    url: str


def is_valid_bilibili_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())

        if parsed.scheme not in ("http", "https"):
            return False

        host = (parsed.hostname or "").lower()

        return (
            host == "bilibili.com"
            or host.endswith(".bilibili.com")
            or host == "b23.tv"
            or host.endswith(".b23.tv")
        )

    except Exception:
        return False


def human_size(size):
    if not size or size <= 0:
        return None

    units = ["B", "KB", "MB", "GB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"

        value /= 1024

    return None


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

    if not is_valid_bilibili_url(url):
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid Bilibili or b23.tv URL."
        )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": 20,
    }

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                url,
                download=False
            )

        if not info:
            raise HTTPException(
                status_code=422,
                detail="No media information was returned for this link."
            )

        formats = []
        seen = set()

        for item in info.get("formats", []):

            media_url = item.get("url")

            if not media_url:
                continue

            format_id = item.get("format_id")
            ext = item.get("ext") or "file"
            height = item.get("height")
            resolution = item.get("resolution")

            quality = (
                item.get("format_note")
                or (
                    f"{height}p"
                    if height else None
                )
                or resolution
                or format_id
                or "Available format"
            )

            filesize = (
                item.get("filesize")
                or item.get("filesize_approx")
            )

            key = (
                str(format_id),
                str(quality),
                str(ext)
            )

            if key in seen:
                continue

            seen.add(key)

            formats.append({
                "format_id": format_id,
                "quality": quality,
                "resolution": resolution,
                "ext": ext,
                "filesize": filesize,
                "filesize_text": human_size(filesize),
                "url": media_url,
                "vcodec": item.get("vcodec"),
                "acodec": item.get("acodec"),
                "width": item.get("width"),
                "height": height
            })

        return {
            "success": True,
            "title": info.get("title") or "Bilibili Video",
            "thumbnail": info.get("thumbnail"),
            "source_url": url,
            "formats": formats
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to process this video. The link may be unavailable, "
                "restricted, unsupported, or may not expose publicly "
                "accessible non-DRM media."
            )
        )
