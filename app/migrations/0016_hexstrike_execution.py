# Generated manually for HexStrike execution records

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0015_vulnerability_source_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='HexStrikeExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target', models.CharField(db_index=True, help_text='IP、域名或主机名', max_length=255, verbose_name='评估目标')),
                ('analysis_type', models.CharField(default='comprehensive', max_length=50, verbose_name='分析类型')),
                ('tool_name', models.CharField(blank=True, help_text='如果是指定工具执行，记录工具名', max_length=100, verbose_name='工具名称')),
                ('status', models.CharField(choices=[('running', '执行中'), ('success', '成功'), ('failed', '失败')], default='running', max_length=20, verbose_name='状态')),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('result', models.JSONField(default=dict, help_text='HexStrike 返回的完整结果数据', verbose_name='执行结果')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('execution_time', models.FloatField(blank=True, help_text='执行耗时（秒）', null=True, verbose_name='执行耗时（秒）')),
                ('created_by', models.CharField(blank=True, help_text='执行此评估的用户', max_length=50, verbose_name='执行人')),
            ],
            options={
                'verbose_name': 'HexStrike 执行记录',
                'verbose_name_plural': 'HexStrike 执行记录',
                'db_table': 'hexstrike_executions',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='hexstrikeexecution',
            index=models.Index(fields=['target', 'started_at'], name='hexstrike_e_target_4a8b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='hexstrikeexecution',
            index=models.Index(fields=['status', 'started_at'], name='hexstrike_e_status_8c9d3e_idx'),
        ),
    ]
