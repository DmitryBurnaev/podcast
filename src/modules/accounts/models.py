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
        db_table = "users"
