import os
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Server start hobar shomoy auto-migrate hobe
try:
    call_command('migrate')
    print("Database Migration Successful!")
except Exception as e:
    print(f"Migration error: {e}")