import crypt
import uuid
from collections import namedtuple
from typing import List

import pytest

from modules.accounts.models import User
from .conftest import make_cookie


async def test_signin__get_method__ok(unauth_client, urls):
    response = await unauth_client.get("/sign-in/")
    assert response.status == 200
    content = await response.text()
    assert "Please sign in" in content


async def test_signin__correct_username_password__ok(unauth_client, web_app, urls):
    username, password = f"u_{uuid.uuid4().hex}"[:10], "password"
    await web_app.objects.create(
        User, username=username, password=crypt.crypt(password)
    )
    request_data = {"username": username, "password": password}
    response = await unauth_client.post(
        urls.sign_in, data=request_data, allow_redirects=False
    )
    assert response.status == 302
    location = response.headers["Location"]
    assert str(web_app.router["index"].url_for()), location

    response = await unauth_client.get(location, allow_redirects=False)
    assert response.status == 200
    content = await response.text()
    assert "podcasts" in content


async def test_signin__bad_request__check_redirect__ok(unauth_client, urls):
    response = await unauth_client.post(urls.sign_in, data={}, allow_redirects=False)
    assert response.status == 302
    assert urls.sign_in == response.headers["Location"]


async def test_signin__user_not_found__fail(unauth_client, urls):
    request_data = {"username": "fake_user", "password": "password"}
    response = await unauth_client.post(urls.sign_in, data=request_data)
    content = await response.text()
    assert "User fake_user was not found" in content


async def test_signin__password_missing__fail(unauth_client, urls):
    request_data = {
        "username": "fake_user",
    }
    response = await unauth_client.post(urls.sign_in, data=request_data)
    content = await response.text()
    assert "password" in content
    assert "required field" in content


async def test_signup__get_html__ok(unauth_client, urls):
    response = await unauth_client.request("GET", urls.sign_up)
    assert response.status == 200
    content = await response.text()
    assert "Please sign Up" in content


async def test_signup__correct_username_password__ok(
    unauth_client, user_data, web_app, urls
):
    username, password = user_data
    request_data = {"username": username, "password": password}
    response = await unauth_client.post(
        urls.sign_up, data=request_data, allow_redirects=False
    )
    assert response.status == 302
    location = response.headers["Location"]
    assert str(web_app.router["default_podcast_details"].url_for()) == location

    response = await unauth_client.get(location, allow_redirects=False)
    assert response.status == 200
    content = await response.text()
    assert "podcasts" in content

    user = await web_app.objects.get(User.select().where(User.username == username))
    assert user is not None


async def test_signup__bad_request__check_redirect__ok(unauth_client, urls):
    response = await unauth_client.post(urls.sign_up, data={}, allow_redirects=False)
    assert response.status == 302
    assert response.headers["Location"] == urls.sign_up


async def test_signup__username_too_large__fail(unauth_client, urls):
    request_data = {"username": "fake_user_" * 30, "password": "password"}
    response = await unauth_client.post(urls.sign_up, data=request_data)
    content = await response.text()
    assert "Input data is invalid" in content
    assert "username" in content
    assert "max length is 10" in content


async def test_signup__password_missing__fail(unauth_client, urls):
    request_data = {
        "username": "fake_user",
    }
    response = await unauth_client.post(urls.sign_up, data=request_data)
    content = await response.text()
    assert "password" in content
    assert "required field" in content


async def test_signup__user_already_exists__fail(
    unauth_client, user_data, web_app, urls
):
    username, password = user_data
    await web_app.objects.create(
        User, username=username, password=crypt.crypt(password)
    )
    request_data = {"username": username, "password": password}
    response = await unauth_client.post(urls.sign_up, data=request_data)
    content = await response.text()
    assert f"{username} already exists" in content


@pytest.fixture
def login_required_urls(urls):
    return (
        urls.podcasts_list,
        urls.podcasts_details,
        urls.episodes_list,
        urls.episodes_details,
    )


async def test_get_objects___user_not_authorized__fail(
    unauth_client, urls, login_required_urls
):
    for url in login_required_urls:
        response = await unauth_client.get(url, allow_redirects=False)
        assert response.status == 302, f"Couldn't get ok response for {url}"
        location = response.headers["Location"]
        assert (
            location == urls.sign_in
        ), f"Couldn't get correct location for {url}: location: {location}"


created_by_url = namedtuple("created_by_url", ["url", "method", "status_code"])


@pytest.fixture
def created_by_urls(urls) -> List[created_by_url]:
    return [
        created_by_url(url=urls.podcasts_details, method="post", status_code=403),
        created_by_url(url=urls.podcasts_delete, method="get", status_code=403),
        created_by_url(url=urls.episodes_list, method="get", status_code=403),
        created_by_url(url=urls.episodes_details, method="post", status_code=403),
        created_by_url(url=urls.episodes_delete, method="get", status_code=403),
    ]


async def test_get_objects___user_not_equal_created_by__fail(
    db_objects, user_data, unauth_client, urls, created_by_urls
):
    handlers = {
        "get": unauth_client.get,
        "post": unauth_client.post,
    }
    with db_objects.allow_sync():
        username, password = user_data
        another_user = User.create(username=username, password=password)
    make_cookie(unauth_client, {"user": another_user.id})

    for by_url in created_by_urls:
        handler = handlers[by_url.method]
        response = await handler(by_url.url, allow_redirects=False)
        assert (
            response.status == by_url.status_code
        ), f"Couldn't get expected response for {by_url.url}"
