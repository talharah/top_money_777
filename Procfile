release: python manage.py migrate --noinput && python create_admin.py && python manage.py collectstatic --noinput
web: gunicorn config.wsgi:application