# Deployment

## Runtime configuration

Run Django with `config.settings.production`. Use a dedicated PostgreSQL database and least-privileged service account. Provide configuration through the deployment platform's secret/environment facility; never copy a real `.env` into an image or commit it.

Required values include:

- `SECRET_KEY`: unique, high-entropy secret, retained securely across deploys.
- `DEBUG=False`.
- `ALLOWED_HOSTS`: comma-separated production hostnames, without schemes.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`.
- `CSRF_TRUSTED_ORIGINS`: HTTPS origins, including scheme, for cross-host form posts.
- Email host and authentication settings if password reset or notifications by email are enabled.

`SECURE_SSL_REDIRECT` and HSTS are enabled by default in production. `USE_PROXY_SSL_HEADER=True` is appropriate only when a trusted reverse proxy overwrites the forwarded-protocol header. Configure the proxy to reject client-supplied forwarded headers; otherwise set it to `False`. Terminate TLS at the proxy and restrict direct access to the Django application server.

HSTS preload is deliberately opt-in. Enable `SECURE_HSTS_PRELOAD=True` only after confirming the apex domain and every subdomain can remain HTTPS-only; browser preload enrollment is a long-lived commitment and requires a separate submission. Django's deployment check may report `security.W021` while preload remains disabled.

## Release procedure

1. Build an immutable release image with pinned/locked dependencies and no `.env`, database, media, or log files.
2. Provision PostgreSQL, a private media volume/object store, email, HTTPS proxy, health monitoring, and tested backups.
3. Run deployment checks in the release environment:

   ```powershell
   python manage.py check --deploy --settings=config.settings.production
   python manage.py makemigrations --check --dry-run --settings=config.settings.production
   ```

4. Back up the database before migrations. Run `python manage.py migrate --noinput` once as a release job, not concurrently in every web worker.
5. Run `python manage.py collectstatic --noinput` and verify the configured static storage can serve the manifest and assets.
6. Start the WSGI application with a process manager and a production server such as Gunicorn. Run behind the trusted HTTPS proxy with bounded worker counts, request timeouts, and graceful shutdown.
7. Verify login, a permitted read-only page, database connectivity, static assets, email delivery, and monitoring before directing traffic to the release.

## Operations

Use structured application logs and forward them to a protected central logging system. Audit events and application logs may contain sensitive business identifiers; apply access controls and retention limits. Alert on 5xx rates, database connection failures, disk usage, backup failures, and authentication lockouts. Establish a process for dependency and security updates.

Production readiness also requires a deployment-specific rollback plan and a tested database restore. Operational reports are not a substitute for reviewed financial statements or a double-entry ledger.