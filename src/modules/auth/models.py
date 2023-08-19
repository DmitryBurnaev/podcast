import secrets
from datetime import datetime

import peewee

from common.models import BaseModel
from modules.auth.hasher import PBKDF2PasswordHasher


class User(BaseModel):
    """Simple model for save users in DB"""

    email = peewee.CharField(max_length=32, index=True, null=False, unique=True)
    password = peewee.CharField(max_length=256, null=False)
    is_active = peewee.BooleanField(default=True)
    is_superuser = peewee.BooleanField(default=False)

    def __repr__(self):
        return f"<User #{self.id} {self.email}"

    class Meta:
        db_table = "auth_users"

    @classmethod
    def make_password(cls, raw_password: str):
        hasher = PBKDF2PasswordHasher()
        return hasher.encode(raw_password)

    def verify_password(self, raw_password: str):
        hasher = PBKDF2PasswordHasher()
        return hasher.verify(raw_password, encoded=str(self.password))


class UserInvite(BaseModel):
    """Simple model for save users in DB"""

    TOKEN_MAX_LENGTH = 32

    user = peewee.ForeignKeyField(User, null=True, unique=True, on_delete="SET NULL")
    email = peewee.CharField(max_length=32, null=True)
    token = peewee.CharField(unique=True, index=True, max_length=TOKEN_MAX_LENGTH, null=False)
    is_applied = peewee.BooleanField(default=False, null=False)
    expired_at = peewee.DateTimeField(null=False)
    created_at = peewee.DateTimeField(default=datetime.utcnow, null=False)
    created_by = peewee.ForeignKeyField(User, null=False, on_delete="CASCADE")

    def __repr__(self):
        return f"<UserInvite #{self.id} {self.token}"

    class Meta:
        db_table = "auth_invites"

    @classmethod
    def generate_token(cls):
        return secrets.token_urlsafe()[: cls.TOKEN_MAX_LENGTH]
