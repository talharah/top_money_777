# TOP MONEY 777

A Django-based earning and task platform with a responsive dashboard and an admin-managed workflow.

## Features

- User registration, login, password management, welcome bonus, and account profile.
- Deposit requests with unique transaction IDs; balance is added only once after admin approval.
- Withdrawals reserve the requested balance immediately. Rejected requests refund it; approved requests show the fee and net payout.
- VIP purchases are recorded with the purchased plan's terms. Daily income can be claimed once per 24 hours, up to the plan's validity.
- Tasks are managed in the admin. Users submit proof; an admin approves or rejects each submission before any reward is credited.
- Referral commissions: 10% for direct referrals and 3% for the second level, paid only when a referred user's deposit is approved.
- Support tickets are saved and manageable in the admin.

## Local setup

From the project directory in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. The admin panel is at `http://127.0.0.1:8000/admin/`.
In the admin panel, configure the website's support links and upload VIP plan images; local development serves uploaded media from `media/`.

## Production configuration

Do not deploy with the local defaults. Set these environment variables in the hosting platform:

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY` to a long, unique secret
- `DJANGO_ALLOWED_HOSTS` to a comma-separated list of the site's hostnames
- `DJANGO_EMAIL_HOST`, and optionally `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USERNAME`, `DJANGO_EMAIL_PASSWORD`, `DJANGO_EMAIL_USE_TLS`, and `DJANGO_DEFAULT_FROM_EMAIL`
- `DJANGO_CSRF_TRUSTED_ORIGINS` to comma-separated `https://` origins when needed
- Optionally set `DJANGO_SECURE_HSTS_SECONDS`; enable `DJANGO_HSTS_INCLUDE_SUBDOMAINS` or `DJANGO_HSTS_PRELOAD` only when every affected hostname is HTTPS-ready
- `DATABASE_URL` for the production database

Production mode enables HTTPS redirects, secure session/CSRF cookies, and root-host HSTS. Ensure the site is served over HTTPS before deploying; subdomain HSTS and browser preloading are opt-in because they can affect every hostname under the domain.

Configure persistent media storage (or a web-server media alias) in production so VIP plan images remain available after deploys. The built-in `/media/` route is enabled only in development.

On Procfile-based hosts, the `release` process applies database migrations and collects static files before the new web release starts.
