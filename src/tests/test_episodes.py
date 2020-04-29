import json
import time
from operator import itemgetter
from typing import List
from unittest.mock import patch

import peewee
import pytest
from aiohttp import ClientResponse

from modules.podcast.utils import EpisodeStatuses
from modules.auth.models import User
from modules.podcast import tasks

from modules.podcast.models import Podcast, Episode
from modules.youtube.exceptions import YoutubeExtractInfoError
from .conftest import generate_video_id, get_user_data, make_cookie
from .mocks import MockYoutube


def get_session_messages(response: ClientResponse) -> List[dict]:
    try:
        cookie_value = json.loads(response.cookies["AIOHTTP_SESSION"].value)
        return [
            message["message"] for _, message in cookie_value["session"]["messages"]
        ]
    except KeyError:
        return []


async def test_episodes__get_list__ok(
    client, db_objects, user, urls, podcast, podcast_data, episode_data
):
    podcast_data["publish_id"] = str(time.time())
    another_podcast = await db_objects.create(Podcast, **podcast_data)

    new_episode_data = {**episode_data, **{"podcast_id": another_podcast.id}}
    await db_objects.create(Episode, **new_episode_data)

    response = await client.get(urls.episodes_list)
    assert response.status == 200
    episodes = await podcast.get_episodes_async(db_objects, request_user_id=user.id)
    expected_data = [{"id": episode.id, "title": episode.title} for episode in episodes]
    response_data = await response.json()
    assert expected_data == response_data


async def test_episodes__get_details__ok(client, episode, urls):
    response = await client.get(urls.episodes_details)
    assert response.status == 200
    content = await response.text()
    assert str(episode.id) in content
    assert episode.title in content


async def test_episodes__create__invalid_request__fail(
    client, db_objects, episode, urls
):
    request_data = {"youtube_fake_link": "some link"}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )
    response_messages = get_session_messages(response)
    expected_messages = [
        "Input data is invalid: {'youtube_fake_link': ['unknown field'], "
        "'youtube_link': ['required field']}"
    ]
    assert response.status == 302
    assert response_messages == expected_messages
    assert response.headers["Location"] == urls.episodes_list


async def test_episodes__create__ok(
    client, db_objects, podcast, urls, mocked_youtube, mocked_s3
):
    youtube_link = mocked_youtube.watch_url
    request_data = {"youtube_link": youtube_link}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )
    assert response.status == 302
    created_episode = await db_objects.get(Episode, watch_url=youtube_link)
    assert (
        response.headers["Location"]
        == f"/podcasts/{podcast.id}/episodes/{created_episode.id}/"
    )


async def test_episodes__create__video_unavailable__fail(
    client, db_objects, podcast, urls, mocked_youtube, mocked_s3
):
    mocked_youtube.extract_info.side_effect = YoutubeExtractInfoError()
    request_data = {"youtube_link": mocked_youtube.watch_url}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )
    response_messages = get_session_messages(response)
    expected_messages = ["Sorry.. Fetching YouTube video was failed"]
    assert response.status == 302
    assert response_messages == expected_messages
    assert response.headers["Location"] == urls.podcasts_details
    with pytest.raises(peewee.DoesNotExist):
        await db_objects.get(Episode, watch_url=mocked_youtube.watch_url)


async def test_episodes__create__youtube_unexpected_error__fail(
    client, db_objects, podcast, urls, mocked_youtube, mocked_s3
):
    mocked_youtube.extract_info.side_effect = ValueError("Ooops")
    request_data = {"youtube_link": mocked_youtube.watch_url}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )
    response_messages = get_session_messages(response)
    expected_messages = ["Sorry.. Fetching YouTube video was failed"]
    assert response.status == 302
    assert response_messages == expected_messages
    assert response.headers["Location"] == urls.podcasts_details
    with pytest.raises(peewee.DoesNotExist):
        await db_objects.get(Episode, watch_url=mocked_youtube.watch_url)


async def test_episodes__create__incorrect_link__fail(
    client, db_objects, episode, urls
):
    request_data = {"youtube_link": "http://path.to-not-youtube.com"}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )
    response_messages = get_session_messages(response)
    expected_messages = ["YouTube link is not correct: http://path.to-not-youtube.com"]
    assert response.status == 302
    assert response_messages == expected_messages
    assert response.headers["Location"] == urls.podcasts_details


async def test_episodes__create__same_episode_in_same_podcast__ok(
    client, db_objects, podcast, urls, episode_data, mocked_youtube, mocked_s3
):
    episode_data.update(
        {"source_id": mocked_youtube.video_id, "watch_url": mocked_youtube.watch_url}
    )
    exists_episode = await db_objects.create(Episode, **episode_data)

    request_data = {"youtube_link": mocked_youtube.watch_url}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )

    response_messages = get_session_messages(response)
    expected_messages = ["Episode already exists in podcast."]
    assert response.status == 302
    assert response_messages == expected_messages
    assert (
        response.headers["Location"]
        == f"/podcasts/{podcast.id}/episodes/{exists_episode.id}/"
    )


async def test_episodes__create__same_episode_in_other_podcast__ok(
    client,
    db_objects,
    podcast,
    podcast_data,
    episode_data,
    urls,
    mocked_youtube: MockYoutube,
    mocked_s3,
):
    updated_title = f"Updated title for video {mocked_youtube.video_id}"
    updated_description = f"Updated description for video {mocked_youtube.video_id}"
    mocked_youtube.title = updated_title
    mocked_youtube.description = updated_description
    mocked_youtube.extract_info.return_value = mocked_youtube.info

    podcast_data["publish_id"] = str(time.time())
    another_podcast = await db_objects.create(Podcast, **podcast_data)
    episode_data.update(
        {
            "podcast_id": another_podcast.id,
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
        }
    )
    await db_objects.create(Episode, **episode_data)

    request_data = {"youtube_link": mocked_youtube.watch_url}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )

    created_episode: Episode = await db_objects.get(
        Episode, podcast_id=podcast.id, source_id=mocked_youtube.video_id
    )

    response_messages = get_session_messages(response)
    expected_messages = [
        "Episode was successfully created from the YouTube video.",
        f"Downloading for youtube {created_episode.source_id} was started.",
    ]

    assert response.status == 302
    assert (
        response.headers["Location"]
        == f"/podcasts/{podcast.id}/episodes/{created_episode.id}/"
    )

    assert created_episode.title == updated_title
    assert created_episode.description == updated_description

    assert response_messages == expected_messages
    mocked_youtube.extract_info.assert_called()


async def test_episodes__create__same_episode_in_other_podcast__youtube_video_unavailable__ok(
    client,
    db_objects,
    podcast,
    podcast_data,
    episode_data,
    urls,
    mocked_youtube: MockYoutube,
    mocked_s3,
):
    mocked_youtube.extract_info.side_effect = YoutubeExtractInfoError("Ooops")

    podcast_data["publish_id"] = str(time.time())
    another_podcast = await db_objects.create(Podcast, **podcast_data)
    episode_data.update(
        {
            "podcast_id": another_podcast.id,
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
        }
    )
    await db_objects.create(Episode, **episode_data)

    request_data = {"youtube_link": mocked_youtube.watch_url}
    response = await client.post(
        urls.episodes_list, data=request_data, allow_redirects=False
    )

    created_episode: Episode = await db_objects.get(
        Episode, podcast_id=podcast.id, source_id=mocked_youtube.video_id
    )

    response_messages = get_session_messages(response)
    expected_messages = [
        "Sorry.. Fetching YouTube video was failed",
        "Episode will be copied from other episode with same video.",
        f"Downloading for youtube {created_episode.source_id} was started.",
    ]

    assert response.status == 302
    assert (
        response.headers["Location"]
        == f"/podcasts/{podcast.id}/episodes/{created_episode.id}/"
    )

    assert created_episode.title == episode_data["title"]
    assert created_episode.description == episode_data["description"]

    assert response_messages == expected_messages


async def test_episodes__create__check_for_start_downloading__ok(
    client, db_objects, podcast, episode_data, urls, mocked_youtube, mocked_s3
):
    assert podcast.download_automatically

    youtube_link = mocked_youtube.watch_url
    request_data = {"youtube_link": youtube_link}
    with patch("rq.queue.Queue.enqueue") as rq_mock:
        response = await client.post(
            urls.episodes_list, data=request_data, allow_redirects=False
        )

    created_episode: Episode = await db_objects.get(Episode, watch_url=youtube_link)
    assert response.status == 302
    rq_mock.assert_called_with(
        tasks.download_episode,
        episode_id=created_episode.id,
        youtube_link=created_episode.watch_url,
    )
    assert (
        response.headers["Location"]
        == f"/podcasts/{podcast.id}/episodes/{created_episode.id}/"
    )


async def test_episodes__delete__ok(
    client, db_objects, episode_data, urls, urls_tpl, mocked_s3
):
    podcast_id = episode_data["podcast_id"]
    episode_data["source_id"] = f"source_{time.time_ns()}"
    episode_data["filename"] = f"fn_{time.time_ns()}"
    episode = await db_objects.create(Episode, **episode_data)

    url = urls_tpl.episodes_delete.format(podcast_id=podcast_id, episode_id=episode.id)
    response = await client.get(url, allow_redirects=False)
    mocked_s3.delete_files_async_mock.assert_called_with([episode.file_name])

    assert response.status == 302
    assert response.headers["Location"] == urls_tpl.podcasts_details.format(
        podcast_id=podcast_id
    )
    with pytest.raises(peewee.DoesNotExist):
        await db_objects.get(Episode, id=episode.id)


@pytest.mark.parametrize(
    "same_episode_status, delete_called", [("new", True), ("published", False)]
)
async def test_episodes__delete__same_episode_exists__ok(
    same_episode_status,
    delete_called,
    client,
    db_objects,
    podcast,
    podcast_data,
    episode_data,
    urls_tpl,
    mocked_youtube,
    mocked_s3,
):
    episode_data.update(
        {
            "podcast_id": podcast.id,
            "source_id": mocked_youtube.video_id,
            "watch_url": mocked_youtube.watch_url,
        }
    )
    episode = await db_objects.create(Episode, **episode_data)

    podcast_data["publish_id"] = str(time.time())
    another_podcast = await db_objects.create(Podcast, **podcast_data)
    episode_data.update(
        {"podcast_id": another_podcast.id, "status": same_episode_status}
    )
    await db_objects.create(Episode, **episode_data)
    url = urls_tpl.episodes_delete.format(podcast_id=podcast.id, episode_id=episode.id)
    response = await client.get(url, allow_redirects=False)
    assert mocked_s3.delete_files_async_mock.called is delete_called

    response_messages = get_session_messages(response)
    expected_messages = [f"Episode for youtube ID {episode.source_id} was removed."]

    assert response.status == 302
    assert response.headers["Location"] == urls_tpl.podcasts_details.format(
        podcast_id=podcast.id
    )
    assert response_messages == expected_messages


async def test_episodes__download__start_downloading__ok(
    client, podcast, episode, urls
):
    with patch("rq.queue.Queue.enqueue") as rq_mock:
        response = await client.get(urls.episodes_download, allow_redirects=False)
        assert response.status == 302

        rq_mock.assert_called_with(
            tasks.download_episode,
            episode_id=episode.id,
            youtube_link=episode.watch_url,
        )

    response_messages = get_session_messages(response)
    expected_messages = [f"Downloading for youtube {episode.source_id} started."]

    assert response.headers["Location"] == urls.progress
    assert response_messages == expected_messages


async def test_episodes__create__mobile_redirect__ok(
    client, db_objects, podcast, episode_data, urls, mocked_youtube, mocked_s3
):
    youtube_link = mocked_youtube.watch_url
    request_data = {"youtube_link": youtube_link}
    response = await client.post(
        urls.episodes_list,
        data=request_data,
        allow_redirects=False,
        headers={"User-Agent": "mobile-app-web-view"},
    )
    assert response.status == 302
    assert await db_objects.get(Episode, watch_url=youtube_link) is not None
    assert response.headers["Location"] == urls.progress


async def test_episodes__progress__several_podcasts__filter_by_status__ok(
    client, db_objects, podcast, podcast_data, episode_data, urls, mocked_redis
):
    podcast_data["publish_id"] = str(time.time())
    podcast_1 = podcast
    podcast_2 = await db_objects.create(Podcast, **podcast_data)
    src_id_1 = generate_video_id()
    src_id_2 = generate_video_id()
    src_id_3 = generate_video_id()
    src_id_4 = generate_video_id()

    podcast_1__episode_data__status_new = {
        **episode_data,
        **{
            "podcast_id": podcast_1.id,
            "source_id": src_id_1,
            "file_name": f"file_name_{src_id_1}",
            "status": Episode.STATUS_NEW,
            "file_size": 1 * 1024 * 1024,
        },
    }
    podcast_1__episode_data__status_downloading = {
        **episode_data,
        **{
            "podcast_id": podcast_1.id,
            "source_id": src_id_2,
            "file_name": f"file_name_{src_id_2}",
            "status": Episode.STATUS_DOWNLOADING,
            "file_size": 2 * 1024 * 1024,
        },
    }
    podcast_2__episode_data__status_new = {
        **episode_data,
        **{
            "podcast_id": podcast_2.id,
            "source_id": src_id_3,
            "file_name": f"file_name_{src_id_3}",
            "status": Episode.STATUS_NEW,
            "file_size": 1 * 1024 * 1024,
        },
    }
    podcast_2__episode_data__status_downloading = {
        **episode_data,
        **{
            "podcast_id": podcast_2.id,
            "source_id": src_id_4,
            "file_name": f"file_name_{src_id_4}",
            "status": Episode.STATUS_DOWNLOADING,
            "file_size": 4 * 1024 * 1024,
        },
    }
    await db_objects.create(Episode, **podcast_1__episode_data__status_new)
    p1_episode_downloading = await db_objects.create(
        Episode, **podcast_1__episode_data__status_downloading
    )
    await db_objects.create(Episode, **podcast_2__episode_data__status_new)
    p2_episode_downloading = await db_objects.create(
        Episode, **podcast_2__episode_data__status_downloading
    )

    mocked_redis.get_many.return_value = {}
    response = await client.get(urls.progress, allow_redirects=False)
    assert response.status == 200, "Progress view is not available"

    mocked_redis.get_many.return_value = {
        p1_episode_downloading.file_name.partition(".")[0]: {
            "status": EpisodeStatuses.episode_downloading,
            "processed_bytes": 1024 * 1024,
            "total_bytes": 2 * 1024 * 1024,
        },
        p2_episode_downloading.file_name.partition(".")[0]: {
            "status": EpisodeStatuses.episode_downloading,
            "processed_bytes": 1024 * 1024,
            "total_bytes": 4 * 1024 * 1024,
        },
    }
    response = await client.get(urls.progress_api, allow_redirects=False)
    response_text = await response.text()
    assert response.status == 200, f"Progress API is not available: {response_text}"

    expected_progress = [
        {
            "status": EpisodeStatuses.episode_downloading,
            "status_display": "Downloading",
            "episode_id": p1_episode_downloading.id,
            "episode_title": p1_episode_downloading.title,
            "podcast_id": p1_episode_downloading.podcast_id,
            "podcast_publish_id": podcast_1.publish_id,
            "completed": 50,  # 1MB from 2MB
            "current_file_size": 1024 * 1024,
            "current_file_size__mb": 1.00,
            "total_file_size": p1_episode_downloading.file_size,
            "total_file_size__mb": 2.00,
        },
        {
            "status": EpisodeStatuses.episode_downloading,
            "status_display": "Downloading",
            "episode_id": p2_episode_downloading.id,
            "episode_title": p2_episode_downloading.title,
            "podcast_id": p2_episode_downloading.podcast_id,
            "podcast_publish_id": podcast_2.publish_id,
            "completed": 25,  # 1MB from 4MB
            "current_file_size": 1024 * 1024,
            "current_file_size__mb": 1.00,
            "total_file_size": p2_episode_downloading.file_size,
            "total_file_size__mb": 4.00,
        },
    ]
    actual_progress = await response.json()
    actual_progress = sorted(actual_progress["progress"], key=itemgetter("episode_id"))
    assert actual_progress == expected_progress


async def test_episodes__progress__filter_by_user__ok(
    unauth_client, db_objects, podcast, podcast_data, episode_data, urls, mocked_redis
):
    username, password = get_user_data()
    other_user = await db_objects.create(User, username=username, password=password)
    client = make_cookie(unauth_client, {"user": other_user.id})

    podcast_data["publish_id"] = str(time.time())
    podcast_data["created_by"] = other_user.id
    podcast_1 = podcast
    podcast_2 = await db_objects.create(Podcast, **podcast_data)
    source_id_1 = generate_video_id()
    source_id_2 = generate_video_id()

    podcast_1__episode_data__requested_user = {
        **episode_data,
        **{
            "podcast_id": podcast_1.id,
            "source_id": source_id_1,
            "file_name": f"file_name_{source_id_1}",
            "status": Episode.STATUS_DOWNLOADING,
            "file_size": 2 * 1024 * 1024,
        },
    }
    podcast_2__episode_data__other_user = {
        **episode_data,
        **{
            "created_by": other_user.id,
            "podcast_id": podcast_2.id,
            "source_id": source_id_2,
            "file_name": f"file_name_{source_id_2}",
            "status": Episode.STATUS_DOWNLOADING,
            "file_size": 4 * 1024 * 1024,
        },
    }
    p1_episode__requested_user = await db_objects.create(
        Episode, **podcast_1__episode_data__requested_user
    )
    p2_episode__other_user = await db_objects.create(
        Episode, **podcast_2__episode_data__other_user
    )

    mocked_redis.get_many.return_value = {
        p1_episode__requested_user.file_name.partition(".")[0]: {
            "status": EpisodeStatuses.episode_downloading,
            "processed_bytes": 1024 * 1024,
            "total_bytes": 2 * 1024 * 1024,
        },
        p2_episode__other_user.file_name.partition(".")[0]: {
            "status": EpisodeStatuses.episode_downloading,
            "processed_bytes": 1024 * 1024,
            "total_bytes": 4 * 1024 * 1024,
        },
    }
    response = await client.get(urls.progress_api, allow_redirects=False)
    response_text = await response.text()
    assert response.status == 200, f"Progress API is not available: {response_text}"
    actual_progress = await response.json()

    expected_episode_ids = [p2_episode__other_user.id]
    actual_episode_ids = [
        progress["episode_id"] for progress in actual_progress["progress"]
    ]
    assert expected_episode_ids == actual_episode_ids


async def test_episodes__progress__empty_list__ok(unauth_client, urls, db_objects):
    username, password = get_user_data()
    other_user = await db_objects.create(User, username=username, password=password)
    client = make_cookie(unauth_client, {"user": other_user.id})

    response = await client.get(urls.progress_api, allow_redirects=False)
    assert response.status == 200, f"Progress API is not available: {response.text}"
    actual_progress = await response.json()

    actual_episode_ids = [
        progress["episode_id"] for progress in actual_progress["progress"]
    ]
    assert actual_episode_ids == []
