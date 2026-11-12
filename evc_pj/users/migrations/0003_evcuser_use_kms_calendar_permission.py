from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_NAME = '勤怠カレンダー利用者'
PERM_CODENAME = 'use_kms_calendar'
# 移行時に権限を付与する対象（従来メニューで判定していたメールドメイン）
LEGACY_DOMAIN = '@system-bridge.jp'


def grant_to_legacy_users(apps, schema_editor):
    """権限・グループを作成し、従来 system-bridge.jp ドメインだったユーザーをグループに入れる"""
    alias = schema_editor.connection.alias
    if alias != 'default':
        return

    # 権限行は post_migrate で作られるため、このマイグレーション内で先に作成する
    app_config = apps.get_app_config('users')
    app_config.models_module = True
    try:
        create_permissions(app_config, apps=apps, verbosity=0, using=alias)
    finally:
        app_config.models_module = None

    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    EvcUser = apps.get_model('users', 'EvcUser')

    perm = Permission.objects.using(alias).get(
        content_type__app_label='users', codename=PERM_CODENAME)
    group, _ = Group.objects.using(alias).get_or_create(name=GROUP_NAME)
    group.permissions.add(perm)

    for user in EvcUser.objects.using(alias).filter(user_id__iendswith=LEGACY_DOMAIN):
        user.groups.add(group)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('users', '0002_mtfolder_use_count'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='evcuser',
            options={
                'permissions': [('use_kms_calendar', '勤怠カレンダー・外勤報告書を利用できる')],
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
        ),
        migrations.RunPython(grant_to_legacy_users, migrations.RunPython.noop),
    ]
