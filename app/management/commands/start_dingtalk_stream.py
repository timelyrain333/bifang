"""
启动钉钉Stream推送服务的Django管理命令
"""
import os
import ssl
import certifi

# 在导入其他模块之前设置SSL证书环境变量
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['CURL_CA_BUNDLE'] = certifi.where()

from django.core.management.base import BaseCommand
from django.db.models import Q
from app.models import AliyunConfig
from app.services.dingtalk_stream_service import start_service, stop_all_services
import logging
import signal
import sys

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '启动钉钉Stream推送服务，接收事件推送'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-id',
            type=int,
            help='指定配置ID（可选，不指定则启动所有启用的配置）',
        )

    def handle(self, *args, **options):
        config_id = options.get('config_id')
        
        # 注册信号处理，优雅退出
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\n正在停止Stream推送服务...'))
            stop_all_services()
            self.stdout.write(self.style.SUCCESS('Stream推送服务已停止'))
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            if config_id:
                # 启动指定配置
                config = AliyunConfig.objects.get(id=config_id)
                if not config.dingtalk_enabled:
                    self.stdout.write(self.style.ERROR(f'配置 {config_id} 未启用钉钉'))
                    return
                if not config.dingtalk_use_stream_push:
                    self.stdout.write(self.style.ERROR(f'配置 {config_id} 未启用Stream推送'))
                    return
                if not config.dingtalk_client_id or not config.dingtalk_client_secret:
                    self.stdout.write(self.style.ERROR(f'配置 {config_id} 缺少Client ID或Client Secret'))
                    return
                
                self.stdout.write(self.style.SUCCESS(f'正在启动配置 {config_id} 的Stream推送服务...'))
                service = start_service(config_id)
                self.stdout.write(self.style.SUCCESS(f'配置 {config_id} 的Stream推送服务已启动'))
            else:
                # 启动所有启用的配置
                configs = AliyunConfig.objects.filter(
                    dingtalk_enabled=True,
                    dingtalk_use_stream_push=True
                ).exclude(
                    dingtalk_client_id=''
                ).exclude(
                    dingtalk_client_secret=''
                )
                
                if not configs.exists():
                    self.stdout.write(self.style.WARNING('未找到启用的钉钉Stream推送配置'))
                    return
                
                self.stdout.write(self.style.SUCCESS(f'找到 {configs.count()} 个启用的配置，正在启动...'))
                for config in configs:
                    try:
                        self.stdout.write(f'启动配置 {config.id} ({config.name})...')
                        service = start_service(config.id)
                        self.stdout.write(self.style.SUCCESS(f'配置 {config.id} 已启动'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'配置 {config.id} 启动失败: {e}'))
            
            # 保持运行
            self.stdout.write(self.style.SUCCESS('\nStream推送服务正在运行，按 Ctrl+C 停止'))
            import time
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            signal_handler(None, None)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'启动失败: {e}'))
            logger.error(f'启动钉钉Stream推送服务失败: {e}', exc_info=True)
            stop_all_services()
            sys.exit(1)





