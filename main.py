from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import re
import os
import uuid
import shutil
import tempfile
import yt_dlp
import imageio_ffmpeg


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


# =========================================================
# VALIDATE BILIBILI URL
# =========================================================

def is_valid_bilibili_url(url: str):

    patterns = [
        r"(^|//)(www\.)?bilibili\.com/",
        r"(^|//)b23\.tv/"
    ]

    return any(
        re.search(pattern, url, re.IGNORECASE)
        for pattern in patterns
    )


# =========================================================
# CLEANUP TEMP FOLDER
# =========================================================

def cleanup_folder(folder):

    try:

        if os.path.exists(folder):

            shutil.rmtree(
                folder,
                ignore_errors=True
            )

    except Exception:

        pass


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "status": "ok",
        "message": "BiliDownload API is running"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# =========================================================
# PROCESS VIDEO
# =========================================================

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

        seen_formats = set()


        for f in info.get("formats", []):

            format_id = f.get("format_id")


            if not format_id:

                continue


            ext = f.get("ext") or "mp4"

            vcodec = f.get("vcodec") or "none"

            acodec = f.get("acodec") or "none"

            height = f.get("height")

            format_note = (
                f.get("format_note")
                or ""
            )


            # ---------------------------------------------
            # AUDIO ONLY
            # ---------------------------------------------

            if (
                vcodec == "none"
                and acodec != "none"
            ):

                media_type = "audio"

                quality = (
                    f.get("abr")
                    or format_note
                    or "Audio"
                )


                if isinstance(
                    quality,
                    (int, float)
                ):

                    quality = (
                        str(int(quality))
                        + " kbps"
                    )


                label = (
                    str(quality)
                    + " "
                    + ext.upper()
                )


            # ---------------------------------------------
            # VIDEO
            # ---------------------------------------------

            elif vcodec != "none":

                media_type = "video"


                if height:

                    quality = (
                        str(height)
                        + "p"
                    )

                else:

                    quality = (
                        f.get("resolution")
                        or format_note
                        or "Video"
                    )


                label = (
                    str(quality)
                    + " "
                    + "MP4"
                )


            else:

                continue


            # ---------------------------------------------
            # REMOVE DUPLICATES
            # ---------------------------------------------

            unique_key = (
                media_type
                + "_"
                + label
            )


            if unique_key in seen_formats:

                continue


            seen_formats.add(
                unique_key
            )


            formats.append({

                "format_id": format_id,

                "quality": quality,

                "ext": ext,

                "type": media_type,

                "filesize": f.get(
                    "filesize"
                ),

                "download_url": (
                    "https://bilidownload-api.onrender.com"
                    "/api/download"
                    "?url="
                    + url
                    + "&format_id="
                    + str(format_id)
                )

            })


        # SORT VIDEO FIRST

        formats.sort(

            key=lambda x: (

                0
                if x["type"] == "video"
                else 1

            )

        )


        return {

            "success": True,

            "title": info.get(
                "title"
            ),

            "thumbnail": info.get(
                "thumbnail"
            ),

            "source_url": url,

            "formats": formats

        }


    except Exception as e:

        print(
            "PROCESS ERROR:",
            str(e)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to process this video. "
                "The content may be unavailable, "
                "restricted, or unsupported."
            )

        )


# =========================================================
# DOWNLOAD AND MERGE VIDEO + AUDIO
# =========================================================

@app.get("/api/download")
def download_video(

    url: str,

    format_id: str,

    background_tasks: BackgroundTasks

):


    if not url or not format_id:

        raise HTTPException(

            status_code=400,

            detail=(
                "Missing video URL or format."
            )

        )


    if not is_valid_bilibili_url(url):

        raise HTTPException(

            status_code=400,

            detail=(
                "Invalid Bilibili URL."
            )

        )


    # -----------------------------------------------------
    # CREATE TEMP FOLDER
    # -----------------------------------------------------

    temp_folder = os.path.join(

        tempfile.gettempdir(),

        "bili_"
        + str(uuid.uuid4())

    )


    os.makedirs(

        temp_folder,

        exist_ok=True

    )


    try:


        # -------------------------------------------------
        # GET FFMPEG PATH
        # -------------------------------------------------

        ffmpeg_path = None


        try:

            ffmpeg_path = (
                imageio_ffmpeg.get_ffmpeg_exe()
            )

        except Exception as e:

            print(
                "FFMPEG ERROR:",
                str(e)
            )


        # -------------------------------------------------
        # GET VIDEO INFORMATION
        # -------------------------------------------------

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


        selected_format = None


        for f in info.get(
            "formats",
            []
        ):

            if str(
                f.get("format_id")
            ) == str(format_id):

                selected_format = f

                break


        if not selected_format:

            cleanup_folder(
                temp_folder
            )


            raise HTTPException(

                status_code=404,

                detail=(
                    "Selected format is no longer available."
                )

            )


        vcodec = (
            selected_format.get("vcodec")
            or "none"
        )


        acodec = (
            selected_format.get("acodec")
            or "none"
        )


        # -------------------------------------------------
        # SAFE FILENAME
        # -------------------------------------------------

        video_title = (
            info.get("title")
            or "bilibili_video"
        )


        safe_title = re.sub(

            r'[\\/*?:"<>|]',

            "_",

            video_title

        )


        # -------------------------------------------------
        # AUDIO DOWNLOAD
        # -------------------------------------------------

        if (
            vcodec == "none"
            and acodec != "none"
        ):


            output_template = os.path.join(

                temp_folder,

                "audio.%(ext)s"

            )


            ydl_opts = {

                "quiet": True,

                "no_warnings": True,

                "noplaylist": True,

                "format": format_id,

                "outtmpl": output_template

            }


            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                ydl.download(
                    [url]
                )


            downloaded_files = [

                os.path.join(
                    temp_folder,
                    f
                )

                for f in os.listdir(
                    temp_folder
                )

            ]


            if not downloaded_files:

                cleanup_folder(
                    temp_folder
                )


                raise HTTPException(

                    status_code=500,

                    detail=(
                        "Unable to download audio."
                    )

                )


            output_file = downloaded_files[0]


            extension = os.path.splitext(
                output_file
            )[1]


            final_name = (

                safe_title

                + extension

            )


        # -------------------------------------------------
        # VIDEO DOWNLOAD + BEST AUDIO + MERGE
        # -------------------------------------------------

        else:


            output_template = os.path.join(

                temp_folder,

                "video.%(ext)s"

            )


            ydl_opts = {

                "quiet": False,

                "no_warnings": False,

                "noplaylist": True,


                # SELECT VIDEO
                # + BEST AVAILABLE AUDIO

                "format": (

                    str(format_id)

                    + "+bestaudio"

                    + "/"

                    + str(format_id)

                    + "+bestaudio/best"
                ),


                "merge_output_format": "mp4",


                "outtmpl": output_template,


                "ffmpeg_location": ffmpeg_path

                if ffmpeg_path

                else None

            }


            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                ydl.download(
                    [url]
                )


            # -------------------------------------------------
            # FIND FINAL FILE
            # -------------------------------------------------

            downloaded_files = []


            for filename in os.listdir(
                temp_folder
            ):

                filepath = os.path.join(

                    temp_folder,

                    filename

                )


                if os.path.isfile(
                    filepath
                ):

                    if filename.lower().endswith(
                        ".mp4"
                    ):

                        downloaded_files.append(
                            filepath
                        )


            # IF MP4 NOT FOUND
            # TAKE ANY DOWNLOADED FILE

            if not downloaded_files:

                for filename in os.listdir(
                    temp_folder
                ):

                    filepath = os.path.join(

                        temp_folder,

                        filename

                    )


                    if os.path.isfile(
                        filepath
                    ):

                        downloaded_files.append(
                            filepath
                        )


            if not downloaded_files:

                cleanup_folder(
                    temp_folder
                )


                raise HTTPException(

                    status_code=500,

                    detail=(
                        "Unable to download "
                        "and merge video with audio."
                    )

                )


            output_file = (
                downloaded_files[0]
            )


            height = selected_format.get(
                "height"
            )


            quality_name = (

                str(height)

                + "p"

                if height

                else "video"

            )


            final_name = (

                safe_title

                + "_"

                + quality_name

                + ".mp4"

            )


        # -------------------------------------------------
        # DELETE TEMP FILES AFTER DOWNLOAD
        # -------------------------------------------------

        background_tasks.add_task(

            cleanup_folder,

            temp_folder

        )


        return FileResponse(

            path=output_file,

            media_type=(
                "video/mp4"

                if vcodec != "none"

                else "audio/mpeg"
            ),

            filename=final_name,

            background=background_tasks

        )


    except HTTPException:

        cleanup_folder(
            temp_folder
        )

        raise


    except Exception as e:


        print(
            "DOWNLOAD ERROR:",
            str(e)
        )


        cleanup_folder(
            temp_folder
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to download this format. "
                "The video may be restricted, "
                "expired, or temporarily unavailable."
            )

        )
