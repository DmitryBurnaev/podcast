""" 
Created_at: 12 Oct. 2019 08:58:56
Target: Episodes: add status column

"""

from playhouse.migrate import *

from migrations.models import database


previous = "0004_07102019_migration"
STATUS_NEW = "new"


def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(
        migrator.add_column(
            "episodes",
            "status",
            CharField(max_length=16, default=STATUS_NEW, null=False),
        )
    )


def downgrade():
    migrator = PostgresqlMigrator(database)
    migrate(migrator.drop_column("episodes", "status"))
