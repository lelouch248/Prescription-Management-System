# Database migrations

Migrations are registered in `src/backend/migrations.py` and applied in numeric order inside transactions. Before any pending migration, HealthVault makes a consistent SQLite snapshot under `data/migration_snapshots/`. Startup runs `PRAGMA integrity_check` after migration and refuses to continue on failure.

Rules for future migrations:

1. Increment `DATABASE_SCHEMA_VERSION`.
2. Add an immutable `migration_<n>` function and register it.
3. Never rewrite an already released migration.
4. Test upgrade from the previous schema and restore from the pre-migration snapshot.
5. Keep export and backup format versions independent from database schema versions.
