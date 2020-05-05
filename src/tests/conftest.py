import functools
import json
import random
import time
import uuid
from collections import namedtuple
from typing import Tuple, List, NamedTuple
from unittest.mock import Mock
from hashlib import blake2b

import peewee_async
import pytest
from youtube_dl import YoutubeDL

from app import create_app
from common.models import database
from common.redis import RedisClient
from common.storage import StorageS3
from common.utils import database_init
from modules.auth.models import User
from modules.podcast.models import Podcast, Episode
from modules.youtube import utils as youtube_utils
from .mocks import MockYoutube, MockRedisClient, MockS3Client


def get_user_data() -> Tuple[str, str]:
    return f"u_{uuid.uuid4().hex}"[:10], "password"


def db_allow_sync(func):
    """ Simple decorator for using peewee in sync mode """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db_objects = peewee_async.Manager(database_init(database))
        with db_objects.allow_sync():
            return func(*args, **kwargs)

    return wrapper


def make_cookie(client, data):
    session_data = {"session": data, "created": int(time.time())}
    value = json.dumps(session_data)
    client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": value})
    return client


def generate_video_id() -> str:
    """ Generate YouTube-like videoID """
    return blake2b(key=bytes(str(time.time()), encoding="utf-8"), digest_size=6).hexdigest()[:11]


def teardown_module(module):
    print(f"module teardown {module}")
    Episode.truncate_table()
    Podcast.truncate_table()
    User.truncate_table()


@pytest.fixture
def web_app(loop):
    return loop.run_until_complete(create_app())


@pytest.fixture
def client(loop, aiohttp_client, web_app, user):
    client = loop.run_until_complete(aiohttp_client(web_app))
    client = make_cookie(client, {"user": user.id})
    return client


@pytest.fixture
def unauth_client(loop, aiohttp_client, web_app):
    client = loop.run_until_complete(aiohttp_client(web_app))
    return client


@pytest.fixture()
def user_data() -> Tuple[str, str]:
    return get_user_data()


@pytest.fixture
def episode_data(podcast: Podcast, user: User) -> dict:
    source_id = generate_video_id()
    episode_data = {
        "source_id": source_id,
        "podcast_id": podcast.id,
        "title": f"episode_{source_id}",
        "watch_url": f"fixture_url_{source_id}",
        "length": random.randint(1, 100),
        "description": f"description_{source_id}",
        "image_url": f"image_url_{source_id}",
        "file_name": f"file_name_{source_id}",
        "file_size": random.randint(1, 100),
        "author_id": None,
        "status": "new",
        "created_by_id": user.id,
    }
    return episode_data


@pytest.fixture
def podcast_data(user: User) -> dict:
    return {
        "publish_id": str(time.time()),
        "name": f"podcast_{time.time()}",
        "created_by_id": user.id,
    }


@pytest.fixture
def db_objects():
    return peewee_async.Manager(database_init(database))


@pytest.fixture
def user(db_objects):
    with db_objects.allow_sync():
        username, password = get_user_data()
        yield User.create(username=username, password=password)


@pytest.fixture
def podcast(db_objects, user, podcast_data):
    with db_objects.allow_sync():
        yield Podcast.create(**podcast_data)


@pytest.fixture
def episode(db_objects, episode_data):
    with db_objects.allow_sync():
        yield Episode.create(**episode_data)


@pytest.fixture
def mocked_youtube(monkeypatch) -> MockYoutube:
    mock_youtube = MockYoutube()
    monkeypatch.setattr(YoutubeDL, "__new__", lambda *_, **__: mock_youtube)  # noqa
    yield mock_youtube
    del mock_youtube


@pytest.fixture
def mocked_redis(monkeypatch) -> MockRedisClient:
    mock_redis_client = MockRedisClient()
    monkeypatch.setattr(RedisClient, "__new__", lambda *_, **__: mock_redis_client)  # noqa
    yield mock_redis_client
    del mock_redis_client


@pytest.fixture
def mocked_s3(monkeypatch) -> MockS3Client:
    mock_s3_client = MockS3Client()
    monkeypatch.setattr(StorageS3, "__new__", lambda *_, **__: mock_s3_client)  # noqa
    yield mock_s3_client
    del mock_s3_client


@pytest.fixture
def mocked_ffmpeg(monkeypatch) -> Mock:
    mocked_ffmpeg_function = Mock()
    monkeypatch.setattr(youtube_utils, "ffmpeg_preparation", mocked_ffmpeg_function)
    yield mocked_ffmpeg_function
    del mocked_ffmpeg_function


named_urls = namedtuple(
    "url",
    [
        "sign_in",
        "sign_up",
        "sign_out",
        "progress",
        "progress_api",
        "podcasts_list",
        "podcasts_details",
        "podcasts_delete",
        "podcasts_default",
        "episodes_list",
        "episodes_details",
        "episodes_delete",
        "episodes_download",
    ],
)


@pytest.fixture
def urls_tpl() -> named_urls:
    return named_urls(
        sign_in="/sign-in/",
        sign_up="/sign-up/",
        sign_out="/sign-out/",
        progress="/progress/",
        progress_api="/api/progress/",
        podcasts_list="/podcasts/",
        podcasts_details="/podcasts/{podcast_id}/",
        podcasts_delete="/podcasts/{podcast_id}/delete/",
        podcasts_default="/podcasts/default/",
        episodes_list="/podcasts/{podcast_id}/episodes/",
        episodes_details="/podcasts/{podcast_id}/episodes/{episode_id}/",
        episodes_delete="/podcasts/{podcast_id}/episodes/{episode_id}/delete/",
        episodes_download="/podcasts/{podcast_id}/episodes/{episode_id}/download/",
    )


@pytest.fixture
def urls(urls_tpl: named_urls, podcast, episode) -> named_urls:
    urls_dict = {
        url_name: url.format(podcast_id=podcast.id, episode_id=episode.id)
        for url_name, url in urls_tpl._asdict().items()
    }
    return named_urls(**urls_dict)


class CheckOwnerUrl(NamedTuple):
    url: str
    method: str
    status_code: int = 403


@pytest.fixture
def check_for_owner_urls(urls) -> List[CheckOwnerUrl]:
    return [
        CheckOwnerUrl(url=urls.podcasts_details, method="post"),
        CheckOwnerUrl(url=urls.podcasts_delete, method="get"),
        CheckOwnerUrl(url=urls.episodes_list, method="get"),
        CheckOwnerUrl(url=urls.episodes_details, method="post"),
        CheckOwnerUrl(url=urls.episodes_delete, method="get"),
    ]


@pytest.fixture
def login_required_urls(urls):
    return (
        urls.podcasts_list,
        urls.podcasts_details,
        urls.episodes_list,
        urls.episodes_details,
    )
