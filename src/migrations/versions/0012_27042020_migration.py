""" 
Created_at: 27 Apr. 2020 16:27:03
Target: USERS: create invites

"""
from datetime import datetime

import peewee
from migrations.models import database

from common.models import database, BaseModel
from common.utils import database_init
from migrations.utils import create_tables, remove_tables

previous = "0011_26042020_migration"


class User(BaseModel):
    ...

    class Meta:
        db_table = "auth_users"


class UserInvite(BaseModel):
    """ Simple model for save users in DB """

    user = peewee.ForeignKeyField(User, null=True, unique=True, on_delete="SET NULL")
    email = peewee.CharField(max_length=32, null=True)
    token = peewee.CharField(unique=True, index=True, max_length=32, null=False)
    is_applied = peewee.BooleanField(default=False, null=False)
    expired_at = peewee.DateTimeField(null=False)
    created_at = peewee.DateTimeField(default=datetime.utcnow, null=False)
    created_by = peewee.ForeignKeyField(User, null=False, on_delete="CASCADE")

    class Meta:
        db_table = "auth_invites"


models = [UserInvite]


def upgrade():
    database_init(database)
    create_tables(models)


def downgrade():
    database_init(database)
    remove_tables(models)
