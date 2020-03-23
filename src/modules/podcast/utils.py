import os
import uuid
from pathlib import Path
from typing import Union, Iterable, Optional

import botocore
import botocore.exceptions
from jinja2 import Template

import settings
from common.redis import RedisClient
from common.utils import get_logger, get_s3_client
from modules.podcast.models import Podcast, Episode

logger = get_logger(__name__)


def _create_rss_file(template: Template, podcast: Podcast, extra_context: dict):
    rss_filename = os.path.join(settings.RESULT_RSS_PATH, f"{podcast.publish_id}.xml")
    logger.info(
        f"Podcast #{podcast.publish_id}: Generation new file rss [{rss_filename}]"
    )
    with open(rss_filename, "w") as fh:
        result_rss = template.render(podcast=podcast, **extra_context)
        fh.write(result_rss)
    logger.info(f"Podcast #{podcast.publish_id}: Generation DONE")


def generate_rss(podcast_id: int):
    """ Generate rss for Podcast and Episodes marked as "published" """

    logger.info(f"Podcast #{podcast_id}: RSS generation has been started.")
    podcast = Podcast.get_by_id(podcast_id)

    # noinspection PyComparisonWithNone
    episodes = podcast.get_episodes(podcast.created_by).where(
        Episode.status == Episode.STATUS_PUBLISHED,
        Episode.published_at != None,  # noqa: E711
    )
    context = {"episodes": episodes, "settings": settings}
    with open(os.path.join(settings.TEMPLATE_PATH, "rss", "feed_template.xml")) as fh:
        template = Template(fh.read())

    _create_rss_file(template, podcast, context)
    logger.info(f"Podcast #{podcast_id}: RSS generation has been finished.")


def delete_file(filename: Union[str, Path]):
    """ Delete local file """
    if not filename:
        logger.error("File deleting was skipped")
        return

    full_path = os.path.join(settings.TMP_AUDIO_PATH, filename)
    try:
        os.remove(full_path)
    except IOError as error:
        logger.warning(f"Could not delete file {full_path}: {error}")
    else:
        logger.info(f"File {full_path} deleted")


def delete_remote_file(filename: Union[str, Path]):
    """ Delete file from S3 storage """

    s3 = get_s3_client()
    try:
        remote_path = os.path.join(settings.S3_BUCKET_AUDIO_PATH, filename)
        file_deleted = s3.delete_object(Key=remote_path, Bucket=settings.S3_BUCKET_NAME)
    except botocore.exceptions.ClientError:
        logger.info("File %s was not found on s3 storage", filename)
    except Exception as error:
        logger.exception("Couldn't deleted file on s3 storage. Error: %s", error)
    else:
        logger.info("File %s found and deleted: %s", filename, file_deleted)


def get_file_name(video_id: str) -> str:
    return f"{video_id}_{uuid.uuid4().hex}.{settings.RESULT_FILE_EXT}"


def get_file_size(file_name):
    try:
        full_path = os.path.join(settings.TMP_AUDIO_PATH, file_name)
        return os.path.getsize(full_path)
    except FileNotFoundError:
        logger.info("File %s not found. Return size 0", file_name)
        return 0


def get_remote_file_size(filename: Optional[str]) -> int:
    """
    Allows to find file on remote storage (S3)
    Headers content info about downloaded file (there is a content-length / file size)
    """
    if filename:
        s3 = get_s3_client()
        try:
            remote_path = os.path.join(settings.S3_BUCKET_AUDIO_PATH, filename)
            file_head = s3.head_object(Key=remote_path, Bucket=settings.S3_BUCKET_NAME)
        except botocore.exceptions.ClientError:
            logger.info("File %s was not found on s3 storage", filename)
        except Exception as error:
            logger.exception("Couldn't fetch file on s3 storage. Error: %s", error)
        else:
            logger.info("File %s found with headers: %s", filename, file_head)
            return int(file_head['ResponseMetadata']['HTTPHeaders']['content-length'])

    return 0


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
