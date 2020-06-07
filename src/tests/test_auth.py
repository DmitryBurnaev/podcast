import uuid
from datetime import datetime, timedelta

import pytest

import settings
from modules.auth.models import User, UserInvite
from modules.auth.utils import decode_jwt, encode_jwt
from .conftest import make_cookie


class TestSignInView:
    path = "/sign-in/"

    async def test_signin__get_html__ok(self, unauth_client):
        response = await unauth_client.get(self.path)
        assert response.status == 200
        content = await response.text()
        assert "Please sign in" in content

    async def test_signin__ok(self, unauth_client, web_app):
        email, password = f"u_{uuid.uuid4().hex}"[:10], "password"

        await web_app.objects.create(User, email=email, password=User.make_password(password))
        request_data = {"email": email, "password": password}
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
        request_data = {"email": "fake_user@test.com", "password": "password"}
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.text()
        assert "Authentication credentials are invalid" in content

    async def test_signin__password_missing__fail(self, unauth_client):
        response = await unauth_client.post(self.path, data={"email": "fake_user"})
        content = await response.text()
        assert "password" in content
        assert "required field" in content


class TestSignUpView:
    path = "/sign-up/"

    async def test_signup__get_html__ok(self, unauth_client):
        response = await unauth_client.request("GET", self.path)
        assert response.status == 200
        content = await response.text()
        assert "Please sign Up" in content

    async def test_signup__ok(self, unauth_client, user_data, web_app, user_invite):
        email, password = user_data
        request_data = {
            "email": email,
            "password_1": password,
            "password_2": password,
            "token": user_invite.token,
        }
        response = await unauth_client.post(self.path, data=request_data, allow_redirects=False)
        content = await response.json()
        assert response.status == 200
        assert content["redirect_url"] == str(web_app.router["index"].url_for())
        user = await User.async_get(web_app.objects, email=email)
        assert user is not None

    async def test_signup__check_invite__ok(
        self, web_app, unauth_client, user_data, db_objects, user_invite
    ):
        email, password = user_data
        request_data = {
            "email": email,
            "password_1": password,
            "password_2": password,
            "token": user_invite.token,
        }
        response = await unauth_client.post(self.path, data=request_data, allow_redirects=False)
        content = await response.json()
        assert response.status == 200
        assert content["redirect_url"] == str(web_app.router["index"].url_for())

        user = await User.async_get(db_objects, email=email)
        saved_user_invite = await UserInvite.async_get(db_objects, id=user_invite.id)
        assert user is not None
        assert saved_user_invite.user == user
        assert saved_user_invite.is_applied

    @pytest.mark.parametrize(
        "request_data, error_details",
        [
            [
                {
                    "email": ("fake_user_" * 30 + "@t.com"),
                    "password_1": "123456",
                    "password_2": "123456",
                    "token": "t",
                },
                {"email": ["max length is 128"]},
            ],
            [
                {"email": "", "password_1": "123456", "password_2": "123456", "token": "t"},
                {"email": ["empty values not allowed"]},
            ],
            [
                {"email": "f@t.com", "password_1": "123456", "token": "t"},
                {"password_2": ["required field"]},
            ],
            [
                {"email": "f@t.com", "password_1": "header", "password_2": "footer"},
                {"token": ["required field"]},
            ],
            [
                {"email": "f@t.com", "password_1": "header", "password_2": "footer", "token": "t"},
                {"password_1": "Passwords must be equal", "password_2": "Passwords must be equal"},
            ],
            [
                {"email": "f@t.com", "password_1": "header", "password_2": "footer", "token": ""},
                {"token": ["empty values not allowed"]},
            ],
        ],
    )
    async def test_signup__request_data_invalid__fail(
        self, unauth_client, request_data, error_details
    ):
        response = await unauth_client.post(self.path, data=request_data)
        content = await response.json()
        assert content == {"message": "Input data is invalid", "details": error_details}

    async def test_signup__user_already_exists__fail(
        self, unauth_client, user_data, web_app, user_invite
    ):
        email, password = user_data
        await web_app.objects.create(User, email=email, password=password)
        request_data = {
            "email": email,
            "password_1": password,
            "password_2": password,
            "token": user_invite.token,
        }
        response = await unauth_client.post(self.path, data=request_data)
        response_data = await response.json()
        assert response_data == {
            "message": "Input data is invalid",
            "details": f"User with email '{email}' already exists",
        }

    async def test_signup__token_is_expired__fail(self, unauth_client, user, db_objects):
        token = f"{uuid.uuid4().hex}"
        await UserInvite.async_create(
            db_objects,
            email="test@test.com",
            token=token,
            created_by=user,
            expired_at=datetime.utcnow() - timedelta(hours=1),
        )

        response = await unauth_client.post(
            self.path,
            data={
                "email": "token-test@test.com",
                "password_1": "password",
                "password_2": "password",
                "token": token,
            },
        )
        response_data = await response.json()
        assert response.status == 400
        assert response_data == {
            "message": "Input data is invalid",
            "details": "Invitation link is expired or unavailable",
        }

    async def test_signup__token_is_applied__fail(self, unauth_client, user, db_objects):
        token = f"{uuid.uuid4().hex}"
        await UserInvite.async_create(
            db_objects,
            email="test@test.com",
            token=token,
            created_by=user,
            expired_at=datetime.utcnow() - timedelta(hours=1),
        )

        response = await unauth_client.post(
            self.path,
            data={
                "email": "token-test@test.com",
                "password_1": "password",
                "password_2": "password",
                "token": token,
            },
        )
        response_data = await response.json()
        assert response.status == 400
        assert response_data == {
            "message": "Input data is invalid",
            "details": "Invitation link is expired or unavailable",
        }


class TestCheckAccessApiView:
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
            email, password = user_data
            another_user = User.create(email=email, password=password)

        make_cookie(unauth_client, {"user": another_user.id})

        for url in check_for_owner_urls:
            handler = handlers[url.method]
            response = await handler(url.url, allow_redirects=False)
            assert response.status == url.status_code, f"Couldn't get expected response for {url}"


class TestUserInviteApiView:
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

        link = f"{settings.SITE_URL}/sign-up/?t={created_token.token}"
        expected_body = (
            f"<p>Hello! :) You have been invited to {settings.SITE_URL}</p>"
            f"<p>Please follow the link </p>"
            f"<p><a href={link}>{link}</a></p>"
        )
        mocked_auth_send.assert_called_once_with(
            recipient_email=self.test_email,
            subject=f"Welcome to {settings.SITE_URL}",
            html_content=expected_body,
        )

    @pytest.mark.parametrize(
        "request_data, error_details",
        [
            [
                {"email": "fake-email"},
                {
                    "email": [
                        "value does not match regex "
                        "'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'"
                    ]
                },
            ],
            [{"email": ""}, {"email": ["empty values not allowed"]}],
            [{}, "Request body can not be empty"],
        ],
    )
    async def test_create_invite__invalid_request__fail(self, client, request_data, error_details):
        response = await client.post(self.path, data=request_data)
        assert response.status == 400
        response_data = await response.json()
        assert response_data == {"message": "Input data is invalid", "details": error_details}

    async def test_create_invite__unauth__fail(self, unauth_client):
        response = await unauth_client.post(self.path, allow_redirects=False)
        assert response.status == 302
        assert response.headers["Location"] == "/sign-in/"


class TestResetPasswordAPIView:
    path = "/api/auth/reset-password/"
    test_email = "test@test.com"

    @pytest.mark.parametrize("reset_by", ["id", "email"])
    async def test_reset_by_email__ok(self, client, user, db_objects, mocked_auth_send, reset_by):
        if reset_by == "id":
            data = {"user_id": user.id}
        else:
            data = {"email": user.email}

        user.is_superuser = True
        await user.async_update(db_objects)

        response = await client.post(self.path, json=data)
        response_data = await response.json()
        assert response.status == 200
        token = response_data["token"]

        assert response_data["user_id"] == user.id
        assert token is not None
        assert decode_jwt(response_data["token"])["user_id"] == user.id

        link = f"{settings.SITE_URL}/change-password/?t={token}"
        expected_body = (
            f"<p>You can reset your password for {settings.SITE_URL}</p>"
            f"<p>Please follow the link </p>"
            f"<p><a href={link}>{link}</a></p>"
        )
        mocked_auth_send.assert_called_once_with(
            recipient_email=user.email,
            subject=f"Welcome back to {settings.SITE_URL}",
            html_content=expected_body,
        )

    async def test_user_is_anonymous__fail(self, unauth_client):
        response = await unauth_client.post(self.path, json={}, allow_redirects=False)
        assert response.status == 401

    async def test_user_is_not_superuser__fail(self, client, user):
        response = await client.post(self.path, data={"email": user.email})
        response_data = await response.json()
        assert response.status == 403
        assert response_data == {
            "details": "Reset password is allowed only for superuser",
            "message": "You don't have permission to perform this action",
        }


class TestChangePasswordView:
    path = "/change-password/"

    async def test_get_rendered_page__ok(self, unauth_client, user):
        token = encode_jwt({"user_id": user.id})
        response = await unauth_client.get(self.path, params={"t": token})
        assert response.status == 200
        content = await response.text()
        assert token in content
        assert user.email in content

    async def test_get_rendered_page__token_expired__fail(self, unauth_client, user):
        token = encode_jwt({"user_id": user.id}, expiration_seconds=-10)
        response = await unauth_client.get(self.path, params={"t": token})
        assert response.status == 200
        content = await response.text()
        assert token not in content
        assert "Provided token is missed or incorrect" in content

    async def test_change_password_success__ok(self, unauth_client, user, web_app):
        token = encode_jwt({"user_id": user.id})
        new_password = "new123456"
        response = await unauth_client.post(
            self.path, data={"token": token, "password_1": new_password, "password_2": new_password}
        )
        assert response.status == 200
        response_data = await response.json()
        assert response_data["redirect_url"] == str(web_app.router["index"].url_for())

        user = await User.async_get(web_app.objects, id=user.id)
        assert user.verify_password(new_password)

    @pytest.mark.parametrize(
        "request_data, error_details",
        [
            [{"password_1": "123456", "token": "t"}, {"password_2": ["required field"]}],
            [{"password_1": "header", "password_2": "footer"}, {"token": ["required field"]}],
            [
                {"password_1": "header", "password_2": "footer", "token": "t"},
                {"password_1": "Passwords must be equal", "password_2": "Passwords must be equal"},
            ],
            [
                {"password_1": "header", "password_2": "footer", "token": ""},
                {"token": ["empty values not allowed"]},
            ],
        ],
    )
    async def test_invalid_request__fail(self, unauth_client, request_data, error_details):
        response = await unauth_client.post(self.path, data=request_data)
        assert response.status == 400
        response_data = await response.json()
        assert response_data == {"message": "Input data is invalid", "details": error_details}

    async def test_token_expired__fail(self, unauth_client, user):
        token = encode_jwt({"user_id": user.id}, expiration_seconds=-10)
        new_password = "new123456"
        response = await unauth_client.post(
            self.path, data={"token": token, "password_1": new_password, "password_2": new_password}
        )
        assert response.status == 401
        response_data = await response.json()
        assert response_data == {
            "details": "Invalid token header. Token could not be decoded as JWT.",
            "message": "Authentication credentials are invalid",
        }

    async def test_token_invalid__fail(self, unauth_client, user):
        token = encode_jwt({"user_id": user.id}) + "fake-post"
        new_password = "new123456"
        response = await unauth_client.post(
            self.path, data={"token": token, "password_1": new_password, "password_2": new_password}
        )
        assert response.status == 401
        response_data = await response.json()
        assert response_data == {
            "details": "Invalid token header. Token could not be decoded as JWT.",
            "message": "Authentication credentials are invalid",
        }

    async def test_user_inactive__fail(self, unauth_client, user, db_objects):
        user.is_active = False
        await user.async_update(db_objects)
        token = encode_jwt({"user_id": user.id})
        new_password = "new123456"
        response = await unauth_client.post(
            self.path, data={"token": token, "password_1": new_password, "password_2": new_password}
        )
        assert response.status == 401
        response_data = await response.json()
        assert response_data == {
            "message": "Authentication credentials are invalid",
            "details": f"Active user #{user.id} not found or token is invalid.",
        }

    async def test_user_does_not_exist__fail(self, unauth_client, user, db_objects):
        user_id = "fake-user-id"
        token = encode_jwt({"user_id": user_id})
        new_password = "new123456"
        response = await unauth_client.post(
            self.path, data={"token": token, "password_1": new_password, "password_2": new_password}
        )
        assert response.status == 401
        response_data = await response.json()
        assert response_data == {
            "message": "Authentication credentials are invalid",
            "details": f"Active user #{user_id} not found or token is invalid.",
        }

    async def test_user_already_authenticated__fail(self, client, web_app):
        response = await client.post(self.path, data={}, allow_redirects=False)
        assert response.status == 302
        location = response.headers["Location"]
        assert str(web_app.router["sign_out"].url_for()), location
