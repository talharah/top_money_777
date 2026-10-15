import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# আপনার পছন্দের Username, Email এবং Password দিন
USERNAME = 'admin'
EMAIL = 'admin@example.com'
PASSWORD = 'YourStrongPassword123'  # আপনার পছন্দমতো পাসওয়ার্ড সেট করুন

def make_admin():
    if not User.objects.filter(username=USERNAME).exists():
        User.objects.create_superuser(username=USERNAME, email=EMAIL, password=PASSWORD)
        print(f"Superuser '{USERNAME}' created successfully!")
    else:
        print(f"Superuser '{USERNAME}' already exists.")

if __name__ == '__main__':
    make_admin()