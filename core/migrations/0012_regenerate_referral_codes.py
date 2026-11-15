import secrets

from django.db import migrations

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def new_code():
    return ''.join(secrets.choice(ALPHABET) for _ in range(8))


def regenerate_codes(apps, schema_editor):
    UserProfile = apps.get_model('core', 'UserProfile')
    used = set(
        UserProfile.objects.exclude(referral_code__isnull=True)
        .values_list('referral_code', flat=True)
    )
    for profile in UserProfile.objects.select_related('user'):
        code = profile.referral_code
        if code and code not in (profile.user.username, profile.phone_number):
            continue
        fresh = new_code()
        while fresh in used:
            fresh = new_code()
        used.add(fresh)
        UserProfile.objects.filter(pk=profile.pk).update(referral_code=fresh)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_passwordresetrequest'),
    ]

    operations = [
        migrations.RunPython(regenerate_codes, migrations.RunPython.noop),
    ]