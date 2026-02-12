# Generated migration for adding Feishu long connection fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_add_feishu_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='aliyunconfig',
            name='feishu_app_id',
            field=models.CharField(blank=True, help_text='飞书机器人应用的App ID（用于长连接）', max_length=100, verbose_name='飞书App ID'),
        ),
        migrations.AddField(
            model_name='aliyunconfig',
            name='feishu_app_secret',
            field=models.CharField(blank=True, help_text='飞书机器人应用的App Secret（用于长连接）', max_length=200, verbose_name='飞书App Secret'),
        ),
        migrations.AddField(
            model_name='aliyunconfig',
            name='feishu_use_long_connection',
            field=models.BooleanField(default=False, help_text='使用长连接方式接收事件，无需公网地址', verbose_name='使用长连接'),
        ),
    ]







