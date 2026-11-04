# Smart Inventory

A Django application for managing product stock, recording sales, and reviewing business activity.

## Features

- Inventory catalog with name/SKU search, category and stock-status filters, and pagination.
- Product-level reorder thresholds and a dashboard that highlights low/out-of-stock items.
- Dashboard KPIs for monthly sales, inventory value, and recent transactions.
- Atomic sale processing with server-side price snapshots and concurrency-safe stock deductions.
- Product changes and sale creation are guarded by Django model permissions.
- Bootstrap-based responsive interface, accessible navigation, and printable sale receipts.

## Local setup

1. Use Python 3.10+ and create/activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, generate a unique Django `SECRET_KEY`, and set `DEBUG=True` only for local development.
4. Run `python manage.py migrate` and `python manage.py createsuperuser`.
5. Run `python manage.py runserver` and sign in at `/accounts/login/`.
6. Assign product and sale permissions to users in Django admin. New accounts do not receive inventory permissions automatically.

## Configuration and deployment

`SECRET_KEY` is required from the environment and must not be committed. Set `DEBUG=False` and configure `ALLOWED_HOSTS` for deployment. HTTPS, secure session/CSRF cookies, HSTS, content-type protection, same-site cookies, and frame denial are enabled by default when debug is off. Only enable HTTPS/HSTS when the application is served behind correctly configured HTTPS.

The default database is SQLite. Optional database settings are listed in `.env.example`; for PostgreSQL, install the appropriate psycopg driver and provide the database credentials through environment variables. Run `python manage.py check --deploy` before releasing.

## Tests

Run `python manage.py test`. Tests cover sale stock deduction and price snapshots, overselling protection, inventory search, permissions, and positive pricing.
