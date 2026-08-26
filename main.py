from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
import yt_dlp
import requests
from urllib.parse import quote


app = FastAPI(
    title="BiliDownload API",
    description="Bilibili video information and download service"
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


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "BiliDownload API is running"
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# --------------------------------------------------
# CHECK BILIBILI URL
# --------------------------------------------------

def is_valid_bilibili_url(url):

    patterns = [
        r"(^|//)(www\.)?bilibili\.com/",
        r"(^|//)b23\.tv/"
    ]

    return any(
        re.search(pattern, url, re.IGNORECASE)
        for pattern in patterns
    )


# --------------------------------------------------
# GET VIDEO INFORMATION
# --------------------------------------------------

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

            format_id = f.get("format_id")

            if not format_id:
                continue

            vcodec = f.get("vcodec")
            acodec = f.get("acodec")

            # खाली formats skip
            if not f.get("url"):
                continue

            # केवल useful formats
            quality = (
                f.get("format_note")
                or f.get("resolution")
                or f.get("height")
                or "Available format"
            )

            # अगर height है
            if isinstance(f.get("height"), int):

                if vcodec != "none" and acodec != "none":
                    quality = f"{f.get('height')}p MP4"

                elif vcodec != "none":
                    quality = f"{f.get('height')}p Video"

            # Audio format
            if vcodec == "none" and acodec != "none":

                quality = (
                    f.get("format_note")
                    or f"{f.get('abr', 'Audio')} kbps Audio"
                )

            formats.append({
                "format_id": format_id,
                "quality": str(quality),
                "ext": f.get("ext") or "mp4",
                "filesize": f.get("filesize")
                    or f.get("filesize_approx"),
                "height": f.get("height"),
                "vcodec": vcodec,
                "acodec": acodec,
                "has_video": vcodec != "none",
                "has_audio": acodec != "none"
            })


        # पहले अच्छे formats दिखाओ
        formats.sort(
            key=lambda x: (
                not (
                    x["has_video"]
                    and x["has_audio"]
                ),
                -(x["height"] or 0)
            )
        )


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


# --------------------------------------------------
# DOWNLOAD THROUGH SERVER
# --------------------------------------------------

@app.get("/api/download")
def download_video(

    url: str = Query(...),
    format_id: str = Query(...)

):

    url = url.strip()

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

            if str(f.get("format_id")) == str(format_id):

                selected_format = f
                break


        if not selected_format:

            raise HTTPException(
                status_code=404,
                detail="Selected format not found."
            )


        media_url = selected_format.get("url")


        if not media_url:

            raise HTTPException(
                status_code=404,
                detail="Download URL not available."
            )


        ext = selected_format.get("ext") or "mp4"


        title = info.get("title") or "video"


        # Filename clean करो
        filename = re.sub(
            r'[\\/*?:"<>|]',
            "",
            title
        )


        filename = filename[:100]


        filename = f"{filename}.{ext}"


        # yt-dlp द्वारा required headers
        headers = selected_format.get("http_headers") or {}

        headers.setdefault(
            "User-Agent",
            "Mozilla/5.0"
        )


        response = requests.get(

            media_url,

            headers=headers,

            stream=True,

            timeout=30
        )


        if response.status_code != 200:

            raise HTTPException(
                status_code=502,
                detail="Unable to fetch the media file."
            )


        content_type = (
            response.headers.get("Content-Type")
            or "application/octet-stream"
        )


        def generate():

            try:

                for chunk in response.iter_content(
                    chunk_size=1024 * 256
                ):

                    if chunk:

                        yield chunk

            finally:

                response.close()


        encoded_filename = quote(filename)


        return StreamingResponse(

            generate(),

            media_type=content_type,

            headers={

                "Content-Disposition":
                    f"attachment; filename*=UTF-8''{encoded_filename}",

                "Content-Length":
                    response.headers.get(
                        "Content-Length",
                        ""
                    )

            }

        )


    except HTTPException:

        raise


    except Exception:

        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to download this media. "
                "The temporary media link may have expired "
                "or the content may be restricted."
            )

        )
