import logging
import logging.config
import os
import uuid
from functools import partial
from typing import Optional

import boto3
from aiohttp import web

import settings
from common.redis import RedisClient


def get_logger(name: str = None):
    """ Getting configured logger """
    logging.config.dictConfig(settings.LOGGING)
    _logger = logging.getLogger(name or "app")
    return _logger


logger = get_logger(__name__)


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


def database_init(db):
    db.init(
        settings.DATABASE["name"],
        host=settings.DATABASE["host"],
        port=settings.DATABASE["port"],
        user=settings.DATABASE["username"],
        password=settings.DATABASE["password"],
    )
    return db


def upload_process_hook(filename: str, chunk: int):
    """
    Allows to handle uploading to Yandex.Cloud (S3) and update redis state (for user's progress).
    It is called by `s3.upload_file` (`common.utils.upload_file`)
    """

    redis_client = RedisClient()
    filename = os.path.basename(filename)
    event_key = redis_client.get_key_by_filename(filename)
    event_data = redis_client.get(event_key)
    processed_bytes = event_data.get("processed_bytes", 0) + chunk
    event_data.update({
        "status": "uploading_to_cloud",
        "processed_bytes": processed_bytes
    })
    logger.debug(
        "Uploading for %s: %.f %", filename, (event_data.get("total_bytes", 0) / processed_bytes) * 100
    )
    redis_client.set(event_key, event_data, ttl=settings.DOWNLOAD_EVENT_REDIS_TTL)


def upload_file(filename: str, remote_directory: str = None) -> Optional[str]:
    """ Allows to upload src_filename to Yandex.Cloud (aka AWS S3) """

    src_filename = os.path.join(settings.RESULT_AUDIO_PATH, filename)

    name, ext = filename.rsplit(".", maxsplit=1)
    dst_filename = os.path.join(remote_directory, f"{name}_{uuid.uuid4().hex}.{ext}")
    session = boto3.session.Session(
        aws_access_key_id=settings.S3_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_AWS_SECRET_ACCESS_KEY,
        region_name="ru-central1"
    )
    s3 = session.client(service_name='s3', endpoint_url=settings.S3_STORAGE_URL)

    logger.info("Upload for %s (target = %s) started.", filename, dst_filename)
    try:
        result_uploading = s3.upload_file(
            src_filename,
            settings.S3_BUCKET_NAME,
            dst_filename,
            Callback=partial(upload_process_hook, filename),
            ExtraArgs={'ACL': 'public-read'}
        )
    except Exception as error:
        logger.exception(
            "Shit! We could not upload file %s to %s. Error: %s",
            filename, settings.S3_STORAGE_URL, error
        )
        return

    result_url = f"{settings.S3_STORAGE_URL}/{dst_filename}"
    logger.info("Great! uploading for %s (%s) was done!", filename, dst_filename)
    logger.debug("Finished uploading for file %s. \n Result url is %s", dst_filename, result_url)
    logger.debug(result_uploading)
    return result_url
