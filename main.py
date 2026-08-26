from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
import yt_dlp


app = FastAPI(
    title="BiliDownload API",
    description="Bilibili media processor"
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


def is_valid_bilibili_url(url: str):

    patterns = [
        r"(^|//)(www\.)?bilibili\.com/",
        r"(^|//)b23\.tv/"
    ]

    return any(
        re.search(pattern, url, re.IGNORECASE)
        for pattern in patterns
    )


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
            detail="Please enter a valid Bilibili URL."
        )


    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extractor_args": {
            "bilibili": {
                "prefer_multi_flv": ["False"]
            }
        }
    }


    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )


        formats = []


        for f in info.get("formats", []):

            format_id = f.get("format_id")

            if not format_id:
                continue


            ext = f.get("ext") or "mp4"


            resolution = (
                f.get("resolution")
                or f.get("format_note")
                or ""
            )


            height = f.get("height")


            if height:

                quality = str(height) + "p"

            elif resolution:

                quality = resolution

            else:

                quality = (
                    f.get("format_note")
                    or "Available"
                )


            vcodec = f.get("vcodec") or "none"

            acodec = f.get("acodec") or "none"


            if vcodec == "none" and acodec != "none":

                media_type = "audio"

                quality_label = (
                    quality
                    if quality
                    else "Audio"
                )

            elif vcodec != "none":

                media_type = "video"

                quality_label = quality

            else:

                continue


            download_url = (
                "https://bilidownload-api.onrender.com"
                "/api/download"
                "?url=" + url
                + "&format_id=" + format_id
            )


            formats.append({
                "format_id": format_id,
                "quality": quality_label,
                "ext": ext,
                "type": media_type,
                "filesize": f.get("filesize"),
                "download_url": download_url
            })


        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "source_url": url,
            "formats": formats
        }


    except Exception:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to process this video. "
                "The content may be unavailable, restricted, "
                "or unsupported."
            )
        )


@app.get("/api/download")
def download_video(
    url: str,
    format_id: str
):

    if not url or not format_id:

        raise HTTPException(
            status_code=400,
            detail="Missing video URL or format."
        )


    if not is_valid_bilibili_url(url):

        raise HTTPException(
            status_code=400,
            detail="Invalid Bilibili URL."
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


        selected_format = None


        for f in info.get("formats", []):

            if str(
                f.get("format_id")
            ) == str(format_id):

                selected_format = f

                break


        if not selected_format:

            raise HTTPException(
                status_code=404,
                detail="Selected format is no longer available."
            )


        media_url = selected_format.get("url")


        if not media_url:

            raise HTTPException(
                status_code=404,
                detail="Download URL is not available."
            )


        import urllib.request


        request = urllib.request.Request(
            media_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com/"
            }
        )


        response = urllib.request.urlopen(
            request,
            timeout=30
        )


        filename = (
            "bilibili_"
            + str(format_id)
            + "."
            + (
                selected_format.get("ext")
                or "mp4"
            )
        )


        def generate():

            while True:

                chunk = response.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                yield chunk


        return StreamingResponse(

            generate(),

            media_type=(
                selected_format.get(
                    "mime_type"
                )
                or "application/octet-stream"
            ),

            headers={
                "Content-Disposition": (
                    'attachment; filename="' +
                    filename +
                    '"'
                )
            }

        )


    except HTTPException:

        raise


    except Exception:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to download this format. "
                "The video may be restricted, expired, "
                "or temporarily unavailable."
            )
        )
