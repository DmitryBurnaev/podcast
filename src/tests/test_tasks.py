import os
from datetime import datetime
from unittest.mock import patch, Mock

import settings

from modules.podcast.models import Episode
from modules.podcast.tasks import (
    generate_rss,
    download_episode,
    EPISODE_DOWNLOADING_IGNORED,
    EPISODE_DOWNLOADING_OK,
    EPISODE_DOWNLOADING_ERROR,
)
from modules.youtube.exceptions import YoutubeException
from .conftest import generate_video_id, db_allow_sync
from .mocks import MockYoutube, MockS3Client


@db_allow_sync
def test_generate_rss__ok(db_objects, podcast, episode_data):

    new_episode_data = {
        **episode_data,
        **{"source_id": generate_video_id(), "status": "new"},
    }
    episode_new: Episode = Episode.create(**new_episode_data)

    new_episode_data = {
        **episode_data,
        **{"source_id": generate_video_id(), "status": "downloading"},
    }
    episode_downloading: Episode = Episode.create(**new_episode_data)

    new_episode_data = {
        **episode_data,
        **{
            "source_id": generate_video_id(),
            "status": "published",
            "published_at": datetime.utcnow(),
        },
    }
    episode_published: Episode = Episode.create(**new_episode_data)

    generate_rss(podcast.id)

    rss_filename = os.path.join(settings.RESULT_RSS_PATH, f"{podcast.publish_id}.xml")
    with open(rss_filename) as file:
        generated_rss_content = file.read()

    assert episode_published.title in generated_rss_content
    assert episode_published.description in generated_rss_content
    assert episode_published.file_name in generated_rss_content

    assert episode_new.source_id not in generated_rss_content
    assert episode_downloading.source_id not in generated_rss_content

    os.remove(rss_filename)


@db_allow_sync
def test_download_sound__episode_downloaded__file_correct__ignore_downloading__ok(
    db_objects, podcast, episode_data, mocked_youtube: MockYoutube, mocked_s3: MockS3Client
):
    new_episode_data = {
        **episode_data,
        **{
            "status": "published",
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
            "file_size": 1024,
        },
    }
    episode: Episode = Episode.create(**new_episode_data)
    mocked_s3.get_file_size.return_value = episode.file_size
    with patch("modules.podcast.tasks.podcast_utils.generate_rss") as generate_rss_mock:
        result = download_episode(episode.watch_url, episode.id)

    with db_objects.allow_sync():
        updated_episode: Episode = Episode.select().where(
            Episode.id == episode.id
        ).first()

    generate_rss_mock.assert_called_with(episode.podcast_id)
    assert result == EPISODE_DOWNLOADING_IGNORED
    assert not mocked_youtube.download.called
    assert updated_episode.status == "published"
    assert updated_episode.published_at == updated_episode.created_at


@db_allow_sync
@patch("modules.podcast.tasks.podcast_utils.generate_rss")
@patch("modules.podcast.tasks.youtube_utils.download_audio")
def test_download_sound__episode_new__correct_downloading(
    download_audio_mock,
    generate_rss_mock,
    db_objects,
    podcast,
    episode_data,
    mocked_youtube: MockYoutube,
    mocked_s3: MockS3Client,
    mocked_ffmpeg: Mock
):
    new_episode_data = {
        **episode_data,
        **{
            "status": "new",
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
            "file_size": 1024,
        },
    }
    episode: Episode = Episode.create(**new_episode_data)

    download_audio_mock.return_value = episode.file_name
    result = download_episode(episode.watch_url, episode.id)

    with db_objects.allow_sync():
        updated_episode: Episode = Episode.select().where(Episode.id == episode.id).first()

    generate_rss_mock.assert_called_with(episode.podcast_id)
    download_audio_mock.assert_called_with(episode.watch_url, episode.file_name)
    mocked_ffmpeg.assert_called_with(episode.file_name)

    assert result == EPISODE_DOWNLOADING_OK
    assert updated_episode.status == "published"
    assert updated_episode.published_at == updated_episode.created_at


@db_allow_sync
@patch("modules.podcast.tasks.podcast_utils.generate_rss")
@patch("modules.podcast.tasks.youtube_utils.download_audio")
def test_download_sound__episode_downloaded__file_incorrect__reload(
    download_audio_mock,
    generate_rss_mock,
    db_objects,
    podcast,
    episode_data,
    mocked_youtube: MockYoutube,
    mocked_s3: MockS3Client,
    mocked_ffmpeg: Mock
):
    new_episode_data = {
        **episode_data,
        **{
            "status": "published",
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
            "file_size": 1024,
        },
    }
    episode: Episode = Episode.create(**new_episode_data)

    download_audio_mock.return_value = episode.file_name
    mocked_s3.get_file_size.return_value = 32
    result = download_episode(episode.watch_url, episode.id)

    with db_objects.allow_sync():
        updated_episode: Episode = Episode.select().where(Episode.id == episode.id).first()

    generate_rss_mock.assert_called_with(episode.podcast_id)
    download_audio_mock.assert_called_with(episode.watch_url, episode.file_name)
    mocked_ffmpeg.assert_called_with(episode.file_name)

    assert result == EPISODE_DOWNLOADING_OK
    assert updated_episode.status == "published"
    assert updated_episode.published_at == updated_episode.created_at


@db_allow_sync
@patch("modules.podcast.tasks.youtube_utils.download_audio")
def test_download_sound__youtube_exception__download_rollback(
    download_audio_mock, db_objects, podcast, episode_data, mocked_youtube: MockYoutube, mocked_s3: MockS3Client
):
    new_episode_data = {
        **episode_data,
        **{
            "status": "new",
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
            "file_size": 1024,
        },
    }
    episode: Episode = Episode.create(**new_episode_data)

    download_audio_mock.side_effect = YoutubeException("Youtube video is not available")
    result = download_episode(episode.watch_url, episode.id)

    with db_objects.allow_sync():
        updated_episode: Episode = Episode.select().where(
            Episode.id == episode.id
        ).first()

    download_audio_mock.assert_called_with(episode.watch_url, episode.file_name)

    assert result == EPISODE_DOWNLOADING_ERROR
    assert updated_episode.status == "new"
    assert updated_episode.published_at is None
