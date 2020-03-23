import asyncio
import os
import re
from functools import partial
from typing import Optional, NamedTuple

import youtube_dl

import settings
from modules.youtube.exceptions import YoutubeExtractInfoError
from modules.podcast.utils import get_file_name, download_process_hook
from common.utils import get_logger

logger = get_logger(__name__)


class YoutubeInfo(NamedTuple):
    """ Structure of extended information about youtube video """

    watch_url: str
    video_id: str
    description: str
    thumbnail_url: str
    title: str
    author: str
    length: int


def get_video_id(youtube_link: str) -> Optional[str]:
    matched_url = re.findall(r"(?:v=|/)([0-9A-Za-z_-]{11}).*", youtube_link)
    if not matched_url:
        logger.error(f"YouTube link is not correct: {youtube_link}")
        return None

    return matched_url[0]


def download_audio(youtube_link: str) -> str:
    """ Download youtube video and perform to audio (.mp3) file

    :param youtube_link: URL to youtube video which are needed to download
    :return result file name
    """

    logger.info(f"=== STARTED downloading for {youtube_link}")
    video_id = get_video_id(youtube_link)
    filename = get_file_name(video_id)
    params = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(
            settings.TMP_AUDIO_PATH, filename.replace("mp3", "%(ext)s")
        ),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "logger": get_logger("youtube_dl.YoutubeDL"),
        "progress_hooks": [download_process_hook],
    }
    with youtube_dl.YoutubeDL(params) as ydl:
        ydl.download([youtube_link])

    logger.info(f"=== DOWNLOAD process for {video_id} was done. Start uploading to the cloud")
    return filename


async def get_youtube_info(youtube_link: str) -> YoutubeInfo:
    """ Allows extract info about youtube video from Youtube webpage (powered by youtube_dl)"""

    logger.info(f"Started fetching data for {youtube_link}")
    loop = asyncio.get_running_loop()

    try:
        with youtube_dl.YoutubeDL({"logger": logger, "noplaylist": True}) as ydl:
            extract_info = partial(ydl.extract_info, youtube_link, download=False)
            youtube_details = await loop.run_in_executor(None, extract_info)

    except Exception as error:
        logger.exception(f"youtube.prefetch failed: {youtube_link} ({error})")
        raise YoutubeExtractInfoError(error)

    youtube_info = YoutubeInfo(
        title=youtube_details["title"],
        description=youtube_details["description"],
        watch_url=youtube_details["webpage_url"],
        video_id=youtube_details["id"],
        thumbnail_url=youtube_details["thumbnail"],
        author=youtube_details["uploader"],
        length=youtube_details["duration"],
    )
    return youtube_info


