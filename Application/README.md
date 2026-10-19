# Asset Lifecycle Management Application

This folder contains the separate Django application workstream. Unlike the read-only portfolio dashboard in [`../ICT Business analysis/dashboard/`](<../ICT Business analysis/dashboard/>), this application is intended to support authenticated asset-management workflows.

> **Development status:** This application is under development. It is not a production deployment and has not yet been validated for production security, reliability, privacy, or operational use. Use synthetic data only.

## Local setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r Application/requirements.txt
export DJANGO_DEBUG=1
python Application/manage.py check
python Application/manage.py migrate
python Application/manage.py createsuperuser
python Application/manage.py runserver 127.0.0.1:8001
```

Open <http://127.0.0.1:8001/>. The default development database is SQLite and is stored in this folder. PostgreSQL configuration and container deployment instructions will be documented here when they are implemented and verified.

The case-study CSV is located at [`../ICT Business analysis/data/assets.csv`](<../ICT Business analysis/data/assets.csv>). Importing any data requires explicit authorization confirmation; use the synthetic sample only for development:

```bash
python Application/manage.py import_assets \
  --input "ICT Business analysis/data/assets.csv" \
  --confirm-authorized-source
```

## Integrations

Identity and third-party connectors must remain read-only and disabled until the provider's official API documentation, approved credentials, and a sandbox are available. Do not configure real identity or vendor integrations using this development project.
