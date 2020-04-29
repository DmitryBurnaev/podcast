from datetime import datetime

import peewee

from common.models import BaseModel


class User(BaseModel):
    """ Simple model for save users in DB """

    username = peewee.CharField(unique=True, index=True, max_length=10, null=False)
    password = peewee.CharField(max_length=256, null=False)
    is_active = peewee.BooleanField(default=True)

    def __repr__(self):
        return f"<User #{self.id} {self.username}"

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

    def __repr__(self):
        return f"<UserInvite #{self.id} {self.token}"

    class Meta:
        db_table = "auth_invites"
