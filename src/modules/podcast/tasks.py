import os

import settings
from common.models import database
from common.storage import StorageS3
from common.utils import get_logger
from modules.podcast.models import Episode, Podcast
from modules.podcast.utils import get_file_name
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

    logger.info("[%s] Episodes update data: %s", source_id, update_data)
    Episode.update(**update_data).where(
        Episode.source_id == source_id, Episode.status != Episode.STATUS_ARCHIVED
    ).execute()


def _update_episodes(
    source_id: str, file_size: int, status: str = Episode.STATUS_PUBLISHED
):
    """ Allows to mark ALL episodes (exclude archived) with provided source_id as published """

    logger.info(f"Episodes with source #{source_id}: updating states")
    update_data = {"status": status, "file_size": file_size}
    if status == Episode.STATUS_PUBLISHED:
        update_data["published_at"] = Episode.created_at

    _update_episode_data(source_id, update_data)


# TODO: refactor me! use class-style for this task
# TODO: transaction atomic is need here
def download_episode(youtube_link: str, episode_id: int):
    """ Allows to download youtube video and recreate specific rss (by requested episode_id) """

    episode = Episode.get_by_id(episode_id)
    logger.info(
        "=== [%s] START downloading process URL: %s FILENAME: %s ===",
        episode.source_id,
        youtube_link,
        episode.file_name,
    )
    stored_file_size = StorageS3().get_file_size(episode.file_name)

    if stored_file_size and stored_file_size == episode.file_size:
        logger.info(
            "[%s] Episode already downloaded and file correct. Downloading will be ignored.",
            episode.source_id,
        )
        _update_episodes(episode.source_id, stored_file_size)
        _update_all_rss(episode.source_id)
        return EPISODE_DOWNLOADING_IGNORED

    elif episode.status not in (Episode.STATUS_NEW, Episode.STATUS_DOWNLOADING):
        logger.error(
            "[%s] Episode is %s but file-size seems not correct. "
            "Removing not-correct file %s and reloading it from youtube.",
            episode.source_id,
            episode.status,
            episode.file_name,
        )
        StorageS3().delete_file(episode.file_name)

    logger.info(
        f"[%s] Mark all episodes with source_id [%s] as downloading.",
        episode.source_id,
        episode.source_id,
    )
    query = Episode.update(status=Episode.STATUS_DOWNLOADING).where(
        Episode.source_id == episode.source_id,
        Episode.status != Episode.STATUS_ARCHIVED,
    )
    query.execute()

    try:
        result_filename = youtube_utils.download_audio(youtube_link, episode.file_name)
    except YoutubeException as error:
        logger.exception(
            "=== [%s] Downloading FAILED: Could not download track: %s. "
            "All episodes will be rolled back to NEW state",
            episode.source_id,
            error,
        )
        Episode.update(status=Episode.STATUS_NEW).where(
            Episode.source_id == episode.source_id
        ).execute()
        return EPISODE_DOWNLOADING_ERROR

    logger.info("=== [%s] DOWNLOADING was done ===", episode.source_id)

    youtube_utils.ffmpeg_preparation(result_filename)
    logger.info("=== [%s] POST PROCESSING was done === ", episode.source_id)

    # ----- uploading file to cloud -----
    remote_url = podcast_utils.upload_episode(result_filename)
    if not remote_url:
        logger.warning("=== [%s] UPLOADING was broken === ")
        _update_episodes(episode.source_id, file_size=0, status=Episode.STATUS_ERROR)
        return EPISODE_DOWNLOADING_ERROR

    _update_episode_data(
        episode.source_id, {"file_name": result_filename, "remote_url": remote_url}
    )
    logger.info("=== [%s] UPLOADING was done === ", episode.source_id)
    # -----------------------------------

    # ----- update episodes data -------
    _update_episodes(
        episode.source_id, file_size=StorageS3().get_file_size(result_filename)
    )
    _update_all_rss(episode.source_id)
    podcast_utils.delete_file(result_filename)  # remove tmp file
    # -----------------------------------

    logger.info("=== [%s] DOWNLOADING total finished ===", episode.source_id)
    return EPISODE_DOWNLOADING_OK


def generate_rss(podcast_id: int):
    """ Allows to download and recreate specific rss (by requested podcast.publish_id) """

    logger.info(f"START rss generation for {podcast_id}")
    podcast_utils.generate_rss(podcast_id)
    logger.info("FINISH generation")


def upload_all():
    """ TMP: Upload local files to S3 storage """

    episodes = list(
        Episode.select()
        .where(Episode.remote_url.is_null())
        .order_by(Episode.created_at.desc())
    )
    for index, episode in enumerate(episodes, start=1):
        logger.info(
            "\n\n====== START [%s]  %i from %i ======",
            episode.source_id,
            index,
            len(episodes),
        )
        with database.atomic() as transaction:  # Opens new transaction.
            try:
                filename = get_file_name(
                    episode.source_id, file_ext=episode.file_name.split(".")[-1]
                )
                src_path = os.path.join(settings.RESULT_AUDIO_PATH, episode.file_name)
                if not os.path.exists(src_path):
                    logger.info(
                        "====== SKIP: file %s does not exist ======", episode.file_name
                    )
                    continue

                remote_url = podcast_utils.upload_episode(filename, src_path=src_path)
                if not remote_url:
                    raise RuntimeError("=== [%s] UPLOADING was broken === ")

                _update_episode_data(
                    episode.source_id, {"file_name": filename, "remote_url": remote_url}
                )

            except Exception as error:
                transaction.rollback()
                logger.exception("======= FAILED ====== \n %s", error)
                exit(1)

        logger.info("=== FINISH [%s] UPLOADING ===", episode.source_id)

    logger.info("\n\n=== START RSS GENERATION ===")

    for podcast in Podcast.select(Podcast.id):
        generate_rss(podcast.id)

    logger.info("=== FINISH RSS GENERATION ===")


def delete_files():
    """ TMP: Remove local files which was uploaded to S3 storage """

    episodes = list(
        Episode.select()
        .where(Episode.remote_url.contains("http"))
        .order_by(Episode.created_at.desc())
    )
    if not episodes:
        logger.info(" ==== Not found episodes with 'remote_url' === ")
        return

    storage = StorageS3()
    for index, episode in enumerate(episodes, start=1):
        logger.info(
            "\n\n====== [%s] START %i from %i ======",
            episode.source_id,
            index,
            len(episodes),
        )
        try:
            file_ext = episode.file_name.split(".")[-1]
            src_path = os.path.join(
                settings.RESULT_AUDIO_PATH, f"{episode.source_id}_sound.{file_ext}"
            )
            if not os.path.exists(src_path):
                logger.info(
                    "====== [%s] SKIP: file %s does not exist ======",
                    episode.source_id,
                    src_path,
                )
                continue

            remote_size = storage.get_file_size(episode.file_name)
            local_size = podcast_utils.get_file_size(src_path)
            if local_size != remote_size:
                logger.warning(
                    "====== [%s] SKIP: file %s has another file size %s != %s ======",
                    episode.source_id,
                    episode.file_name,
                    local_size,
                    remote_size,
                )
                continue

            try:
                os.remove(src_path)
            except IOError as error:
                logger.warning(
                    f"====== [%s] Could not delete file %s: %s",
                    episode.source_id,
                    src_path,
                    error,
                )
            else:
                logger.info(
                    f"==== [%s] FILE %s deleted ==== ", episode.source_id, src_path
                )

        except Exception as error:
            logger.exception(
                "======= [%s] FAILED ====== \n %s", episode.source_id, error
            )
            exit(1)

    logger.info("=== FINISH FILE REMOVING ===\n\n")
