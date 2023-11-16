import json
import time
from typing import List

import peewee
import pytest
from aiohttp import ClientResponse

from modules.podcast.models import Podcast, Episode

pytestmark = pytest.mark.asyncio


def get_session_messages(response: ClientResponse) -> List[dict]:
    try:
        cookie_value = json.loads(response.cookies["AIOHTTP_SESSION"].value)
        return [message["message"] for _, message in cookie_value["session"]["messages"]]
    except KeyError:
        return []


async def test_podcasts__get_list__ok(client, db_objects, urls, user, podcast, podcast_data):
    podcast_data["publish_id"] = str(time.time())
    podcast_data["created_by"] = user.id
    another_podcast = await db_objects.create(Podcast, **podcast_data)

    response = await client.get(urls.podcasts_list)
    response_data = await response.text()

    assert response.status == 200
    assert str(podcast.id) in response_data
    assert str(another_podcast.id) in response_data


async def test_podcasts__get_details__ok(client, podcast, urls):
    response = await client.get(urls.podcasts_details)
    assert response.status == 200
    content = await response.text()
    assert str(podcast.id) in content
    assert podcast.name in content


async def test_podcasts__get_default_podcast__ok(client, podcast, urls):
    response = await client.get(urls.podcasts_default)
    assert response.status == 200
    content = await response.text()
    assert str(podcast.id) in content
    assert podcast.name in content


async def test_podcasts__create__invalid_request__fail(client, db_objects, episode, urls):
    request_data = {"name_as_not_allowed_field": "some link"}
    response = await client.post(urls.podcasts_list, data=request_data, allow_redirects=False)
    response_messages = get_session_messages(response)
    expected_messages = [
        "Input data is invalid: {'name': ['required field'], "
        "'name_as_not_allowed_field': ['unknown field']}"
    ]
    assert response.status == 302
    assert response_messages == expected_messages
    assert response.headers["Location"] == urls.podcasts_list


async def test_podcasts__create__ok(client, db_objects, podcast, urls):
    request_data = {"name": "test name", "description": "test description"}
    response = await client.post(urls.podcasts_list, data=request_data, allow_redirects=False)
    assert response.status == 302
    created_podcast = await db_objects.get(Podcast.select().order_by(Podcast.created_at.desc()))
    assert response.headers["Location"] == f"/podcasts/{created_podcast.id}/"
    assert created_podcast.name == "test name"
    assert created_podcast.description == "test description"


async def test_podcasts__delete__ok(
    client, db_objects, podcast, podcast_data, episode_data, urls_tpl, mocked_s3
):
    podcast_data["publish_id"] = str(time.time())
    another_podcast: Podcast = await db_objects.create(Podcast, **podcast_data)

    episode_data["podcast_id"] = another_podcast.id
    source_id = f"test_source_1_{time.time()}"
    episode_data["source_id"] = source_id
    episode_data["file_name"] = f"file_{source_id}"
    episode = await db_objects.create(Episode, **episode_data)

    url = urls_tpl.podcasts_delete.format(podcast_id=another_podcast.id)
    response = await client.get(url, allow_redirects=False)

    expected_call_args = [
        (([episode.file_name],), {}),
        (([f"{another_podcast.publish_id}.xml"],), {"remote_path": "rss"}),
    ]
    actual_call_args = [
        (call[0], call[1]) for call in mocked_s3.delete_files_async_mock.call_args_list
    ]

    assert actual_call_args == expected_call_args
    assert response.status == 302
    assert response.headers["Location"] == urls_tpl.podcasts_list

    with pytest.raises(peewee.DoesNotExist):
        await db_objects.get(Podcast, id=another_podcast.id)
        await db_objects.get(Episode, id=episode.id)

    podcast = await db_objects.get(Podcast, id=podcast.id)
    assert podcast is not None


async def test_podcasts__delete__skip_used_episode_deletion(
    client, db_objects, podcast_data, episode_data, urls_tpl, mocked_s3
):
    podcast_data["publish_id"] = str(time.time())
    podcast_to_delete: Podcast = await db_objects.create(Podcast, **podcast_data)

    podcast_data["publish_id"] = str(time.time())
    podcast_2: Podcast = await db_objects.create(Podcast, **podcast_data)

    source_id_1 = f"test_source_1_{time.time()}"
    source_id_2 = f"test_source_2_{time.time()}"

    episode_data["podcast_id"] = podcast_to_delete.id
    episode_data["source_id"] = source_id_1
    episode_data["file_name"] = f"file_{source_id_1}"
    episode_1 = await db_objects.create(Episode, **episode_data)

    episode_data["source_id"] = source_id_2
    episode_data["file_name"] = f"file_{source_id_2}"
    await db_objects.create(Episode, **episode_data)

    episode_data["podcast_id"] = podcast_2.id
    episode_data["source_id"] = source_id_2
    episode_data["file_name"] = f"file_{source_id_2}"
    await db_objects.create(Episode, **episode_data)

    url = urls_tpl.podcasts_delete.format(podcast_id=podcast_to_delete.id)
    response = await client.get(url, allow_redirects=False)

    expected_call_args = [
        (([episode_1.file_name],), {}),
        (([f"{podcast_to_delete.publish_id}.xml"],), {"remote_path": "rss"}),
    ]
    actual_call_args = [
        (call[0], call[1]) for call in mocked_s3.delete_files_async_mock.call_args_list
    ]

    assert actual_call_args == expected_call_args
    assert response.status == 302
    assert response.headers["Location"] == urls_tpl.podcasts_list
