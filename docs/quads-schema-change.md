# QUADS Schema Change

## Overview

Database schema changes (also known as schema migrations) are necessary operations that help evolve our database structure to accommodate new features, improve performance, or fix data modeling issues. In our PostgreSQL database, we perform these updates periodically to maintain and enhance our application's data layer.

### Why We Need Schema Changes

1. **Feature Requirements**: New application features often require new data structures or modifications to existing ones
2. **Performance Optimization**: Schema changes can improve query performance through better indexing or table restructuring
3. **Data Integrity**: Updates may be needed to enforce new business rules or data constraints
4. **Technical Debt**: Addressing suboptimal data modeling decisions from earlier development stages


### Migration Process

1. **Migration Script Generation**
   - Generate migration script:

        ```bash
        cd /opt/quads/
        flask --app quads.server.app db migrate -m "description of schema changes"
        ```

        > [!NOTE]
        > The migration directory will be located in the QUADS buildroot directory udner: `/opt/quads/migrations`

        > [!WARNING]
        > These commands must be run from the `/opt/quads/` directory

   - This will create a new migration script in the `migrations` directory.
   - The migration script will automatically generate 2 methods, the upgrade and the downgrade which will do a complete drop of all tables and the subsequent reconstruction
   - We need to modify the script to only drop and add the columns that we added to our schema

        > [!NOTE]
        > The migration script will be named like `071677379d4e_description_of_schema_changes.py`

2. **Migration Script Modification**
   - On the `upgrade` method, add the columns that we added to our schema
   - On the `downgrade` method, drop the columns that we added to our schema

        ```python
        """Hostname metadata

        Revision ID: 071677379d4e
        Revises: 253ba446570d
        Create Date: 2025-01-17 06:17:12.541605

        """
        from alembic import op
        import sqlalchemy as sa
        from sqlalchemy.dialects import postgresql

        # revision identifiers, used by Alembic.
        revision = '071677379d4e'
        down_revision = '253ba446570d'
        branch_labels = None
        depends_on = None


        def upgrade():
            op.add_column('hosts', sa.Column('rack', sa.String()))
            op.add_column('hosts', sa.Column('uloc', sa.String()))
            op.add_column('hosts', sa.Column('blade', sa.String()))


        def downgrade():
            op.drop_column('hosts', 'rack')
            op.drop_column('hosts', 'uloc')
            op.drop_column('hosts', 'blade')
        ```

3. **Upgrade**
   - Run the migration script:

        ```bash
        flask --app quads.server.app db upgrade
        ```

4. **Downgrade**
   - Run the migration script:

        ```bash
        flask --app quads.server.app db downgrade
        ```

### Upgrading to Latest Schema

When deploying QUADS or updating to a new version, you may need to upgrade your database to match the latest schema. The repository includes all necessary migration scripts, making this process straightforward:

1. **Ensure Database Service is Running**
   ```bash
   systemctl status postgresql
   ```

2. **Navigate to QUADS Directory**
   ```bash
   cd /opt/quads/
   ```

3. **Run Database Upgrade**
   ```bash
   flask --app quads.server.app db upgrade
   ```

This will automatically apply any pending migrations in the correct order to bring your database schema up to date with the latest version.

> [!NOTE]
> Always backup your database before performing schema upgrades in production environments.

> [!WARNING]
> If you encounter any errors during the upgrade process, check the PostgreSQL logs for detailed information.

