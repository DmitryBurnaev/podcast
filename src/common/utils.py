import logging
import logging.config

from aiohttp import web

import settings


def redirect(
    request,
    router_name: str,
    *,
    permanent=False,
    url: str = None,
    reason="HttpFound",
    **kwargs,
):
    """ Redirect to given URL name

    :param request: current request for web app
    :param router_name: router name for creating redirect url (used if url not specified)
    :param permanent: use permanent redirect
    :param url: directly set url for redirecting
    :param reason: Http reason for redirect moving ('HttpFound' by default)
    :param kwargs: url-kwargs for forming redirecting url
    :raises  `aiohttp.web.HTTPMovedPermanently` `aiohttp.web.HTTPFound`

    """

    if not url:
        for key in kwargs.keys():
            kwargs[key] = str(kwargs[key])
        url = request.app.router[router_name].url_for(**kwargs)
        if permanent:
            raise web.HTTPMovedPermanently(url, reason=reason)

    raise web.HTTPFound(url, reason=reason)


def add_message(request, message: str, title: str = None, kind: str = "info"):
    """ Put message into session """
    messages = request.session.get("messages", [])
    kind = "danger" if kind == "error" else kind
    message = {"title": title or "Podcasts informer", "message": message}
    messages.append((kind, message))
    request.session["messages"] = messages


async def get_object_or_404(request, model, **kwargs):
    """ Get object or raise HttpNotFound """
    try:
        return await request.app.objects.get(model, **kwargs)
    except model.DoesNotExist:
        raise web.HTTPNotFound()


def is_mobile_app(request):
    """ Detects requests from mobile application (It will change some view)"""
    user_agent = request.headers.get("User-Agent")
    return "mobile-app-web-view" in user_agent


def get_logger(name: str = None):
    """ Getting configured logger """
    logging.config.dictConfig(settings.LOGGING)
    _logger = logging.getLogger(name or "app")
    return _logger


def database_init(db):
    db.init(
        settings.DATABASE["name"],
        host=settings.DATABASE["host"],
        port=settings.DATABASE["port"],
        user=settings.DATABASE["username"],
        password=settings.DATABASE["password"],
    )
    return db
