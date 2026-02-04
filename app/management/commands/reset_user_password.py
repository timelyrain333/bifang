"""
管理命令：重置用户密码
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction


class Command(BaseCommand):
    help = '重置用户密码'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='要重置密码的用户名'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='新密码（如果不提供，将提示输入）'
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='如果用户不存在，则创建新用户'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='创建用户时使用的邮箱地址'
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            help='创建超级用户'
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options.get('password')
        create = options.get('create', False)
        email = options.get('email', '')
        superuser = options.get('superuser', False)

        try:
            user = User.objects.get(username=username)
            self.stdout.write(f'找到用户: {username} (ID: {user.id})')
            self.stdout.write(f'  邮箱: {user.email}')
            self.stdout.write(f'  是否激活: {user.is_active}')
            self.stdout.write(f'  是否超级用户: {user.is_superuser}')
            
            # 如果没有提供密码，提示输入
            if not password:
                import getpass
                password = getpass.getpass('请输入新密码: ')
                password_confirm = getpass.getpass('请确认新密码: ')
                
                if password != password_confirm:
                    raise CommandError('两次输入的密码不一致')
                
                if not password:
                    raise CommandError('密码不能为空')
            
            # 重置密码
            user.set_password(password)
            user.save()
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ 密码已成功重置'))
            
        except User.DoesNotExist:
            if create:
                self.stdout.write(f'用户 {username} 不存在，正在创建...')
                
                # 如果没有提供密码，提示输入
                if not password:
                    import getpass
                    password = getpass.getpass('请输入密码: ')
                    password_confirm = getpass.getpass('请确认密码: ')
                    
                    if password != password_confirm:
                        raise CommandError('两次输入的密码不一致')
                    
                    if not password:
                        raise CommandError('密码不能为空')
                
                # 创建用户
                user = User.objects.create_user(
                    username=username,
                    email=email or f'{username}@example.com',
                    password=password
                )
                
                if superuser:
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f'\n✓ 超级用户 {username} 已创建'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'\n✓ 用户 {username} 已创建'))
            else:
                raise CommandError(f'用户 {username} 不存在。使用 --create 参数可以创建新用户。')
        
        self.stdout.write(f'\n现在可以使用以下信息登录:')
        self.stdout.write(f'  用户名: {username}')
        self.stdout.write(f'  密码: {"*" * len(password)}')


