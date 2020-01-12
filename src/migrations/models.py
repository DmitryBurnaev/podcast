import datetime

import peewee

database = peewee.PostgresqlDatabase(None)


class MigrationHistory(peewee.Model):
    """ Simple model for saving applied migrations to DB """

    migration_name = peewee.CharField(unique=True, max_length=256, null=False)
    migration_details = peewee.TextField(null=True)
    applied_at = peewee.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        db_table = "migrations_history"
        database = database
