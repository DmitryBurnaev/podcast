from typing import List

import peewee
import peewee_async

database = peewee_async.PostgresqlDatabase(None)


# noinspection PyProtectedMember
class BaseModel(peewee.Model):
    """Base model with db Meta"""

    id: int = None  # auto matching field by peewee

    class Meta:
        database = database
        db_table = NotImplemented

    def to_dict(self, field_names: List[str]):
        field_names = field_names or list(self.__class__._meta.sorted_field_names)
        return {field: getattr(self, field) for field in field_names}

    @classmethod
    async def async_create(cls, db_objects: peewee_async.Manager, **kwargs) -> "BaseModel":
        return await db_objects.create(cls, **kwargs)

    @classmethod
    async def async_get(cls, db_objects: peewee_async.Manager, **filter_kwargs) -> "BaseModel":
        query = cls.select()
        for filter_name, filter_value in filter_kwargs.items():
            field, _, criteria = filter_name.partition("__")
            if criteria in ("eq", ""):
                query = query.where(getattr(cls, field) == filter_value)
            elif criteria == "gt":
                query = query.where(getattr(cls, field) > filter_value)
            elif criteria == "lt":
                query = query.where(getattr(cls, field) < filter_value)
            else:
                raise NotImplementedError(f"Unexpected criteria: {criteria}")

        return await db_objects.get(query)

    async def async_update(self, db_objects):
        return await db_objects.update(self)
