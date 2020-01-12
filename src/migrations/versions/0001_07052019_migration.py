""" 
Created_at: 07 May. 2019 20:17:07
Target: Creation (If does not exists) tables for models: Podcast, Publication( now - Episodes), User

"""
from datetime import datetime

import peewee

from common.models import database, BaseModel
from common.utils import database_init

previous = "0000"


class User(BaseModel):
    """ Migration version for model `modules.accounts.models.User` """

    username = peewee.CharField(unique=True, index=True, max_length=10, null=False)
    password = peewee.CharField(max_length=256, null=False)
    is_active = peewee.BooleanField(default=True)

    class Meta:
        db_table = "users"


class Podcast(BaseModel):
    """ Migration version for model `modules.podcast.models.Podcast`  """

    publish_id = peewee.CharField(unique=True, index=True, max_length=32, null=False)
    name = peewee.CharField(index=True, max_length=256, null=False)
    description = peewee.TextField(null=True)
    logo_path = peewee.CharField(max_length=256, null=True)
    created_at = peewee.DateTimeField(default=datetime.utcnow, null=False)
    updated_at = peewee.DateTimeField(default=datetime.utcnow, null=False)
    created_by = peewee.ForeignKeyField(User, related_name="podcasts")

    class Meta:
        order_by = ("created_at",)
        db_table = "podcasts"


class Publication(BaseModel):
    """ Migration version for model `modules.podcast.models.Episode` """

    source_id = peewee.CharField(index=True, max_length=32, null=False)
    podcast = peewee.ForeignKeyField(Podcast, related_name="episodes")
    title = peewee.CharField(max_length=256, null=False)
    watch_url = peewee.CharField(max_length=128, null=True)
    length = peewee.IntegerField(null=True, default=0)
    description = peewee.TextField(null=True, default="")
    image_url = peewee.CharField(max_length=512, null=True)
    file_name = peewee.CharField(max_length=128, null=True)
    file_size = peewee.IntegerField(null=True, default=0)
    author = peewee.CharField(max_length=256, null=True)
    downloaded = peewee.BooleanField(default=False)
    created_at = peewee.DateTimeField(default=datetime.utcnow)
    published_at = peewee.DateTimeField(default=datetime.utcnow)
    created_by = peewee.ForeignKeyField(User, related_name="podcasts")

    class Meta:
        order_by = ("-published_at",)
        db_table = "publications"  # old version of table name


models = (User, Podcast, Publication)


def upgrade():
    database_init(database)
    for model in models:
        model.create_table()


def downgrade():
    database_init(database)
    for model in models:
        model.drop_table()
