# Generated migration for adding SecurityAlert model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0012_add_dingtalk_client_credentials'),
    ]

    operations = [
        migrations.CreateModel(
            name='SecurityAlert',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_id', models.CharField(db_index=True, help_text='阿里云返回的告警唯一标识', max_length=100, unique=True, verbose_name='告警ID')),
                ('unique_info', models.CharField(blank=True, db_index=True, help_text='告警的唯一key，用于去重', max_length=200, verbose_name='唯一标识')),
                ('name', models.CharField(max_length=200, verbose_name='告警名称')),
                ('level', models.CharField(blank=True, help_text='serious/suspicious/remind', max_length=50, verbose_name='告警级别')),
                ('status', models.CharField(blank=True, help_text='0:全部 1:待处理 2:已忽略 4:已确认 8:已标记误报等', max_length=50, verbose_name='处理状态')),
                ('dealt', models.BooleanField(default=False, help_text='Y:已处理 N:待处理', verbose_name='是否已处理')),
                ('alert_time', models.DateTimeField(db_index=True, verbose_name='告警时间')),
                ('event_type', models.CharField(blank=True, help_text='如：WEBSHELL、异常登录等', max_length=200, verbose_name='告警类型')),
                ('instance_id', models.CharField(blank=True, max_length=200, verbose_name='实例ID')),
                ('instance_name', models.CharField(blank=True, max_length=200, verbose_name='实例名称')),
                ('ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')),
                ('uuid', models.CharField(blank=True, db_index=True, max_length=200, verbose_name='资产UUID')),
                ('data', models.JSONField(default=dict, help_text='完整的告警信息', verbose_name='告警详细数据')),
                ('pushed_to_dingtalk', models.BooleanField(default=False, verbose_name='已推送到钉钉')),
                ('pushed_to_feishu', models.BooleanField(default=False, verbose_name='已推送到飞书')),
                ('pushed_at', models.DateTimeField(blank=True, null=True, verbose_name='推送时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '安全告警',
                'verbose_name_plural': '安全告警',
                'db_table': 'security_alerts',
                'ordering': ['-alert_time', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='securityalert',
            index=models.Index(fields=['alert_time'], name='security_al_alert_t_38b5d2_idx'),
        ),
        migrations.AddIndex(
            model_name='securityalert',
            index=models.Index(fields=['level', 'dealt'], name='security_al_level_d32b4a_idx'),
        ),
        migrations.AddIndex(
            model_name='securityalert',
            index=models.Index(fields=['pushed_to_dingtalk', 'pushed_to_feishu'], name='security_al_pushed__a7f8b2_idx'),
        ),
    ]
