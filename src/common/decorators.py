import logging
from aiohttp import web

from common.excpetions import BaseApplicationError, AuthenticationRequiredError
from common.utils import redirect, add_message


logger = logging.getLogger(__name__)


def json_response(func):
    """ Wrapper for view method, to return JsonResponse """

    async def wrapped(*args, **kwargs):
        content, status = await func(*args, **kwargs)
        return web.json_response(data=content, status=status)

    return wrapped


def login_api_required(func):
    # TODO: use more common approach to detecting user's auth
    async def wrapped(self, *args, **kwargs):
        if self.request.user is None:
            raise AuthenticationRequiredError(details="Unauth access to resource")

        return await func(self, *args, **kwargs)

    return wrapped


def login_required(func):
    """ Allow only auth users """

    async def wrapped(self, *args, **kwargs):
        if self.request.user is None:
            add_message(self.request, "LogIn to continue.")
            redirect(self.request, "sign_in")
        return await func(self, *args, **kwargs)

    return wrapped


def anonymous_required(func):
    """ Allow only anonymous users """

    async def wrapped(self, *args, **kwargs):
        if self.request.user is not None:
            add_message(self.request, "Please log-out to continue.")
            redirect(self.request, "index")
        return await func(self, *args, **kwargs)

    return wrapped


def errors_wrapped(func):
    """ Allow only anonymous users """

    async def wrapped(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except AuthenticationRequiredError as ex:
            logger.warning(f"Trying to use unauth access: {ex}")
            add_message(self.request, "LogIn to continue.")
            redirect(self.request, "sign_in")

        except BaseApplicationError as ex:
            message = getattr(ex, "message", None) or str(ex)
            details = getattr(ex, "details", None)
            if details:
                message = f"{message}: {details}"

            add_message(self.request, message, kind="error")
            raise web.HTTPFound(self.request.path)

    return wrapped


def errors_api_wrapped(func):
    """ Allow only anonymous users """

    async def wrapped(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as ex:
            message = getattr(ex, "message", None) or "Something went wrong"
            details = getattr(ex, "details", None) or str(ex)
            status_code = getattr(ex, "status_code", 500)
            logger.exception(
                "Couldn't perform action: %s. Error: %s, Details: %s", ex, message, details
            )
            return {"message": message, "details": details}, status_code

    return wrapped
