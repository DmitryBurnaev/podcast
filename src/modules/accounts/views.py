import crypt
from time import time
from hmac import compare_digest as compare_hash

import aiohttp_jinja2
from aiohttp import web
from cerberus import Validator

from common.excpetions import NotAuthenticatedError, InvalidParameterError
from common.views import BaseApiView
from modules.accounts.models import User
from common.utils import redirect, add_message, is_mobile_app
from common.decorators import anonymous_required, login_required, errors_wrapped
from modules.podcast.models import Podcast


def _login_and_redirect(request, user, redirect_to="index"):
    request.session["user"] = str(user.id)
    request.session["time"] = time()

    redirect_to = "default_podcast_details" if is_mobile_app(request) else redirect_to
    redirect(request, redirect_to)


class SignInView(BaseApiView):
    """ Simple Login user by username """

    template_name = "accounts/sign_in.html"
    model_class = User
    validator = Validator(
        {
            "username": {
                "type": "string",
                "minlength": 1,
                "maxlength": 10,
                "required": True,
            },
            "password": {
                "type": "string",
                "minlength": 1,
                "maxlength": 32,
                "required": True,
            },
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
            add_message(
                self.request, f"Provide both username and password", kind="warning"
            )
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

    template_name = "accounts/sign_up.html"
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
        }
    )

    @anonymous_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        return {}

    @anonymous_required
    @errors_wrapped
    async def post(self):
        """ Check is username unique and create new User """
        cleaned_data = await self._validate()
        username = cleaned_data["username"]
        password = cleaned_data["password"]

        if await self.request.app.objects.count(
            User.select().where(User.username ** username)
        ):
            add_message(self.request, f"{username} already exists", kind="danger")
            redirect(self.request, "sign_up")

        user = await self.request.app.objects.create(
            User, username=username, password=crypt.crypt(password)
        )
        await Podcast.create_first_podcast(self.request.app.objects, user.id)

        _login_and_redirect(self.request, user, redirect_to="default_podcast_details")


class SignOutView(web.View):
    """ Remove current user from session """

    @login_required
    async def get(self):
        self.request.session.pop("user")
        add_message(self.request, "You are logged out")
        redirect(self.request, "index")
