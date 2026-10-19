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

Open <http://127.0.0.1:8001/>. The default development database is SQLite and is stored in this folder. For PostgreSQL, use the local Docker deployment below.

### Run from VS Code

1. Open the repository root folder in VS Code.
2. Select a Python interpreter that has the application requirements installed. If needed, open **Terminal → New Terminal** and run:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r Application/requirements.txt
   ```

   On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.
3. Open **Run and Debug** and choose **Run Asset Lifecycle Django app**, then press **F5**.
4. VS Code applies migrations and starts the development server at <http://127.0.0.1:8001/>.
5. If you have not created a login yet, stop the server and run `python Application/manage.py createsuperuser` in the terminal, then start the app again and sign in.

The VS Code launch profile uses the local SQLite database at `Application/db.sqlite3`. It is for development with synthetic data only.

The case-study CSV is located at [`../ICT Business analysis/data/assets.csv`](<../ICT Business analysis/data/assets.csv>). Importing any data requires explicit authorization confirmation; use the synthetic sample only for development:

```bash
python Application/manage.py import_assets \
  --input "ICT Business analysis/data/assets.csv" \
  --confirm-authorized-source
```

## Local Docker deployment

This Compose setup runs PostgreSQL and the Django application locally. The web port is bound to `127.0.0.1:8001`; this is a development environment, not a public or production deployment.

From the repository root:

```bash
cp .env.example .env
# Replace the Django and PostgreSQL placeholder values in .env.
docker compose up --build
```

Open <http://127.0.0.1:8001/>. The web container waits for PostgreSQL, applies the checked-in migrations, and then starts Gunicorn. To create an administrator, open a second terminal and run:

```bash
docker compose exec web python manage.py createsuperuser
```

Stop the services with Ctrl+C or `docker compose down`. The named PostgreSQL volume remains so local data survives a restart; `docker compose down --volumes` removes that volume and its database contents.

The Compose configuration disables secure cookies only for its loopback-bound local HTTP setup. For any real deployment, use HTTPS, secure cookies, managed secrets, a controlled migration/release process, backups, monitoring, and a reviewed security/privacy design. Do not expose this local Compose configuration to a network or load real organizational data.

## ETL and reporting

The first asset ETL source is the synthetic CSV in the portfolio folder. `import_assets` performs these stages:

1. **Extract:** read the UTF-8 CSV, calculate a SHA-256 source fingerprint, and check the declared columns and row shape.
2. **Validate and transform:** validate lifecycle values, dates, and required attributes; trim text fields and convert dates/boolean fields to application types. The import is all-or-nothing when validation fails.
3. **Profile:** calculate record-level quality findings for missing custodian/return/disposal evidence, stale source dates (over 90 days), warranty dates before purchase, and duplicate serial references.
4. **Load:** transactionally upsert on `asset_id`, write lifecycle events for created/changed records, and record created/updated/unchanged/rejected counts on the import run. Replaying an unchanged file is idempotent. A missing source row does not delete or retire an existing asset.

Each run records its source filename and hash, start/completion status, row counts, quality summary, and a bounded error summary. Identity values and bearer tokens are not included in dashboard reporting. The dashboard combines a site/status-filtered operational snapshot with current data-quality exception counts, the most recent asset import runs, and SCIM integration-run summaries. Data-quality counts are investigation prompts, not proof of a business-policy breach.

The signed-in application also has a live in-app notification page. It flags overdue/soon-due returns, expired/soon-expiring active-asset warranties, and selected missing asset references or disposal evidence. Notifications are computed from current records and disappear when the underlying condition is resolved; they do not send email or push messages.

### Permission setup for the workflow modules

Create Django Groups and assign these permissions in Django Admin; grant only the capabilities required for each job:

| Role | Permissions |
|---|---|
| Asset operator | `inventory.view_asset`; add/edit and `inventory.transition_asset` only where required |
| Maintenance coordinator | `inventory.view_maintenanceworkorder`, `inventory.add_maintenanceworkorder`, `inventory.change_maintenanceworkorder` |
| Procurement requester | `inventory.view_procurementrequest`, `inventory.add_procurementrequest` |
| Procurement approver | `inventory.view_procurementrequest`, `inventory.view_all_procurementrequests`, `inventory.approve_procurementrequest` |
| Procurement buyer/receiver | `inventory.view_procurementrequest`, `inventory.view_all_procurementrequests`, `inventory.manage_procurementrequest` |
| Disposal requester | `inventory.view_disposalcase`, `inventory.add_disposalcase`, plus asset view/transition access as required |
| Disposal reviewer | `inventory.view_disposalcase`, `inventory.approve_disposalcase` |
| Disposal operator | `inventory.view_disposalcase`, `inventory.complete_disposalcase` |

The requester manages their own procurement draft. Managing another user's request requires both `inventory.change_procurementrequest` and `inventory.view_all_procurementrequests`; approval and buyer/receiver actions likewise require their action permission plus view-all access. Approval policies and Groups shown here are implementation controls, not company-specific delegated financial authorities. Test permission combinations using non-superuser accounts before deployment.

### Maintenance work orders

Users with the relevant Django permissions can open maintenance work orders from an asset record, track priority, vendor, target date, and cost, and move orders through permitted statuses. Status transitions are recorded in an audit history. Work orders do not automatically change the asset's lifecycle status; that remains a separately permissioned asset transition. Disposed and lost/stolen assets cannot have new maintenance orders opened.

### Procurement and receiving

The procurement prototype covers draft requests, supplier quote comparison, quote selection, independent approval, purchase-order reference capture, expected delivery/tracking details, in-transit/delayed updates, partial/final receiving, unique receipt references, and registration of received items as assets. The requester cannot approve their own request. Separate Django permissions control request creation/change, independent approval, and order/receipt management. The prototype uses one independent approval for all amounts; it does not implement spend thresholds, budget checks, contract validation, or external supplier APIs. Configure real approval authority and delegated limits before organizational use. Barcode registration supports a keyboard/USB scanner and the browser's native camera `BarcodeDetector` when available; scanned values are checked against asset ID and serial references. No barcode is assumed unique, and no image or camera stream is uploaded or stored. Supplier quotes, purchase orders, tracking and receiving are captured as identifiers/references and audit data; uploaded document storage is not implemented.

### Disposal approvals

Assets must first be moved through the lifecycle workflow to **Ready for Disposal**. A requester records the disposal reason and method; if sanitisation is required, passed sanitisation and its evidence reference are mandatory before submission. A different authorized user approves or rejects the request. A separately permissioned operator then records disposal evidence, which completes the approved case and the audited asset lifecycle transition to **Disposed**. These role permissions are a prototype separation-of-duties control, not a configured company approval matrix. External erasure/disposition vendors and their evidence APIs are not connected.

Pipeline execution is manual using the documented `import_assets` command; no schedule or freshness SLA has been configured. The SCIM connector is read-only and only generates return-review work items. Additional systems require provider-specific data contracts, authorization, and sandbox validation before their records can be mapped into these pipelines.

## Integrations

The authenticated app's **Integrations** page is a capability catalogue, not a
one-click marketplace. It distinguishes working connectors from planned adapters
so a client can match their workflow without implying unsupported APIs are live.
Provider adapters implement the shared identity status contract in
`inventory/integrations/contracts.py` and are selected through the registry in
`inventory/integrations/adapters.py`. The SCIM adapter is the only registered
identity provider today; unregistered vendors fail explicitly instead of returning
sample or success-shaped data.
Current availability:

| Client platform/feed | Current status |
|---|---|
| Local CSV asset feed | Implemented ETL import with audit and quality reports |
| Generic SCIM 2.0 | Implemented read-only users status sync, subject to provider contract compatibility |
| Microsoft Entra ID / Graph, Okta, Active Directory / LDAP | Provider adapter required; no direct vendor API integration is claimed |
| ServiceNow, Jira Service Management | Adapter and workflow/status mapping required |
| Microsoft Intune, Jamf Pro | Device inventory adapter required |
| Blancco | Blocked pending official API documentation, vendor sandbox, and evidence mapping contract |
| SFTP and generic REST/webhooks | Transport adapters and source/destination contracts required |

Each provider adapter should translate provider-specific authentication, pagination,
rate limits, identifiers, and payloads into a versioned internal contract. The
workflow layer then validates, deduplicates, audits, and routes events to human
review; external writes stay disabled until separately approved and tested.
This boundary is intended to fit existing client workflows without making the
core inventory application dependent on one vendor.

### SCIM 2.0 deactivation review

The initial SCIM connector is read-only. It requests only `id` and `active` from the provider's `/Users` resource, requires HTTPS certificate verification, follows SCIM pagination, and does not send account changes. Map SCIM subject IDs to local custodian references in the Django admin before running a sync. Inactive mapped users create idempotent return-review items for their currently assigned assets; the sync does not change identity status or asset lifecycle status. Unmapped inactive identities are counted but their identifiers are not recorded in the run summary.

Set the provider's HTTPS SCIM service-provider root and an approved, least-privilege bearer token in the environment, then explicitly confirm authorization when running:

```bash
export SCIM_BASE_URL="https://identity-provider.example/scim/v2"
export SCIM_BEARER_TOKEN="<approved-read-only-token>"
python Application/manage.py sync_scim_deactivations \
  --confirm-read-only-authorized
```

Do not put credentials in source control, command-line arguments, URLs, or logs. Use only a provider sandbox until access, privacy, retention, and security approvals are complete.

### Other providers

No Blancco or other third-party API calls are implemented. Keep those integrations disabled until official API documentation, approved credentials, and a sandbox are available. Do not configure real identity or vendor integrations using this development project.
