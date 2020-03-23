import settings
from common.utils import get_logger, upload_file
from modules.podcast.models import Episode
from modules.youtube.exceptions import YoutubeException
from modules.youtube import utils as youtube_utils
from modules.podcast import utils as podcast_utils

logger = get_logger(__name__)

EPISODE_DOWNLOADING_OK = 0
EPISODE_DOWNLOADING_IGNORED = 1
EPISODE_DOWNLOADING_ERROR = 2


def _update_all_rss(source_id: str):
    """ Allows to regenerate rss for all podcasts with requested episode (by source_id) """

    logger.info(
        f"Episodes with source #%s: updating rss for all podcasts included for",
        source_id,
    )

    affected_episodes = list(
        Episode.select(Episode.podcast).where(Episode.source_id == source_id)
    )
    podcast_ids = [episode.podcast_id for episode in affected_episodes]
    logger.info(f"Found podcasts for rss updates: %s", podcast_ids)

    for podcast_id in podcast_ids:
        podcast_utils.generate_rss(podcast_id)


def _update_episode_data(source_id: str, update_data: dict):
    """ Allows to update data for episodes (filtered by source_id)"""

    logger.info(f"Episodes with source #{source_id}: update_data")
    Episode.update(**update_data).where(
        Episode.source_id == source_id, Episode.status != Episode.STATUS_ARCHIVED
    ).execute()


def _update_episode_state(source_id: str, file_size: int):
    """ Allows to mark ALL episodes (exclude archived) with provided source_id as published """

    logger.info(f"Episodes with source #{source_id}: updating states")
    _update_episode_data(source_id, {
        "status": Episode.STATUS_PUBLISHED,
        "published_at": Episode.created_at,
        "file_size": file_size,
    })


def download_episode(youtube_link: str, episode_id: int):
    """ Allows to download youtube video and recreate specific rss (by requested episode_id) """

    logger.info(f"START downloading for {youtube_link}")
    episode = Episode.get_by_id(episode_id)

    stored_file_size = podcast_utils.get_remote_file_size(episode.file_name)
    if stored_file_size and stored_file_size == episode.file_size:
        logger.info(
            f"Episode {episode} already downloaded and file correct. "
            f"Downloading will be ignored."
        )
        _update_episode_state(episode.source_id, stored_file_size)
        _update_all_rss(episode.source_id)
        return EPISODE_DOWNLOADING_IGNORED

    elif episode.status not in (Episode.STATUS_NEW, Episode.STATUS_DOWNLOADING):
        logger.error(
            f"Episode {episode} is {episode.status} but file-size seems not correct. "
            f"Removing not-correct file and reloading it from youtube."
        )
        podcast_utils.delete_remote_file(episode.file_name)

    logger.info(
        f"Mark all episodes with source_id [{episode.source_id}] as downloading."
    )
    query = Episode.update(status=Episode.STATUS_DOWNLOADING).where(
        Episode.source_id == episode.source_id,
        Episode.status != Episode.STATUS_ARCHIVED,
    )
    query.execute()

    try:
        result_filename = youtube_utils.download_audio(youtube_link)
    except YoutubeException as error:
        logger.exception(
            f"Downloading #{episode.source_id} FAILED: Could not download track: {error}. "
            f"All episodes will be rolled back to NEW state"
        )
        Episode.update(status=Episode.STATUS_NEW).where(
            Episode.source_id == episode.source_id
        ).execute()
        return EPISODE_DOWNLOADING_ERROR

    # ----- uploading file to cloud -----
    remote_url = upload_file(result_filename, remote_directory=settings.S3_BUCKET_AUDIO_PATH)
    _update_episode_data(episode.source_id, {"file_name": result_filename, "remote_url": remote_url})
    logger.info(f"=== UPLOAD process for {episode.source_id} was done.")
    # -----------------------------------

    # ----- update episodes data -------
    file_size = podcast_utils.get_remote_file_size(result_filename)
    _update_episode_state(episode.source_id, file_size)
    _update_all_rss(episode.source_id)
    logger.info("=== DOWNLOADING #%s FINISHED", episode.source_id)
    # -----------------------------------

    podcast_utils.delete_file(result_filename)  # remove tmp file
    return EPISODE_DOWNLOADING_OK


def generate_rss(podcast_id: int):
    """ Allows to download and recreate specific rss (by requested podcast.publish_id) """

    logger.info(f"START rss generation for {podcast_id}")
    podcast_utils.generate_rss(podcast_id)
    logger.info("FINISH generation")
