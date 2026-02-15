"""
修复所有有无效组件名称的漏洞
"""
from django.core.management.base import BaseCommand
from app.models import Vulnerability
from app.utils.qianwen import _is_invalid_component_name, _extract_component_from_text
from django.db import transaction
import re


class Command(BaseCommand):
    help = '修复所有有无效组件名称的漏洞'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示将要修复的漏洞，不实际修改',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('这是试运行模式，不会实际修改数据'))
        
        # 查找所有有无效组件名称的漏洞
        invalid_vulns = []
        for vuln in Vulnerability.objects.all():
            if isinstance(vuln.content, dict):
                component = vuln.content.get('affected_component', '').strip()
                if component and _is_invalid_component_name(component):
                    invalid_vulns.append(vuln)
        
        self.stdout.write(f'找到 {len(invalid_vulns)} 个有无效组件名称的漏洞')
        
        if not invalid_vulns:
            self.stdout.write(self.style.SUCCESS('没有需要修复的漏洞'))
            return
        
        fixed_count = 0
        failed_count = 0
        
        with transaction.atomic():
            for vuln in invalid_vulns:
                old_component = vuln.content.get('affected_component', '').strip()
                
                # 尝试从各种来源提取组件名称
                new_component = None
                
                # 1. 从标题中提取
                if vuln.title:
                    new_component = _extract_component_from_text(vuln.title)
                
                # 2. 从描述中提取
                if not new_component and vuln.description:
                    new_component = _extract_component_from_text(vuln.description[:500])
                
                # 3. 从raw_content中提取Subject
                if not new_component and vuln.raw_content:
                    subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', vuln.raw_content, re.IGNORECASE | re.MULTILINE)
                    if subject_match:
                        subject = subject_match.group(1).strip()
                        new_component = _extract_component_from_text(subject)
                
                # 4. 从basic_description中提取
                if not new_component and vuln.content.get('basic_description'):
                    new_component = _extract_component_from_text(vuln.content.get('basic_description', '')[:500])
                
                # 5. 从vulnerability_description中提取
                if not new_component and vuln.content.get('vulnerability_description'):
                    new_component = _extract_component_from_text(vuln.content.get('vulnerability_description', '')[:500])
                
                # 6. 从affected_versions中提取（如果包含组件名称）
                if not new_component and vuln.content.get('affected_versions'):
                    versions = vuln.content.get('affected_versions', '')
                    # 尝试匹配 "Apache Struts (com.opensymphony:xwork)" 这样的模式
                    component_match = re.search(r'\b(Apache\s+[A-Z][a-zA-Z]+)', versions, re.IGNORECASE)
                    if component_match:
                        new_component = component_match.group(1)
                
                # 验证提取的组件名称
                if new_component and not _is_invalid_component_name(new_component):
                    if not dry_run:
                        vuln.content['affected_component'] = new_component
                        vuln.save(update_fields=['content', 'updated_at'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ {vuln.cve_id}: "{old_component}" -> "{new_component}"'
                        )
                    )
                    fixed_count += 1
                else:
                    # 如果无法提取，清空组件名称
                    if not dry_run:
                        vuln.content['affected_component'] = ''
                        vuln.save(update_fields=['content', 'updated_at'])
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ {vuln.cve_id}: "{old_component}" -> "" (无法提取有效组件名称)'
                        )
                    )
                    failed_count += 1
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'修复完成: {fixed_count} 个成功, {failed_count} 个无法修复'))





