import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# ⬇️ এখানে আপনার পছন্দমতো Username, Email এবং Password বসান ⬇️
USERNAME = 'admin'
EMAIL = 'admin@fahad.com'
PASSWORD = 'Password123'  # এই পাসওয়ার্ডটি মনে রাখবেন, লগইন করতে লাগবে

def make_admin():
    if not User.objects.filter(username=USERNAME).exists():
        User.objects.create_superuser(username=USERNAME, email=EMAIL, password=PASSWORD)
        print(f"Superuser '{USERNAME}' created successfully!")
    else:
        print(f"Superuser '{USERNAME}' already exists.")

if __name__ == '__main__':
    make_admin()