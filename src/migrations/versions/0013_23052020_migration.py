""" 
Created_at: 23 May. 2020 09:28:22
Target: USERS: add email | remove username

"""
from playhouse.migrate import *
from migrations.models import database

previous = "0012_27042020_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(
        migrator.rename_column("auth_users", "username", "email"),
        migrator.alter_column_type(
            "auth_users", "email", CharField(max_length=128, index=True, null=False, unique=True)
        ),
        migrator.add_column("auth_users", "is_superuser", BooleanField(default=False)),
    )


def downgrade():
    migrator = PostgresqlMigrator(database)
    migrate(
        migrator.rename_column("auth_users", "email", "username"),
        migrator.drop_column("auth_users", "is_superuser"),
    )
