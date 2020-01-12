from typing import List

import peewee
import peewee_async

database = peewee_async.PostgresqlDatabase(None)


# noinspection PyProtectedMember
class BaseModel(peewee.Model):
    """ Base model with db Meta """

    class Meta:
        database = database

    def to_dict(self, field_names: List[str]):
        field_names = field_names or list(self.__class__._meta.sorted_field_names)
        return {field: getattr(self, field) for field in field_names}
