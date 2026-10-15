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


    # Auto Migration
try:
    call_command('migrate')
    print("Database Migration Successful!")
except Exception as e:
    print(f"Migration error: {e}")

# Auto Admin Superuser Creation
try:
    import create_admin
    create_admin.make_admin()
except Exception as e:
    print(f"Admin creation error: {e}")