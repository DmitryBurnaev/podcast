import uuid
from _md5 import md5
from xml.sax.saxutils import escape

import peewee
from datetime import datetime
import peewee_async

from app_i18n import aiohttp_translations
from modules.auth.models import User
from common.models import BaseModel
from common.utils import get_logger

_ = aiohttp_translations.gettext
logger = get_logger(__name__)


class Podcast(BaseModel):
    """ Simple model for saving podcast in DB """

    publish_id = peewee.CharField(unique=True, index=True, max_length=32, null=False)
    name = peewee.CharField(index=True, max_length=256, null=False)
    description = peewee.TextField(null=True)
    logo_path = peewee.CharField(max_length=256, null=True)
    created_at = peewee.DateTimeField(default=datetime.utcnow, null=False)
    updated_at = peewee.DateTimeField(default=datetime.utcnow, null=False)
    created_by = peewee.ForeignKeyField(User, related_name="podcasts")
    download_automatically = peewee.BooleanField(default=True)
    rss_link = peewee.CharField(max_length=128, null=True)

    class Meta:
        order_by = ("created_at",)
        db_table = "podcast_podcasts"

    def __str__(self):
        return f'<Podcast #{self.id} "{self.name}">'

    @classmethod
    async def get_all(cls, objects, request_user_id):
        """ Return all podcasts """
        return await objects.execute(cls.select().where(cls.created_by_id == request_user_id))

    async def get_episodes_async(self, objects: peewee_async.Manager, request_user_id: int):
        """ Return all episodes for current podcast item """
        return await objects.execute(self.get_episodes(request_user_id))

    def get_episodes(self, request_user_id: int) -> peewee.Query:
        """ Return peewee query for """
        return (
            Episode.select()
            .where(Episode.podcast_id == self.id, Episode.created_by_id == request_user_id)
            .order_by(Episode.published_at.desc(), Episode.created_at.desc())
        )

    @classmethod
    async def create_first_podcast(cls, objects, user_id: int):
        description = _(
            "Add new episode -> wait for downloading -> copy podcast RSS-link "
            "-> past this link to your podcast application -> enjoy"
        )
        return await objects.create(
            Podcast,
            **dict(
                publish_id=cls.generate_publish_id(),
                name=_("Your first podcast"),
                description=description,
                created_by_id=user_id,
            ),
        )

    @classmethod
    def generate_publish_id(cls):
        return md5(uuid.uuid4().hex.encode("utf-8")).hexdigest()[::2]


class Episode(BaseModel):
    """ Simple model for saving episodes in DB """

    STATUS_NEW = "new"
    STATUS_DOWNLOADING = "downloading"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"
    STATUS_ERROR = "error"

    STATUS_CHOICES = (
        (STATUS_NEW, _("New")),
        (STATUS_DOWNLOADING, _("Downloading")),
        (STATUS_PUBLISHED, _("Published")),
        (STATUS_ARCHIVED, _("Archived")),
        (STATUS_ERROR, _("Error")),
    )
    PROGRESS_STATUSES = (STATUS_DOWNLOADING, STATUS_ERROR)

    source_id = peewee.CharField(index=True, max_length=32, null=False)
    podcast = peewee.ForeignKeyField(Podcast, related_name="episodes")
    title = peewee.CharField(max_length=256, null=False)
    watch_url = peewee.CharField(max_length=128, null=True)
    remote_url = peewee.CharField(max_length=128, null=True)
    image_url = peewee.CharField(max_length=512, null=True)
    length = peewee.IntegerField(null=True, default=0)
    description = peewee.TextField(null=True, default="")
    file_name = peewee.CharField(max_length=128, null=True)
    file_size = peewee.IntegerField(null=True, default=0)
    author = peewee.CharField(max_length=256, null=True)
    status = peewee.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NEW, null=False)
    created_at = peewee.DateTimeField(default=datetime.utcnow)
    published_at = peewee.DateTimeField(null=True)
    created_by = peewee.ForeignKeyField(User, related_name="podcasts")

    class Meta:
        order_by = ("-published_at",)
        db_table = "podcast_episodes"

    def __str__(self):
        return f'<Episode #{self.id} {self.source_id} [{self.status}] "{self.title[:10]}..." >'

    @classmethod
    async def get_in_progress(cls, objects, user_id) -> peewee.Query:
        """ Return downloading episodes """
        return await objects.execute(
            cls.select()
            .where(cls.status.in_(cls.PROGRESS_STATUSES), cls.created_by_id == user_id)
            .order_by(Episode.created_at.desc())
        )

    @property
    def safe_image_url(self) -> str:
        return escape(self.image_url or "")

    @property
    def content_type(self) -> str:
        file_name = self.file_name or "unknown"
        return f"audio/{file_name.split('.')[-1]}"
