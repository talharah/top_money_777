import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# ⬇️ ইউজারনেম ও নতুন পাসওয়ার্ড ⬇️
USERNAME = 'admin'
EMAIL = 'admin@fahad.com'
PASSWORD = 'Password123'

def make_admin():
    user, created = User.objects.get_or_create(
        username=USERNAME,
        defaults={'email': EMAIL, 'is_staff': True, 'is_superuser': True}
    )
    # পাসওয়ার্ড নিশ্চিতভাবে আপডেট ও এনক্রিপ্ট করার জন্য:
    user.set_password(PASSWORD)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"Superuser '{USERNAME}' updated/created successfully with new password!")

if __name__ == '__main__':
    make_admin()