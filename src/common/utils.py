import logging
import logging.config

import aiohttp
from aiohttp import web

import settings
from common.excpetions import SendRequestError


def get_logger(name: str = None):
    """ Getting configured logger """
    logging.config.dictConfig(settings.LOGGING)
    return logging.getLogger(name or "app")


def redirect(
    request, router_name: str, *, permanent=False, url: str = None, reason="HttpFound", **kwargs
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


def database_init(db):
    db.init(
        settings.DATABASE["name"],
        host=settings.DATABASE["host"],
        port=settings.DATABASE["port"],
        user=settings.DATABASE["username"],
        password=settings.DATABASE["password"],
    )
    return db


async def send_email(recipient_email: str, subject: str, html_content: str):
    """ Allows to send email via Sendgrid API """

    request_url = f"https://api.sendgrid.com/{settings.SENDGRID_API_VERSION}/mail/send"
    request_data = {
        "personalizations": [{"to": [{"email": recipient_email}], "subject": subject}],
        "from": {"email": settings.EMAIL_FROM},
        "content": [{"type": "text/html", "value": html_content}],
    }
    request_header = {"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"}
    request_logger = get_logger(__name__)
    request_logger.info("Send request to %s. Data: %s", request_url, request_data)

    async with aiohttp.ClientSession() as session:
        async with session.post(request_url, json=request_data, headers=request_header) as response:
            if response.status > 299:
                response_text = await response.text()
                raise SendRequestError(
                    f"Couldn't send email to {recipient_email}",
                    f"Got status code: {response.status}; response text: {response_text}",
                    response_status=response.status,
                    request_url=request_url,
                )
            else:
                request_logger.info(
                    "Email sent to %s. Status code: %s", recipient_email, response.status
                )
