import http
import logging
import crypt
from time import time
from datetime import datetime, timedelta
from hmac import compare_digest as compare_hash

import aiohttp_jinja2
import peewee
from aiohttp import web
from cerberus import Validator

import settings
from app_i18n import aiohttp_translations
from common.excpetions import (
    InvalidParameterError,
    InviteTokenInvalidationError,
    NotAuthenticatedError,
)
from common.views import BaseApiView
from modules.auth.models import User, UserInvite
from common.utils import redirect, add_message, is_mobile_app, send_email
from common.decorators import (
    anonymous_required,
    login_required,
    errors_wrapped,
    errors_api_wrapped,
    json_response,
)
from modules.podcast.models import Podcast


logger = logging.getLogger(__name__)
_ = aiohttp_translations.gettext


def _login_and_redirect(request, user, redirect_to="index"):
    request.session["user"] = str(user.id)
    request.session["time"] = time()
    print(request.session)
    redirect_to = "default_podcast_details" if is_mobile_app(request) else redirect_to
    redirect(request, redirect_to)


class SignInView(BaseApiView):
    """ Simple Login user by username """

    template_name = "auth/sign_in.html"
    model_class = User
    validator = Validator(
        {
            "username": {"type": "string", "minlength": 1, "maxlength": 10, "required": True},
            "password": {"type": "string", "minlength": 1, "maxlength": 32, "required": True},
        }
    )

    @anonymous_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        return {}

    @anonymous_required
    @errors_wrapped
    async def post(self):
        """ Check username and login """
        cleaned_data = await self._validate()
        username = cleaned_data["username"]
        password = cleaned_data["password"]

        if not username:
            add_message(self.request, f"Provide both username and password", kind="warning")
            redirect(self.request, "sign_in")
        try:
            user = await self.authenticate(username, password)
            _login_and_redirect(self.request, user)
        except User.DoesNotExist:
            raise InvalidParameterError(f"User {username} was not found")

        redirect(self.request, "sign_in")

    async def authenticate(self, username, password):
        user = await self.request.app.objects.get(User, User.username == username)
        if not compare_hash(user.password, crypt.crypt(password, user.password)):
            raise NotAuthenticatedError
        return user


class SignUpView(BaseApiView):
    """ Create new user in db """

    template_name = "auth/sign_up.html"
    model_class = User
    validator = Validator(
        {
            "username": {
                "type": "string",
                "minlength": 3,
                "maxlength": 10,
                "required": True,
                "regex": "^\w+$",
            },
            "password": {
                "type": "string",
                "minlength": 6,
                "maxlength": 32,
                "required": True,
                "regex": "^\w+$",
            },
            "token": {"type": "string", "minlength": 32, "maxlength": 32, "required": True},
        }
    )

    @anonymous_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        token = self.request.query.get("invite", "")
        return {"token": token[:32]}

    @anonymous_required
    @errors_wrapped
    async def post(self):
        """ Check is username unique and create new User """
        cleaned_data = await self._validate()
        username = cleaned_data["username"]
        password = cleaned_data["password"]
        invite_token = cleaned_data["token"]
        try:
            user_invite: UserInvite = await self.request.app.objects.get(
                UserInvite.select().where(
                    UserInvite.token == invite_token,
                    UserInvite.is_applied == False,  # noqa
                    UserInvite.expired_at > datetime.utcnow(),
                )
            )
        except peewee.DoesNotExist as err:
            logger.exception("Couldn't invite user: %s", err)
            raise InviteTokenInvalidationError(details=str(err))

        if await self.request.app.objects.count(User.select().where(User.username ** username)):
            add_message(self.request, f"{username} already exists", kind="danger")
            redirect(self.request, "sign_up")

        user = await self.request.app.objects.create(
            User, username=username, password=crypt.crypt(password)
        )
        user_invite.user = user
        user_invite.is_applied = True
        await self.request.app.objects.update(user_invite)
        await Podcast.create_first_podcast(self.request.app.objects, user.id)

        _login_and_redirect(self.request, user, redirect_to="default_podcast_details")


class SignOutView(web.View):
    """ Remove current user from session """

    @login_required
    async def get(self):
        self.request.session.pop("user")
        add_message(self.request, "You are logged out")
        redirect(self.request, "index")


class InviteUserView(BaseApiView):
    """ Remove current user from session """

    model_class = User
    validator = Validator(
        {
            "email": {
                "type": "string",
                "required": False,
                "regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
            },
        }
    )
    INVITE_EXPIRED_DAYS = 30

    @json_response
    @login_required
    @errors_api_wrapped
    async def post(self):
        cleaned_data = await self._validate()
        email = cleaned_data["email"]
        token = UserInvite.generate_token()
        expired_at = datetime.utcnow() + timedelta(days=self.INVITE_EXPIRED_DAYS)
        logger.info("INVITE: create for %s (expired %s) token [%s]", email, expired_at, token)
        user_invite: UserInvite = await self.request.app.objects.create(
            UserInvite, created_by=self.user, email=email, token=token, expired_at=expired_at
        )
        await self._send_email(user_invite)
        return self.model_to_dict(user_invite), http.HTTPStatus.CREATED

    @staticmethod
    async def _send_email(user_invite: UserInvite):
        link = f"{settings.SITE_URL}/sign-up/?invite={user_invite.token}"
        body = f"""
            <p>Hello! :) You have been invited to {settings.SITE_URL}</p>
            <p>Please follow the link </p>
            <p><a href={link}>{link}</a></p>
        """
        await send_email(
            recipient_email=user_invite.email,
            subject="Welcome to podcast.devpython.ru",
            html_content=body,
        )
