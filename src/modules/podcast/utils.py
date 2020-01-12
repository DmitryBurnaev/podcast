import os
from logging import Logger
from pathlib import Path
from typing import Union

from jinja2 import Template

import settings
from common.utils import get_logger
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


def delete_file(filename: Union[str, Path], log: Logger):
    if not filename:
        log.error(f"Episode contains 'None' file. SKIP")
        return

    full_path = os.path.join(settings.RESULT_AUDIO_PATH, filename)
    try:
        os.remove(full_path)
    except IOError as error:
        log.warning(f"Could not delete file {full_path}: {error}")
    else:
        log.info(f"File {full_path} deleted")
