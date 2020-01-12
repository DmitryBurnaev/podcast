import json
import os
import time
from typing import List
from unittest.mock import patch

import peewee
import pytest
from aiohttp import ClientResponse

import settings

from modules.podcast.models import Podcast, Episode


def get_session_messages(response: ClientResponse) -> List[dict]:
    try:
        cookie_value = json.loads(response.cookies["AIOHTTP_SESSION"].value)
        return [
            message["message"] for _, message in cookie_value["session"]["messages"]
        ]
    except KeyError:
        return []


async def test_podcasts__get_list__ok(
    client, db_objects, urls, user, podcast, podcast_data
):
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


async def test_podcasts__create__invalid_request__fail(
    client, db_objects, episode, urls
):
    request_data = {"name_as_not_allowed_field": "some link"}
    response = await client.post(
        urls.podcasts_list, data=request_data, allow_redirects=False
    )
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
    response = await client.post(
        urls.podcasts_list, data=request_data, allow_redirects=False
    )
    assert response.status == 302
    created_podcast = await db_objects.get(
        Podcast.select().order_by(Podcast.created_at.desc())
    )
    assert response.headers["Location"] == f"/podcasts/{created_podcast.id}/"
    assert created_podcast.name == "test name"
    assert created_podcast.description == "test description"


async def test_podcasts__delete__ok(
    client, db_objects, podcast, podcast_data, episode_data, urls, urls_tpl
):

    podcast_data["publish_id"] = str(time.time())
    another_podcast: Podcast = await db_objects.create(Podcast, **podcast_data)

    episode_data["source_id"] = "test_source_id"
    episode_data["podcast_id"] = another_podcast.id
    episode = await db_objects.create(Episode, **episode_data)

    with patch("os.remove") as mocked_os_remove:
        url = urls_tpl.podcasts_delete.format(podcast_id=another_podcast.id)
        response = await client.get(url, allow_redirects=False)
        mocked_os_remove.assert_called()
        expected_remove_files = [
            os.path.join(settings.RESULT_AUDIO_PATH, episode.file_name),
            os.path.join(settings.RESULT_RSS_PATH, f"{another_podcast.publish_id}.xml"),
        ]
        actual_remove_files = [
            call_args[0][0] for call_args in mocked_os_remove.call_args_list
        ]
        assert actual_remove_files == expected_remove_files

    assert response.status == 302
    assert response.headers["Location"] == urls_tpl.podcasts_list

    with pytest.raises(peewee.DoesNotExist):
        await db_objects.get(Podcast, id=another_podcast.id)
        await db_objects.get(Episode, id=episode.id)

    podcast = await db_objects.get(Podcast, id=podcast.id)
    assert podcast is not None
