# Agile Hub

Agile Hub is a Django application for managing hub operations, products and stock, sales, agent commissions, payroll, beneficiary businesses, cash flow, audit events, and operational reports.

## Requirements

- Python 3.11 or newer
- PostgreSQL 14 or newer for deployment
- The packages in `requirements.txt`

SQLite is used by the automated test settings only. Do not use SQLite for production.

## Local setup

1. Create and activate a virtual environment.
2. Install runtime and development dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-dev.txt
   ```

3. Copy `.env.example` to `.env` and set a unique `SECRET_KEY`, database connection values, and allowed hosts. Keep `.env` private; it is ignored by Git.
4. Create the configured PostgreSQL database and database user.
5. Apply migrations and create an administrator:

   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py setup_roles
   ```

6. Start the development server:

   ```powershell
   python manage.py runserver
   ```

The local development settings are `config.settings.development`. The application reads environment values from the process environment and `.env`.

## Demo data

To add a small set of realistic sample records directly to the database used by your regular local app, start the development server as usual, then run this in another terminal:

```bash
python manage.py seed_demo_data --sales 30 --batch preview
```

This uses the configured development database (normally the PostgreSQL database in `.env`), so the records appear in the existing local app without switching servers or accounts. The command creates the sample hub, products, inventory, agent, completed sales, three worker profiles with current-month pending salary records, and three beneficiary profiles with active businesses. Sales and payroll records use the normal business models/workflows where applicable. It is idempotent: rerunning the same command will not duplicate sales, workers, beneficiaries, businesses or salary periods. Use a different `--batch` value to add a separate set of sales; workers, beneficiaries, businesses and current-month payroll remain one stable sample set. Sample seeding is blocked under production settings.

The example business setup is a hub-based social enterprise, cooperative, distributor or community-development program: each hub can track local inventory and product sales, sales-agent commissions, staff and payroll, beneficiary businesses, cash flow and operational reporting. The app provides role-scoped records and approval workflows; it is not a general-purpose accounting ledger or a full HR suite.

To seed the separate, disposable SQLite demo database instead, explicitly select its settings:

```powershell
python manage.py migrate --settings=config.settings.demo
python manage.py seed_demo_data --sales 1000 --batch preview --settings=config.settings.demo
python manage.py createsuperuser --settings=config.settings.demo
python manage.py runserver 127.0.0.1:8001 --settings=config.settings.demo
```

This stores demo records in the ignored `demo.sqlite3` file, completely separate from PostgreSQL and `.env` database credentials. The reserved sample sales agent has no usable password; sign in with a demo admin created for that database. Increase `--sales` (up to 10000) to exercise larger datasets. Never seed real customer or production data.

To reset the isolated demo environment, stop the local server and remove only `demo.sqlite3`; run the demo migrations and seed command again. The sample is for functional exploration, not a production load-test—use a dedicated staging setup and a measured load-testing plan for capacity decisions.

Optional public landing-page contact details can be configured with `PUBLIC_CONTACT_EMAIL`, `PUBLIC_CONTACT_PHONE`, and `PUBLIC_CONTACT_LOCATION`.

## Tests and checks

```powershell
python -m pytest
python manage.py check --settings=config.settings.testing
python manage.py makemigrations --check --dry-run --settings=config.settings.testing
```

## Core business rules

- Currency defaults to KES and can be changed with `CURRENCY_CODE`.
- Commission defaults to 20%; active, effective-dated `CommissionSetting` records take precedence. Commissions are accrued only on completed eligible agent sales and must be approved before payment.
- Sale completion and stock movements run in database transactions. A hub cannot sell stock it does not have.
- Salary records must be approved before they can be paid.
- Sales, stock movements, commission transitions, salary transitions, and administrative actions are recorded in the audit trail.
- Reporting summarizes the operational records currently stored by Agile Hub. It is not a double-entry general ledger and must not be treated as audited financial statements.

## Production deployment

Use `config.settings.production`, PostgreSQL, a trusted HTTPS reverse proxy, and a process manager such as Gunicorn behind the proxy. Configure secrets in the deployment platform, not in source control. Follow [the deployment guide](docs/DEPLOYMENT.md), [backup guidance](docs/BACKUPS.md), [API notes](docs/API.md), and [role permissions](docs/PERMISSIONS.md).

Before serving real users, provision and test production backups, outbound email, TLS, static files, monitoring, and recovery procedures. Run `manage.py check --deploy --settings=config.settings.production` in the actual deployment environment.