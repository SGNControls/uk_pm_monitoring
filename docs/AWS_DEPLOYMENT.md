# AWS deployment guide for `zoho-cleanup-working`

This branch is the cleanup and productionization line for `uk_pm_monitoring`.

## Recommended stack
- EC2 Ubuntu instance
- PostgreSQL on Amazon RDS
- Nginx reverse proxy
- Gunicorn application server
- SSL on the website/proxy layer

## Suggested runtime flow
1. Clone branch `zoho-cleanup-working`
2. Create Python virtual environment
3. Install `requirements.txt`
4. Copy `.env.aws.example` to `.env` and fill values
5. Run `schema.sql`
6. Run `migrations/002_add_extended_columns.sql`
7. Start with Gunicorn bound to `127.0.0.1:8000`
8. Put Nginx in front of the app

## First bootstrap commands
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx postgresql-client git

git clone -b zoho-cleanup-working https://github.com/SGNControls/uk_pm_monitoring.git
cd uk_pm_monitoring
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.aws.example .env
```

## Database setup
Run base schema first, then migration:
```bash
psql "$DATABASE_URL" -f schema.sql
psql "$DATABASE_URL" -f migrations/002_add_extended_columns.sql
```

If using split DB variables instead of `DATABASE_URL`, connect with:
```bash
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f schema.sql
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f migrations/002_add_extended_columns.sql
```

## Gunicorn start command
```bash
venv/bin/gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:8000 app:app
```

## Notes
- This branch still needs app cleanup before final production use.
- Current priorities are MQTT client mapping, auth cleanup, and startup cleanup.
- Keep `main` untouched until branch validation is complete.
