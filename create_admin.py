import os


def main():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

    if not username:
        if password or email:
            raise RuntimeError('Set DJANGO_SUPERUSER_USERNAME with the other admin variables.')
        return

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    import django

    django.setup()

    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        if not password:
            raise RuntimeError(
                'DJANGO_SUPERUSER_PASSWORD is required to create a new admin user.'
            )
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        print(f'Created admin user: {username}')
        return

    changed_fields = []
    for field in ('is_active', 'is_staff', 'is_superuser'):
        if not getattr(user, field):
            setattr(user, field, True)
            changed_fields.append(field)
    if changed_fields:
        user.save(update_fields=changed_fields)
    print(f'Admin permissions ensured for: {username}')


if __name__ == '__main__':
    main()
