from django.apps import AppConfig
import sys

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # রেন্ডার বা সার্ভার চালুর সময় অটোমেটিক মাইগ্রেশন রান করার লজিক
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv or 'wsgi' in sys.argv:
            try:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
            except Exception as e:
                print(f"Auto migration error: {e}")