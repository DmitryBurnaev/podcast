import http
import logging
import uuid
from abc import ABCMeta
from time import time
from datetime import datetime, timedelta

import aiohttp_jinja2
from aiohttp import web
from cerberus import Validator
from jwt import PyJWTError

import settings
from app_i18n import aiohttp_translations
from common.excpetions import (
    InvalidParameterError,
    AuthenticationFailedError,
    Forbidden,
)
from common.views import BaseApiView
from modules.auth.hasher import PBKDF2PasswordHasher, get_salt
from modules.auth.models import User, UserInvite
from common.utils import redirect, add_message, is_mobile_app, send_email
from common.decorators import (
    anonymous_required,
    login_required,
    errors_wrapped,
    errors_api_wrapped,
    json_response,
)
from modules.auth.utils import encode_jwt, decode_jwt
from modules.podcast.models import Podcast


logger = logging.getLogger(__name__)
_ = aiohttp_translations.gettext


class BaseAuthView(BaseApiView, metaclass=ABCMeta):
    def _get_url(self, router_name):
        return str(self.request.app.router[router_name].url_for())

    def _login(self, user):
        self.request.session["user"] = str(user.id)
        self.request.session["time"] = time()

    def _login_and_redirect(self, user, redirect_to="index"):
        self._login(user)
        redirect_to = "default_podcast_details" if is_mobile_app(self.request) else redirect_to
        redirect(self.request, redirect_to)

    @staticmethod
    def _password_match(password_1: str, password_2: str):
        if password_1 != password_2:
            raise InvalidParameterError(
                details={
                    "password_1": _("Passwords must be equal"),
                    "password_2": _("Passwords must be equal"),
                }
            )


class SignInView(BaseAuthView):
    """ Simple Login user by email """

    template_name = "auth/sign_in.html"
    model_class = User
    validator = Validator(
        {
            "email": {"type": "string", "minlength": 1, "maxlength": 128, "required": True},
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
        """ Check email and login """
        cleaned_data = await self._validate()
        email = cleaned_data["email"]
        password = cleaned_data["password"]

        if not email:
            add_message(self.request, "Provide both email and password", kind="warning")
            redirect(self.request, "sign_in")

        try:
            user = await self.authenticate(email, password)
            self._login_and_redirect(user)
        except User.DoesNotExist:
            logger.info("Not found user with email [%s]", email)
            raise AuthenticationFailedError

        redirect(self.request, "sign_in")

    async def authenticate(self, email, password):
        user = await self.request.app.objects.get(User, User.email == email)
        hasher = PBKDF2PasswordHasher()
        if not hasher.verify(password, encoded=user.password):
            logger.error("Password didn't verify with encoded version (email: [%s])", email)
            raise AuthenticationFailedError

        return user


class SignUpView(BaseAuthView):
    """ Create new user in db """

    template_name = "auth/sign_up.html"
    model_class = User
    validator = Validator(
        {
            "email": {
                "type": "string",
                "maxlength": 128,
                "required": True,
                "empty": False,
                "regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
            },
            "password_1": {
                "type": "string",
                "minlength": 6,
                "maxlength": 32,
                "required": True,
                "regex": "^\w+$",
            },
            "password_2": {
                "type": "string",
                "minlength": 6,
                "maxlength": 32,
                "required": True,
                "regex": "^\w+$",
            },
            "token": {"type": "string", "required": True, "empty": False},
        }
    )

    @anonymous_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        invite_token = self.request.query.get("t", "")
        user_invite = await self._get_user_invite(self.request.app.objects, invite_token)
        if user_invite:
            return {"token": user_invite.token, "email": user_invite.email}

        add_message(self.request, "Provided token is missed or incorrect", kind="danger")
        return {}

    @json_response
    @errors_api_wrapped
    async def post(self):
        """ Check is email unique and create new User """
        cleaned_data = await self._validate()
        email = cleaned_data["email"]
        password_1 = cleaned_data["password_1"]
        password_2 = cleaned_data["password_2"]
        invite_token = cleaned_data.get("token")
        db_objects = self.request.app.objects
        self._password_match(password_1, password_2)

        user_invite = await self._get_user_invite(db_objects, invite_token)
        if not user_invite:
            details = "Invitation link is expired or unavailable"
            logger.error("Couldn't signup user token: %s | details: %s", invite_token, details)
            raise InvalidParameterError(details=details)

        if await db_objects.count(User.select().where(User.email ** email)):
            raise InvalidParameterError(details=f"User with email '{email}' already exists")

        user = await User.async_create(
            db_objects, email=email, password=User.make_password(password_1),
        )
        user_invite.user = user
        user_invite.is_applied = True
        await user_invite.async_update(db_objects)
        await Podcast.create_first_podcast(self.request.app.objects, user.id)
        self._login(user)
        return {"redirect_url": self._get_url("index")}, http.HTTPStatus.OK

    @staticmethod
    async def _get_user_invite(db_objects, invite_token: str) -> UserInvite:
        try:
            user_invite = await UserInvite.async_get(
                db_objects, token=invite_token, is_applied=False, expired_at__gt=datetime.utcnow(),
            )
        except UserInvite.DoesNotExist:
            logger.error(f"Couldn't get UserInvite invite_token={invite_token}.")
            user_invite = None

        return user_invite


class SignOutView(web.View):
    """ Remove current user from session """

    @login_required
    async def get(self):
        self.request.session.pop("user")
        add_message(self.request, "You are logged out")
        redirect(self.request, "index")


class InviteUserAPIView(BaseApiView):
    """ Remove current user from session """

    model_class = User
    validator = Validator(
        {
            "email": {
                "type": "string",
                "required": True,
                "empty": False,
                "regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
            },
        }
    )
    INVITE_EXPIRATION = 3 * 24 * 3600  # 3 day

    @json_response
    @login_required
    @errors_api_wrapped
    async def post(self):
        cleaned_data = await self._validate()
        email = cleaned_data["email"]
        token = UserInvite.generate_token()
        expired_at = datetime.utcnow() + timedelta(seconds=self.INVITE_EXPIRATION)
        logger.info("INVITE: create for %s (expired %s) token [%s]", email, expired_at, token)

        async with self.db_objects.transaction():
            user_invite = await UserInvite.async_create(
                self.db_objects,
                created_by=self.user,
                email=email,
                token=token,
                expired_at=expired_at,
            )
            logger.info("Invite object %r created. Sending message...", user_invite)
            await self._send_email(user_invite)

        return self.model_to_dict(user_invite), http.HTTPStatus.CREATED

    @staticmethod
    async def _send_email(user_invite: UserInvite):
        link = f"{settings.SITE_URL}/sign-up/?t={user_invite.token}"
        body = (
            f"<p>Hello! :) You have been invited to {settings.SITE_URL}</p>"
            f"<p>Please follow the link </p>"
            f"<p><a href={link}>{link}</a></p>"
        )
        await send_email(
            recipient_email=user_invite.email,
            subject="Welcome to podcast.devpython.ru",
            html_content=body.strip(),
        )


class ResetPasswordAPIView(BaseApiView):
    """ Remove current user from session """

    model_class = User
    validator = Validator(
        {
            "email": {
                "type": "string",
                "required": False,
                "regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
            },
            "user_id": {"type": "integer", "required": False},
        }
    )
    INVITE_EXPIRED_DAYS = 30

    @json_response
    @login_required
    @errors_api_wrapped
    async def post(self):
        db_objects = self.request.app.objects
        cleaned_data = await self._validate(allow_empty=True)
        email = cleaned_data.get("email")
        user_id = cleaned_data.get("user_id")
        filter_kwargs = {}
        if user_id:
            filter_kwargs["id"] = user_id
        elif email:
            filter_kwargs["email"] = email

        if not filter_kwargs:
            raise InvalidParameterError(details="Neither user_id nor email was given")

        if not self.request.user.is_superuser:
            raise Forbidden(details="Reset password is allowed only for superuser")

        try:
            user = await User.async_get(db_objects, **filter_kwargs)
        except User.DoesNotExist:
            logger.info("Not found user with filter [%s]", filter_kwargs)
            raise InvalidParameterError(details="Email or UserID is invalid (user not found)")

        token = self._generate_token(user)
        await self._send_email(user, token)
        return {"user_id": user.id, "token": token}, http.HTTPStatus.OK

    @staticmethod
    async def _send_email(user: User, token: str):
        link = f"{settings.SITE_URL}/change-password/?t={token}"
        body = (
            f"<p>You can reset your password for {settings.SITE_URL}</p>"
            f"<p>Please follow the link </p>"
            f"<p><a href={link}>{link}</a></p>"
        )
        await send_email(
            recipient_email=user.email,
            subject="Welcome back to podcast.devpython.ru",
            html_content=body.strip(),
        )

    @staticmethod
    def _generate_token(user: User):
        payload = {
            "user_id": user.id,
            "email": user.email,
            "jti": f"token-{uuid.uuid4()}",  # JWT ID
            "slt": get_salt(),
        }
        return encode_jwt(payload, expiration_seconds=settings.RESET_PASSWORD_LINK_EXP)


class ChangePasswordView(BaseAuthView):
    """ Create new user in db """

    template_name = "auth/change_password.html"
    model_class = User
    validator = Validator(
        {
            "password_1": {
                "type": "string",
                "minlength": 6,
                "maxlength": 32,
                "required": True,
                "regex": "^\w+$",
            },
            "password_2": {
                "type": "string",
                "minlength": 6,
                "maxlength": 32,
                "required": True,
                "regex": "^\w+$",
            },
            "token": {"type": "string", "empty": False, "required": True},
        }
    )

    @anonymous_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        token = self.request.query.get("t", "")
        try:
            user = await self.authenticate_user(self.request.app.objects, token)
        except AuthenticationFailedError as error:
            logger.error(f"We couldn't recognize recover password token: {error}")
            add_message(self.request, "Provided token is missed or incorrect", kind="danger")
            return {}

        return {"token": token, "email": user.email}

    @json_response
    @anonymous_required
    @errors_api_wrapped
    async def post(self):
        """ Check is email unique and create new User """
        cleaned_data = await self._validate()
        password_1 = cleaned_data["password_1"]
        password_2 = cleaned_data["password_2"]
        jwt_token = cleaned_data["token"]
        self._password_match(password_1, password_2)

        user = await self.authenticate_user(self.db_objects, jwt_token)
        user.password = User.make_password(password_1)
        await user.async_update(self.db_objects)
        self._login(user)
        return {"redirect_url": self._get_url("index")}, http.HTTPStatus.OK

    @staticmethod
    async def authenticate_user(db_objects, jwt_token) -> User:
        logger.info("Logging via JWT auth. Got token: %s", jwt_token)

        try:
            jwt_payload = decode_jwt(jwt_token)
        except PyJWTError as err:
            msg = _("Invalid token header. Token could not be decoded as JWT.")
            logger.exception("Bad jwt token: %s", err)
            raise AuthenticationFailedError(details=msg)

        try:
            user = await User.async_get(db_objects, id=jwt_payload["user_id"], is_active=True)
        except User.DoesNotExist:
            raise AuthenticationFailedError(details=_("Active user not found or token is invalid."))

        return user
