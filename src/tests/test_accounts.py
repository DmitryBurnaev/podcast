import crypt
import uuid
from datetime import datetime, timedelta

import settings
from modules.auth.models import User, UserInvite
from .conftest import make_cookie


class SignInViewTestCase:
    path = "/sign-in/"

    async def test_signin__get_html__ok(self, unauth_client):
        response = await unauth_client.get(self.path)
        assert response.status == 200
        content = await response.text()
        assert "Please sign in" in content

    async def test_signin__ok(self, unauth_client, web_app):
        username, password = f"u_{uuid.uuid4().hex}"[:10], "password"
        await web_app.objects.create(User, username=username, password=crypt.crypt(password))
        request_data = {"username": username, "password": password}
        response = await unauth_client.post(self.path, data=request_data, allow_redirects=False)
        assert response.status == 302
        location = response.headers["Location"]
        assert str(web_app.router["index"].url_for()), location

        response = await unauth_client.get(location, allow_redirects=False)
        assert response.status == 200
        content = await response.text()
        assert "podcasts" in content

    async def test_signin__bad_request__redirect__ok(self, unauth_client, urls):
        response = await unauth_client.post(self.path, data={}, allow_redirects=False)
        assert response.status == 302
        assert urls.sign_in == response.headers["Location"]

    async def test_signin__user_not_found__fail(self, unauth_client):
        request_data = {"username": "fake_user", "password": "password"}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert "User fake_user was not found" in content

    async def test_signin__password_missing__fail(self, unauth_client):
        response = await unauth_client.post(self.path, data={"username": "fake_user"})
        content = await response.text()
        assert "password" in content
        assert "required field" in content


class SignUpViewTestCase:
    path = "/sign-up/"

    async def test_signup__get_html__ok(self, unauth_client):
        response = await unauth_client.request("GET", self.path)
        assert response.status == 200
        content = await response.text()
        assert "Please sign Up" in content

    async def test_signup__ok(self, unauth_client, user_data, web_app, user_invite):
        username, password = user_data
        request_data = {"username": username, "password": password, "token": user_invite.token}
        response = await unauth_client.post(self.path, data=request_data, allow_redirects=False)
        assert response.status == 302
        location = response.headers["Location"]
        assert str(web_app.router["default_podcast_details"].url_for()) == location

        response = await unauth_client.get(location, allow_redirects=False)
        assert response.status == 200
        content = await response.text()
        assert "podcasts" in content

        user = await web_app.objects.get(User.select().where(User.username == username))
        assert user is not None

    async def test_signup__check_invite__ok(
        self, unauth_client, user_data, db_objects, user_invite
    ):
        username, password = user_data
        request_data = {"username": username, "password": password, "token": user_invite.token}
        await unauth_client.post(self.path, data=request_data, allow_redirects=False)
        user = await db_objects.get(User.select().where(User.username == username))
        saved_user_invite = await db_objects.get(
            UserInvite.select().where(UserInvite.id == user_invite.id)
        )
        assert user is not None
        assert saved_user_invite.user == user
        assert saved_user_invite.is_applied

    async def test_signup__bad_request__check_redirect__fail(self, unauth_client):
        response = await unauth_client.post(self.path, data={}, allow_redirects=False)
        assert response.status == 302
        assert response.headers["Location"] == self.path

    async def test_signup__username_too_large__fail(self, unauth_client):
        request_data = {"username": "fake_user_" * 30, "password": "password"}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert "Input data is invalid" in content
        assert "username" in content
        assert "max length is 10" in content

    async def test_signup__password_missing__fail(self, unauth_client):
        response = await unauth_client.post(self.path, data={"username": "fake_user"})
        content = await response.text()
        assert "password" in content
        assert "required field" in content

    async def test_signup__user_already_exists__fail(
        self, unauth_client, user_data, web_app, user_invite
    ):
        username, password = user_data
        await web_app.objects.create(User, username=username, password=crypt.crypt(password))
        request_data = {"username": username, "password": password, "token": user_invite.token}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert f"{username} already exists" in content

    async def test_signup__token_is_missed__fail(self, unauth_client):
        request_data = {"username": "username", "password": "password", "token": ""}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert "Input data is invalid: {&#39;token&#39;: [&#39;min length is 32&#39;]}" in content

    async def test_signup__token_is_expired__fail(self, unauth_client, user, db_objects):
        token = f"{uuid.uuid4().hex}"
        await db_objects.create(
            UserInvite,
            email="test@test.com",
            token=token,
            created_by=user,
            expired_at=datetime.utcnow() - timedelta(hours=1),
        )

        request_data = {"username": "username", "password": "password", "token": token}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert "Invitation link is unavailable" in content

    async def test_signup__token_is_applied__fail(self, unauth_client, user, db_objects):
        token = f"{uuid.uuid4().hex}"
        await db_objects.create(
            UserInvite,
            email="test@test.com",
            token=token,
            created_by=user,
            expired_at=datetime.utcnow() - timedelta(hours=1),
        )

        request_data = {"username": "username", "password": "password", "token": token}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert "Invitation link is unavailable" in content


class CheckAccessTestCase:
    sign_in_url = "/sign-in/"

    async def test_get_objects___user_unauth__fail(self, unauth_client, login_required_urls):
        for url in login_required_urls:
            response = await unauth_client.get(url, allow_redirects=False)
            assert response.status == 302, f"Couldn't get ok response for {url}"
            location = response.headers["Location"]
            assert_message = f"Couldn't get correct location for {url}: location: {location}"
            assert location == self.sign_in_url, assert_message

    @staticmethod
    async def test_check_owners(db_objects, user_data, unauth_client, check_for_owner_urls):
        handlers = {
            "get": unauth_client.get,
            "post": unauth_client.post,
        }
        with db_objects.allow_sync():
            username, password = user_data
            another_user = User.create(username=username, password=password)

        make_cookie(unauth_client, {"user": another_user.id})

        for url in check_for_owner_urls:
            handler = handlers[url.method]
            response = await handler(url.url, allow_redirects=False)
            assert response.status == url.status_code, f"Couldn't get expected response for {url}"


class CreateInviteTestCase:
    path = "/api/auth/invite/"
    test_email = "test@test.com"

    async def test_create_invite__ok(self, client, user, db_objects, mocked_auth_send):

        response = await client.post(self.path, data={"email": self.test_email})
        with db_objects.allow_sync():
            created_token: UserInvite = (
                UserInvite.select().order_by(UserInvite.created_at.desc()).first()
            )

        response_data = await response.json()
        assert response.status == 201
        assert response_data["id"] == created_token.id
        assert response_data["token"] == created_token.token
        assert response_data["email"] == self.test_email
        assert response_data["created_by"] == user.id

        link = f"{settings.SITE_URL}/sign-up/?invite={created_token.token}"
        expected_body = (
            f"<p>Hello! :) You have been invited to {settings.SITE_URL}</p>"
            f"<p>Please follow the link </p>"
            f"<p><a href={link}>{link}</a></p>"
        )
        mocked_auth_send.assert_called_once_with(
            recipient_email=self.test_email,
            subject="Welcome to podcast.devpython.ru",
            html_content=expected_body,
        )

    async def test_create_invite__no_email__ok(self, client, user, db_objects, mocked_auth_send):
        response = await client.post(self.path)
        with db_objects.allow_sync():
            created_token: UserInvite = (
                UserInvite.select().order_by(UserInvite.created_at.desc()).first()
            )

        response_data = await response.json()
        assert response.status == 201
        assert response_data["id"] == created_token.id
        assert response_data["token"] == created_token.token
        assert response_data["email"] is None
        assert response_data["created_by"] == user.id
        assert not mocked_auth_send.called

    async def test_create_invite__unauth__fail(self, unauth_client):
        response = await unauth_client.post(self.path, allow_redirects=False)
        assert response.status == 302
        assert response.headers["Location"] == "/sign-in/"

    async def test_create_invite__invalid_email__fail(self, client, mocked_auth_send):
        response = await client.post(self.path, data={"email": "fake email"})
        response_data = await response.json()
        assert response.status == 400
        assert response_data["message"] == "Input data is invalid"
        assert "email" in response_data["details"]
        assert not mocked_auth_send.called
