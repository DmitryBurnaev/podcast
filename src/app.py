import asyncio
import logging

import aiohttp_i18n
import aioredis
import jinja2
import peewee_async
import aiohttp_jinja2
import aiohttp_debugtoolbar
import rq
import sentry_sdk
import uvloop

from aiohttp import web
from aiohttp_session import session_middleware, SimpleCookieStorage
from aiohttp_session.redis_storage import RedisStorage
from redis import Redis
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

import settings
import app_i18n
from common import context_processors
from common import jinja_filters
from common.middlewares import request_user_middleware
from common.jinja_template_tags import tags
from common.models import database
from common.utils import get_logger, database_init

logger = get_logger()
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class PodcastWebApp(web.Application):
    """ Extended web Application for podcast-specific logic """

    rq_queue: rq.Queue = None
    objects: peewee_async.Manager = None
    redis_pool: aioredis.ConnectionsPool = None
    gettext_translation: app_i18n.AioHttpGettextTranslations = None


async def shutdown_app(app):
    """ Safe close server """
    app.redis_pool.close()
    await app.redis_pool.wait_closed()
    await app.objects.close()


async def create_app() -> PodcastWebApp:
    """ Prepare application """
    redis_pool = await aioredis.create_pool(settings.REDIS_CON)
    session_engine = SimpleCookieStorage() if settings.TEST_MODE else RedisStorage(redis_pool)
    middlewares = [
        session_middleware(session_engine),
        request_user_middleware,
        aiohttp_i18n.babel_middleware,
    ]

    if settings.DEBUG:
        middlewares.append(aiohttp_debugtoolbar.middleware)

    app = PodcastWebApp(middlewares=middlewares, logger=logger, debug=settings.DEBUG)
    app.redis_pool = redis_pool
    app.gettext_translation = app_i18n.aiohttp_translations
    app.on_shutdown.append(shutdown_app)

    # db conn
    app.database = database_init(database)
    app.database.set_allow_sync(False)
    app.objects = peewee_async.Manager(app.database)

    app["static_root_url"] = settings.STATIC_URL
    jinja_env = aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(settings.TEMPLATE_PATH),
        context_processors=[
            aiohttp_jinja2.request_processor,
            context_processors.podcast_items,
            context_processors.mobile_app_web_view,
        ],
        filters={
            "datetime_format": jinja_filters.datetime_format,
            "human_length": jinja_filters.human_length,
        },
        extensions=["jinja2.ext.i18n"],
    )
    jinja_env.globals.update(tags)
    jinja_env.install_gettext_translations(app.gettext_translation)
    if settings.DEBUG:
        aiohttp_debugtoolbar.setup(app, intercept_redirects=False)

    # make routes
    from urls import urls as app_routes

    for route in app_routes:
        app.router.add_route(**route.as_dict)

    app.router.add_static("/static", settings.STATIC_PATH, name="static")

    app.logger = get_logger()
    app.rq_queue = rq.Queue(
        name="youtube_downloads",
        connection=Redis(*settings.REDIS_CON),
        default_timeout=settings.RQ_DEFAULT_TIMEOUT,
    )

    if settings.SENTRY_DSN:
        sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        sentry_sdk.init(settings.SENTRY_DSN, integrations=[AioHttpIntegration(), sentry_logging])

    return app


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    web_app = loop.run_until_complete(create_app())

    try:
        web.run_app(web_app, host=settings.APP_HOST, port=settings.APP_PORT)
    except KeyboardInterrupt:
        logger.debug("Keyboard Interrupt ^C")

    logger.debug("Server has been stopped")
