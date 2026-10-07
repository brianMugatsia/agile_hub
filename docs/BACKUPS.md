# Backup and recovery

Database backups and media backups are separate responsibilities. Configure encrypted, automated PostgreSQL backups (including point-in-time recovery where available) and separately back up uploaded media and any deployment-specific files. The repository's `backups/` directory is not a production backup target and is ignored by Git.

## Minimum controls

- Encrypt backups in transit and at rest; store copies outside the production account/region.
- Limit access to backup credentials and regularly rotate them.
- Define retention to meet business, legal, and privacy requirements.
- Alert on missed or failed backup jobs and monitor storage capacity.
- Keep database and media backup timestamps coordinated.
- Never place credentials, user exports, or production data in source control.

## Restore testing

At least quarterly and after major schema changes, restore a recent database and matching media copy into an isolated environment. Verify migrations, login, representative sale/inventory/finance records, and application checks; record the restore duration and any data loss window. Do not test a restore by overwriting production. Document a deployment-specific recovery point objective, recovery time objective, and authorized decision-maker.