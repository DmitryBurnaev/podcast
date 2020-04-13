import asyncio
import os
import re
import subprocess
from functools import partial
from typing import Optional, NamedTuple

import youtube_dl

import settings
from modules.youtube.exceptions import YoutubeExtractInfoError, FFMPegPreparationError
from modules.podcast.utils import get_file_size, episode_process_hook, EpisodeStatuses
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


def download_process_hook(event: dict):
    """
    Allows to handle processes of downloading episode's file.
    It is called by `youtube_dl.YoutubeDL`
    """
    total_bytes = event.get("total_bytes") or event.get("total_bytes_estimate", 0)
    episode_process_hook(
        status=EpisodeStatuses.episode_downloading,
        filename=event["filename"],
        total_bytes=total_bytes,
        processed_bytes=event.get("downloaded_bytes", total_bytes)
    )


def download_audio(youtube_link: str, filename: str) -> str:
    """ Download youtube video and perform to audio (.mp3) file

    :param youtube_link: URL to youtube video which are needed to download
    :param filename: autogenerated filename for episode
    :return result file name
    """
    params = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(settings.TMP_AUDIO_PATH, filename),
        "logger": get_logger("youtube_dl.YoutubeDL"),
        "progress_hooks": [download_process_hook],
    }
    with youtube_dl.YoutubeDL(params) as ydl:
        ydl.download([youtube_link])

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


def ffmpeg_preparation(filename: str):
    """ Ffmpeg allows to fix problem with length of audio track
        (in metadata value for this is incorrect, but fact length is fully correct)
    """

    logger.info(f"Start FFMPEG preparations for {filename} === ")
    episode_process_hook(
        status=EpisodeStatuses.episode_postprocessing,
        filename=filename,
        total_bytes=get_file_size(filename),
        processed_bytes=0
    )
    tmp_filename = os.path.join(settings.TMP_AUDIO_PATH, f"tmp_{filename}")
    result_filename = os.path.join(settings.TMP_AUDIO_PATH, filename)
    proc = subprocess.Popen(
        ["ffmpeg", "-i", result_filename, "-strict", "-2", "-y", tmp_filename]
    )
    outs, errs = proc.communicate(timeout=settings.FFMPEG_TIMEOUT)
    if outs:
        logger.info(outs)
    if errs:
        logger.error(errs)
        episode_process_hook(status=EpisodeStatuses.error, filename=filename)

    try:
        os.remove(result_filename)
        os.rename(tmp_filename, result_filename)
    except IOError as err:
        logger.exception("Failed to rename/remove tmp file after ffmpeg preparation")
        episode_process_hook(status=EpisodeStatuses.error, filename=filename)
        raise FFMPegPreparationError(err)

    total_file_size = get_file_size(result_filename)
    episode_process_hook(
        status=EpisodeStatuses.episode_postprocessing,
        filename=filename,
        total_bytes=total_file_size,
        processed_bytes=total_file_size,
    )
    logger.info("FFMPEG Preparation for %s was done", filename)
