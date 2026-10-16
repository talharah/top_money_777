from django.apps import AppConfig
import sys

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        if not any(cmd in sys.argv for cmd in ['makemigrations', 'shell', 'test']):
            try:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
            except Exception as e:
                print(f"Migration execution info: {e}")