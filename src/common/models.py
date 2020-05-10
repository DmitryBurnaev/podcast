from typing import List

import peewee
import peewee_async

database = peewee_async.PostgresqlDatabase(None)


# noinspection PyProtectedMember
class BaseModel(peewee.Model):
    """ Base model with db Meta """

    id: int = None  # auto matching field by peewee

    class Meta:
        database = database
        db_table = NotImplemented

    def to_dict(self, field_names: List[str]):
        field_names = field_names or list(self.__class__._meta.sorted_field_names)
        return {field: getattr(self, field) for field in field_names}

    @classmethod
    async def create_async(cls, db_objects: peewee_async.Manager, **kwargs) -> "BaseModel":
        return await db_objects.create(cls, **kwargs)
