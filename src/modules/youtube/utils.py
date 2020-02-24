import asyncio
import os
import re
from functools import partial
from typing import Optional, Iterable, NamedTuple

import youtube_dl

import settings
from modules.youtube.exceptions import YoutubeExtractInfoError
from modules.podcast.models import Episode
from common.utils import get_logger
from common.redis import RedisClient

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


def get_file_name(video_id: str) -> str:
    return f"{video_id}.mp3"


def get_file_size(file_name):
    try:
        full_path = os.path.join(settings.RESULT_AUDIO_PATH, file_name)
        return os.path.getsize(full_path)
    except FileNotFoundError:
        logger.info("File %s not found. Return size 0", file_name)
        return 0


def get_video_id(youtube_link: str) -> Optional[str]:
    matched_url = re.findall(r"(?:v=|/)([0-9A-Za-z_-]{11}).*", youtube_link)
    if not matched_url:
        logger.error(f"YouTube link is not correct: {youtube_link}")
        return None

    return matched_url[0]


def download_process_hook(event: dict):
    """
    Allows to handle processes of downloading and performing episode's file.
    It is called by `youtube_dl.YoutubeDL`
    """
    redis_client = RedisClient()
    filename = os.path.basename(event["filename"])
    event_key = redis_client.get_key_by_filename(filename)
    total_bytes = event.get("total_bytes") or event.get("total_bytes_estimate", 0)
    event_data = {
        "event_key": event_key,
        "status": event["status"],
        "processed_bytes": event.get("processed_bytes", total_bytes),
        "total_bytes": total_bytes,
    }
    redis_client.set(event_key, event_data, ttl=settings.DOWNLOAD_EVENT_REDIS_TTL)


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
            settings.RESULT_AUDIO_PATH, filename.replace("mp3", "%(ext)s")
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


async def check_state(episodes: Iterable[Episode]) -> list:
    """ Allows to get info about download progress for requested episodes """

    redis_client = RedisClient()
    file_names = {redis_client.get_key_by_filename(episode.file_name) for episode in episodes}
    current_states = await redis_client.async_get_many(file_names, pkey="event_key")
    result = []
    for episode in episodes:
        file_name = episode.file_name
        if not file_name:
            logger.warning(f"Episode {episode} does not contain filename")
            continue

        event_key = redis_client.get_key_by_filename(file_name)
        current_state = current_states.get(event_key)
        if current_state:
            current_file_size = current_state["processed_bytes"]
            current_file_size_mb = round(current_file_size / 1024 / 1024, 2)
            total_file_size = current_state["total_bytes"]
            total_file_size_mb = round(total_file_size / 1024 / 1024, 2)
            completed = int((100 * current_file_size) / total_file_size)
        else:
            current_file_size = 0
            current_file_size_mb = 0
            total_file_size = 0
            total_file_size_mb = 0
            completed = 0

        result.append(
            {
                "episode_id": episode.id,
                "episode_title": episode.title,
                "podcast_id": episode.podcast_id,
                "completed": completed,
                "current_file_size": current_file_size,
                "current_file_size__mb": current_file_size_mb,
                "total_file_size": total_file_size,
                "total_file_size__mb": total_file_size_mb,
            }
        )

    return result
