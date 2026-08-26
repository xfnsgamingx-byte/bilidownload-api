from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import yt_dlp
import os
import re
import uuid
import shutil
import tempfile
from urllib.parse import urlparse, urlencode


app = FastAPI(
    title="BiliDownload API",
    description="Bilibili media downloader for publicly accessible, non-DRM content"
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


API_BASE_URL = "https://bilidownload-api.onrender.com"


def validate_bilibili_url(url: str):

    try:

        parsed = urlparse(url)

        hostname = (
            parsed.hostname or ""
        ).lower()

    except Exception:

        return False


    allowed_domains = [
        "bilibili.com",
        "www.bilibili.com",
        "b23.tv"
    ]


    if hostname in allowed_domains:

        return True


    if hostname.endswith(".bilibili.com"):

        return True


    return False


def cleanup_folder(folder_path: str):

    try:

        if os.path.exists(folder_path):

            shutil.rmtree(
                folder_path,
                ignore_errors=True
            )

    except Exception:

        pass


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


    if not validate_bilibili_url(url):

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

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )


        formats = []


        seen = set()


        for f in info.get(
            "formats",
            []
        ):


            format_id = f.get(
                "format_id"
            )


            if not format_id:

                continue


            ext = (
                f.get("ext")
                or "mp4"
            )


            vcodec = (
                f.get("vcodec")
                or "none"
            )


            acodec = (
                f.get("acodec")
                or "none"
            )


            # सिर्फ ऐसे formats दिखाओ
            # जिनमें कम से कम video या audio मौजूद हो

            if (
                vcodec == "none" and
                acodec == "none"
            ):

                continue


            height = f.get(
                "height"
            )


            width = f.get(
                "width"
            )


            format_note = (
                f.get("format_note")
                or ""
            )


            # Media type

            if (
                vcodec == "none" and
                acodec != "none"
            ):

                media_type = "audio"

                quality = (
                    format_note
                    or f.get("abr")
                    or "Audio"
                )


            elif (
                vcodec != "none" and
                acodec == "none"
            ):

                media_type = "video_only"

                if height:

                    quality = (
                        str(height)
                        + "p Video"
                    )

                else:

                    quality = (
                        format_note
                        or "Video"
                    )


            else:

                media_type = "video"

                if height:

                    quality = (
                        str(height)
                        + "p"
                    )

                elif width:

                    quality = (
                        str(width)
                        + "px"
                    )

                else:

                    quality = (
                        format_note
                        or "Video"
                    )


            # Duplicate रोकने के लिए

            unique_key = (
                str(format_id)
                + "|"
                + str(ext)
                + "|"
                + str(vcodec)
                + "|"
                + str(acodec)
            )


            if unique_key in seen:

                continue


            seen.add(
                unique_key
            )


            # Render download endpoint का URL

            params = urlencode({

                "url": url,

                "format_id": format_id

            })


            download_url = (
                API_BASE_URL
                + "/api/download?"
                + params
            )


            formats.append({

                "format_id":
                    format_id,

                "quality":
                    quality,

                "ext":
                    ext,

                "filesize":
                    f.get("filesize"),

                "type":
                    media_type,

                "vcodec":
                    vcodec,

                "acodec":
                    acodec,

                "download_url":
                    download_url

            })


        return {

            "success": True,

            "title":
                info.get("title")
                or "Bilibili Video",

            "thumbnail":
                info.get("thumbnail"),

            "source_url":
                url,

            "formats":
                formats

        }


    except Exception:

        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to process this video. "
                "The content may be unavailable, restricted, "
                "or unsupported. Only publicly accessible, "
                "non-DRM content can be processed."
            )

        )


@app.get("/api/download")
def download_video(

    background_tasks: BackgroundTasks,

    url: str = Query(...),

    format_id: str = Query(...)

):


    url = url.strip()

    format_id = format_id.strip()


    if not validate_bilibili_url(url):

        raise HTTPException(

            status_code=400,

            detail="Invalid Bilibili URL."

        )


    if not format_id:

        raise HTTPException(

            status_code=400,

            detail="Invalid format."

        )


    download_folder = tempfile.mkdtemp(

        prefix="bilidownload_"

    )


    output_template = os.path.join(

        download_folder,

        "%(title).80s_%(id)s.%(ext)s"

    )


    try:


        # पहले video information लेकर
        # format_id को validate करेंगे

        info_opts = {

            "quiet": True,

            "no_warnings": True,

            "skip_download": True,

            "noplaylist": True

        }


        with yt_dlp.YoutubeDL(
            info_opts
        ) as ydl:

            info = ydl.extract_info(

                url,

                download=False

            )


        available_format_ids = {

            str(item.get("format_id"))

            for item in info.get(
                "formats",
                []
            )

            if item.get("format_id")

        }


        if format_id not in available_format_ids:

            cleanup_folder(
                download_folder
            )

            raise HTTPException(

                status_code=400,

                detail="This download format is no longer available."

            )


        # Selected format download

        download_opts = {

            "quiet": True,

            "no_warnings": True,

            "noplaylist": True,

            "format": format_id,

            "outtmpl": output_template,

            "restrictfilenames": True,

            "nopart": True

        }


        with yt_dlp.YoutubeDL(
            download_opts
        ) as ydl:


            downloaded_info = ydl.extract_info(

                url,

                download=True

            )


            file_path = ydl.prepare_filename(
                downloaded_info
            )


        # अगर expected filename नहीं मिला
        # तो folder में actual downloaded file ढूंढो

        if not os.path.exists(
            file_path
        ):


            files = []


            for filename in os.listdir(
                download_folder
            ):

                full_path = os.path.join(

                    download_folder,

                    filename

                )


                if os.path.isfile(
                    full_path
                ):

                    files.append(
                        full_path
                    )


            if files:

                file_path = files[0]


        if not os.path.exists(
            file_path
        ):

            cleanup_folder(
                download_folder
            )

            raise Exception(
                "Downloaded file could not be found."
            )


        filename = os.path.basename(
            file_path
        )


        # Response खत्म होने के बाद
        # temporary file delete होगा

        background_tasks.add_task(

            cleanup_folder,

            download_folder

        )


        return FileResponse(

            path=file_path,

            filename=filename,

            media_type="application/octet-stream",

            background=background_tasks

        )


    except HTTPException:

        raise


    except Exception:


        cleanup_folder(
            download_folder
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to download this format. "
                "The video may be restricted, expired, "
                "or temporarily unavailable."
            )

        )
