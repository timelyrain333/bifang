"""
oss-security邮件列表漏洞采集插件
从 https://www.openwall.com/lists/oss-security/ 采集漏洞信息
"""
import sys
import os
import re
import logging
import io
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from urllib.parse import urljoin, urlparse

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin

# 尝试导入依赖库
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class Plugin(BasePlugin):
    """oss-security邮件列表漏洞采集插件"""
    
    BASE_URL = 'https://www.openwall.com/lists/oss-security/'
    
    def __init__(self, config=None):
        super().__init__(config)
        if not REQUESTS_AVAILABLE:
            raise ImportError("缺少必需的依赖库，请安装: pip install requests beautifulsoup4 lxml")
        
        # 默认配置
        self.max_days = self.config.get('max_days', 7)  # 默认采集最近7天的数据
        self.year = self.config.get('year', None)  # 指定年份，None则自动获取当前年份
        self.months = self.config.get('months', None)  # 指定月份列表，None则自动获取
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 日志缓冲区
        self.log_buffer = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_buffer)
        self.log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        执行漏洞采集
        
        Returns:
            dict: 执行结果
        """
        log_info = self.log_info
        log_error = self.log_error
        log_warning = self.log_warning
        
        try:
            log_info("开始采集oss-security邮件列表漏洞信息")
            
            # 导入模型（在execute方法中导入，避免循环依赖）
            from app.models import Vulnerability
            from django.utils import timezone
            from django.db import transaction
            
            # 确定采集范围
            if self.year is None:
                current_year = datetime.now().year
            else:
                current_year = int(self.year)
            
            log_info(f"目标年份: {current_year}")
            
            # 获取月份列表
            # 如果用户指定了months且不为空，使用指定的月份
            valid_months = []
            if self.months and isinstance(self.months, list):
                for m in self.months:
                    m_str = str(m).strip()
                    # 过滤掉空字符串和无效值
                    if m_str and m_str != '00' and m_str != '':
                        try:
                            month_num = int(m_str)
                            if 1 <= month_num <= 12:
                                valid_months.append(str(month_num).zfill(2))
                        except ValueError:
                            continue
            
            if valid_months:
                months_to_process = valid_months
            else:
                # 如果指定了max_days，只获取最近N天的数据
                if self.max_days and self.max_days > 0:
                    months_to_process = self._get_recent_months(self.max_days, current_year)
                else:
                    # 默认获取最近7天的数据
                    months_to_process = self._get_recent_months(7, current_year)
            
            if not months_to_process:
                # 如果还是为空，使用当前月份
                current_month = datetime.now().strftime('%m')
                months_to_process = [current_month]
                log_warning(f"月份列表为空，使用当前月份: {current_month}")
            
            log_info(f"需要处理的月份: {', '.join(months_to_process)}")
            
            total_collected = 0
            total_updated = 0
            total_skipped = 0
            errors = []
            
            # 计算日期范围（用于过滤邮件）
            from datetime import timedelta
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=self.max_days) if self.max_days and self.max_days > 0 else end_date - timedelta(days=1)
            
            # 处理每个月份
            for month in months_to_process:
                try:
                    log_info(f"正在处理 {current_year}年{month}月的邮件...")
                    month_url = urljoin(self.BASE_URL, f"{current_year}/{month}/")
                    
                    # 获取该月份在日期范围内的邮件链接（只获取最近N天的邮件）
                    try:
                        email_links = self._get_email_links(month_url, start_date=start_date, end_date=end_date, year=current_year, month=month)
                        log_info(f"找到 {len(email_links)} 封邮件（最近 {self.max_days} 天）")
                    except Exception as e:
                        error_msg = f"获取月份 {month} 的邮件链接失败: {str(e)}"
                        log_error(error_msg)
                        errors.append(error_msg)
                        continue
                    
                    if not email_links:
                        log_warning(f"{month}月最近 {self.max_days} 天没有找到邮件")
                        continue
                    
                    # 处理每封邮件（添加超时保护，避免单个邮件处理时间过长）
                    for email_link in email_links:
                        try:
                            result = self._process_email(email_link, Vulnerability, start_date=start_date, end_date=end_date)
                            if result and isinstance(result, dict):
                                if result.get('status') == 'created':
                                    total_collected += 1
                                elif result.get('status') == 'updated':
                                    total_updated += 1
                                elif result.get('status') == 'skipped':
                                    total_skipped += 1
                        except Exception as e:
                            error_msg = f"处理邮件失败 {email_link}: {str(e)}"
                            log_error(error_msg)
                            errors.append(error_msg)
                            # 继续处理下一封邮件，不中断整个任务
                            continue
                
                except Exception as e:
                    error_msg = f"处理月份 {month} 失败: {str(e)}"
                    log_error(error_msg)
                    errors.append(error_msg)
                    # 继续处理下一个月，不中断整个任务
                    continue
            
            # 获取日志内容
            logs = self.log_buffer.getvalue()
            
            result_message = (
                f"采集完成。新增: {total_collected}, 更新: {total_updated}, "
                f"跳过: {total_skipped}, 错误: {len(errors)}"
            )
            
            log_info(result_message)
            
            return {
                'success': True,
                'message': result_message,
                'data': {
                    'collected': total_collected,
                    'updated': total_updated,
                    'skipped': total_skipped,
                    'errors': len(errors),
                    'error_details': errors[:10]  # 只返回前10个错误
                },
                'logs': logs
            }
        
        except Exception as e:
            error_msg = f"采集失败: {str(e)}"
            self.log_error(error_msg, exc_info=True)
            logs = self.log_buffer.getvalue()
            return {
                'success': False,
                'message': error_msg,
                'data': {},
                'logs': logs
            }
    
    def _get_recent_months(self, max_days: int, year: int) -> List[str]:
        """获取最近N天涉及的月份列表"""
        from datetime import timedelta
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=max_days)
        
        months = set()
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.year == year:
                month_str = current_date.strftime('%m')
                months.add(month_str)
            current_date += timedelta(days=1)
        
        return sorted(list(months))
    
    def _get_months_for_year(self, year: int) -> List[str]:
        """获取指定年份的所有月份链接"""
        try:
            year_url = urljoin(self.BASE_URL, f"{year}/")
            try:
                response = self.session.get(year_url, timeout=30)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                self.log_warning(f"获取年份页面超时: {year_url}")
                # 如果获取失败，返回当前月份
                current_month = datetime.now().strftime('%m')
                return [current_month]
            except requests.exceptions.RequestException as e:
                self.log_warning(f"获取年份页面失败: {year_url}, 错误: {str(e)}")
                # 如果获取失败，返回当前月份
                current_month = datetime.now().strftime('%m')
                return [current_month]
            
            soup = BeautifulSoup(response.text, 'html.parser')
            months = []
            
            # 查找所有月份链接（通常是两位数字，格式如 "01/" 或 "01"）
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # 匹配月份格式：01/, 02/, ..., 12/
                if re.match(r'^\d{2}/?$', href):
                    month = href.rstrip('/')
                    # 验证月份是否在有效范围内
                    if month and len(month) == 2:
                        try:
                            month_num = int(month)
                            if 1 <= month_num <= 12:
                                if month not in months:
                                    months.append(month)
                        except ValueError:
                            continue
            
            # 如果没找到，尝试从表格中提取（月份名称下方的数字链接）
            if not months:
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    # 查找格式如 "01/" 的链接
                    if '/' in href and href.startswith(('0', '1')):
                        parts = href.split('/')
                        if len(parts) >= 2 and parts[0].isdigit():
                            month = parts[0].zfill(2)
                            if month not in months and 1 <= int(month) <= 12:
                                months.append(month)
            
            # 排序月份
            months.sort()
            
            if not months:
                # 如果还是没找到，返回当前月份
                current_month = datetime.now().strftime('%m')
                self.log_warning(f"无法从网页提取月份，使用当前月份: {current_month}")
                return [current_month]
            
            return months
        
        except Exception as e:
            self.log_warning(f"获取月份列表失败: {str(e)}")
            # 如果获取失败，返回当前月份
            current_month = datetime.now().strftime('%m')
            return [current_month]
    
    def _get_email_links(self, month_url: str, start_date: date = None, end_date: date = None, year: int = None, month: str = None) -> List[str]:
        """
        获取指定月份的邮件链接
        
        Args:
            month_url: 月份页面URL
            start_date: 开始日期（可选，用于过滤）
            end_date: 结束日期（可选，用于过滤）
            year: 年份（用于构建完整日期）
            month: 月份（用于构建完整日期）
        """
        try:
            try:
                response = self.session.get(month_url, timeout=30)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                self.log_error(f"获取月份页面超时: {month_url}")
                return []
            except requests.exceptions.ConnectionError as e:
                self.log_error(f"连接失败: {month_url}, 错误: {str(e)}")
                return []
            except requests.exceptions.RequestException as e:
                self.log_error(f"请求失败: {month_url}, 错误: {str(e)}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            email_links = []
            base_url = month_url.rstrip('/') + '/'
            
            # oss-security邮件列表的结构是按日期组织的：
            # 月份页面 -> 日期页面（如01/01/）-> 邮件链接（msg...）
            # 首先获取所有日期链接
            # 日期链接格式：01/, 02/, 03/等（在月份页面的日历表格中）
            date_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # 匹配日期格式：01/, 02/, 03/等（两位数字加斜杠）
                if re.match(r'^\d{2}/?$', href):
                    # 验证日期是否有效（01-31）
                    day = href.rstrip('/')
                    if day and len(day) == 2:
                        try:
                            day_num = int(day)
                            if 1 <= day_num <= 31:
                                # 如果指定了日期范围，检查日期是否在范围内
                                if start_date and end_date and year and month:
                                    try:
                                        email_date = date(year, int(month), day_num)
                                        # 只处理在日期范围内的日期
                                        if email_date < start_date or email_date > end_date:
                                            continue
                                    except ValueError:
                                        # 日期无效（如2月30日），跳过
                                        continue
                                
                                date_url = urljoin(base_url, href)
                                if date_url not in date_links:
                                    date_links.append(date_url)
                        except ValueError:
                            continue
            
            self.log_info(f"找到 {len(date_links)} 个日期页面（在指定日期范围内）")
            
            # 遍历每个日期页面，获取邮件链接
            for date_url in date_links:
                try:
                    try:
                        date_response = self.session.get(date_url, timeout=30)
                        date_response.raise_for_status()
                    except requests.exceptions.Timeout:
                        self.log_warning(f"获取日期页面超时: {date_url}，跳过")
                        continue
                    except requests.exceptions.ConnectionError as e:
                        self.log_warning(f"连接失败: {date_url}, 错误: {str(e)}，跳过")
                        continue
                    except requests.exceptions.RequestException as e:
                        self.log_warning(f"请求失败: {date_url}, 错误: {str(e)}，跳过")
                        continue
                    
                    date_soup = BeautifulSoup(date_response.text, 'html.parser')
                    
                    # 在每个日期页面查找邮件链接
                    # 邮件链接格式是数字：1, 2, 3等（在<ul><li><a href="1">中）
                    for link in date_soup.find_all('a', href=True):
                        href = link.get('href', '')
                        # 邮件链接是纯数字或数字/格式（如"1", "2", "1/"等）
                        href_clean = href.rstrip('/')
                        if href_clean and href_clean.isdigit():
                            # 排除日期链接（格式如"01/", "02/"等）- 邮件编号通常是1-3位数字
                            if len(href_clean) <= 3:
                                full_url = urljoin(date_url, href)
                                if full_url not in email_links:
                                    email_links.append(full_url)
                
                except Exception as e:
                    self.log_warning(f"获取日期页面 {date_url} 失败: {str(e)}")
                    continue
            
            self.log_info(f"从 {month_url} 提取到 {len(email_links)} 个邮件链接")
            if email_links and len(email_links) <= 5:
                for link in email_links[:3]:
                    self.log_info(f"  示例链接: {link}")
            
            return email_links
        
        except Exception as e:
            self.log_error(f"获取邮件链接失败 {month_url}: {str(e)}")
            return []
    
    def _process_email(self, email_url: str, Vulnerability, start_date: date = None, end_date: date = None) -> Dict[str, str]:
        """处理单封邮件，提取漏洞信息并保存到数据库"""
        from django.db import transaction
        from django.utils import timezone
        from datetime import datetime
        
        try:
            try:
                response = self.session.get(email_url, timeout=30)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                self.log_error(f"获取邮件内容超时: {email_url}")
                raise
            except requests.exceptions.ConnectionError as e:
                self.log_error(f"连接失败: {email_url}, 错误: {str(e)}")
                raise
            except requests.exceptions.RequestException as e:
                self.log_error(f"请求失败: {email_url}, 错误: {str(e)}")
                raise
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取邮件内容（通常在<pre>标签中）
            pre_tag = soup.find('pre')
            if not pre_tag:
                return {'status': 'skipped', 'reason': '未找到邮件内容'}
            
            raw_content = pre_tag.get_text()
            
            # 提取邮件头信息
            headers = self._parse_email_headers(raw_content)
            
            # 提取发布日期（先检查日期范围）
            date_str = headers.get('Date', '')
            published_date = self._parse_date(date_str)
            
            # 如果指定了日期范围，检查邮件日期是否在范围内
            if start_date and end_date and published_date:
                if isinstance(published_date, datetime):
                    email_date = published_date.date()
                elif isinstance(published_date, date):
                    email_date = published_date
                else:
                    email_date = None
                
                if email_date:
                    if email_date < start_date or email_date > end_date:
                        return {'status': 'skipped', 'reason': f'邮件日期 {email_date} 不在范围内 ({start_date} 至 {end_date})'}
            
            # 提取CVE编号
            cve_ids = self._extract_cve_ids(raw_content)
            if not cve_ids:
                # 如果没有CVE编号，尝试从标题中提取
                subject = headers.get('Subject', '')
                cve_ids = self._extract_cve_ids(subject)
            
            # 如果没有CVE编号，跳过
            if not cve_ids:
                return {'status': 'skipped', 'reason': '未找到CVE编号'}
            
            # 使用第一个CVE编号作为主标识
            cve_id = cve_ids[0]
            
            # 提取标题
            subject = headers.get('Subject', '').strip()
            if not subject:
                subject = f"Vulnerability: {cve_id}"
            
            # 从Subject中提取组件名（如果存在）
            component_from_subject = self._extract_component_from_subject(subject, cve_id)
            
            # 提取Message-ID
            message_id = headers.get('Message-ID', '').strip()
            if message_id:
                message_id = message_id.strip('<>')
            
            # 提取描述（邮件正文的前几段）
            description = self._extract_description(raw_content)
            
            # 解析结构化信息（针对特定CVE）
            # 优先使用AI模型解析，如果未启用则使用规则解析
            parsed_info = self._parse_vulnerability_info(raw_content, cve_id, subject)
            
            # 如果启用了AI解析，使用AI模型增强解析结果
            if self.config.get('use_ai_parsing', False):
                ai_config = self.config.get('ai_config', {})
                if ai_config.get('api_key') and ai_config.get('enabled', False):
                    try:
                        from app.utils.qianwen import parse_vulnerability_with_ai
                        # 添加超时保护，如果AI解析超时或失败，继续使用规则解析结果
                        try:
                            ai_result = parse_vulnerability_with_ai(
                                raw_content=raw_content,
                                cve_id=cve_id,
                                api_key=ai_config.get('api_key'),
                                api_base=ai_config.get('api_base', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                                model=ai_config.get('model', 'qwen-plus')
                            )
                        except Exception as ai_error:
                            # AI解析失败不影响任务执行，记录警告并继续
                            self.log_warning(f"AI解析CVE {cve_id} 失败: {str(ai_error)}，将使用规则解析结果")
                            ai_result = {}
                        # AI解析结果覆盖规则解析结果（但保留references）
                        # 注意：parse_vulnerability_with_ai 内部已经调用了验证和修正函数
                        if ai_result and isinstance(ai_result, dict):
                            for key in ['basic_description', 'vulnerability_description', 'impact', 
                                       'severity', 'affected_component', 'affected_versions', 
                                       'solution', 'mitigation']:
                                # 只有当AI返回的字段值非空时才覆盖（空字符串不覆盖，因为可能表示AI未找到）
                                ai_value = ai_result.get(key)
                                if ai_value and str(ai_value).strip():
                                    # 对于 affected_component，需要额外验证（虽然已经在parse_vulnerability_with_ai中验证过，但这里再次确认）
                                    if key == 'affected_component':
                                        from app.utils.qianwen import _is_invalid_component_name, _extract_component_from_text
                                        component_value = str(ai_value).strip()
                                        # 如果组件名称无效，尝试从邮件标题或内容中提取
                                        if _is_invalid_component_name(component_value):
                                            self.log_warning(f"AI解析的组件名称无效: '{component_value}' (CVE: {cve_id})，尝试从邮件内容中重新提取")
                                            # 尝试从邮件标题中提取
                                            extracted = _extract_component_from_text(subject or '')
                                            if not extracted:
                                                # 如果从标题中提取失败，尝试从前500字符中提取
                                                extracted = _extract_component_from_text(raw_content[:500])
                                            if extracted and not _is_invalid_component_name(extracted):
                                                parsed_info[key] = extracted
                                                self.log_info(f"从邮件内容中提取到组件名称: '{extracted}' (CVE: {cve_id})")
                                            else:
                                                # 如果无法提取，使用规则解析的结果（component_from_subject）
                                                if component_from_subject and not _is_invalid_component_name(component_from_subject):
                                                    parsed_info[key] = component_from_subject
                                                    self.log_info(f"使用规则解析的组件名称: '{component_from_subject}' (CVE: {cve_id})")
                                                else:
                                                    # 如果规则解析的结果也无效，留空
                                                    parsed_info[key] = ''
                                                    self.log_warning(f"无法提取有效的组件名称 (CVE: {cve_id})，留空")
                                        else:
                                            parsed_info[key] = component_value
                                    # 规范化severity字段（首字母大写）
                                    elif key == 'severity':
                                        severity_value = str(ai_value).strip()
                                        # 规范化：moderate -> Moderate, high -> High等
                                        severity_map = {
                                            'moderate': 'Moderate',
                                            'high': 'High',
                                            'medium': 'Medium',
                                            'low': 'Low',
                                            'critical': 'Critical',
                                            'important': 'Important'
                                        }
                                        severity_lower = severity_value.lower()
                                        if severity_lower in severity_map:
                                            parsed_info[key] = severity_map[severity_lower]
                                        else:
                                            # 首字母大写
                                            parsed_info[key] = severity_value.capitalize()
                                        self.log_info(f"AI模型提取到CVE {cve_id}的危害等级: {parsed_info[key]} (原始值: {ai_value})")
                                    else:
                                        parsed_info[key] = str(ai_value).strip()
                            self.log_info(f"AI模型成功解析CVE {cve_id}的字段信息")
                    except Exception as e:
                        self.log_warning(f"AI解析失败，使用规则解析: {e}")
            
            # 构建结构化内容
            content = {
                'cve_ids': cve_ids,
                'basic_description': parsed_info.get('basic_description', ''),
                'vulnerability_description': parsed_info.get('vulnerability_description', description),
                'impact': parsed_info.get('impact', ''),
                'severity': parsed_info.get('severity', ''),
                'affected_component': parsed_info.get('affected_component', component_from_subject or ''),
                'affected_versions': parsed_info.get('affected_versions', ''),
                'solution': parsed_info.get('solution', ''),
                'mitigation': parsed_info.get('mitigation', ''),
                'references': parsed_info.get('references', []),
                'headers': headers,
            }
            
            # 保存或更新到数据库
            # 使用 cve_id 作为主键去重，而不是 url（因为同一个CVE可能出现在多个邮件中）
            with transaction.atomic():
                # 先尝试根据 cve_id 查找现有记录
                existing = Vulnerability.objects.filter(cve_id=cve_id).first()
                
                if existing:
                    # 如果已存在，更新记录（保留最早的url和published_date）
                    if not existing.published_date and published_date:
                        existing.published_date = published_date
                    if published_date and existing.published_date and published_date < existing.published_date:
                        existing.url = email_url
                        existing.published_date = published_date
                    elif not existing.url:
                        existing.url = email_url
                    
                    # 智能合并content字段：保留已有字段（如果新数据为空），优先使用新数据（如果新数据非空）
                    if existing.content and isinstance(existing.content, dict):
                        merged_content = existing.content.copy()
                        # 对于每个字段，如果新数据非空则使用新数据，否则保留旧数据
                        for key in content.keys():
                            if key == 'references':
                                # references是列表，合并去重
                                old_refs = merged_content.get('references', [])
                                new_refs = content.get('references', [])
                                if isinstance(old_refs, list) and isinstance(new_refs, list):
                                    merged_refs = list(set(old_refs + new_refs))
                                    merged_content['references'] = merged_refs
                                elif new_refs:
                                    merged_content['references'] = new_refs
                            elif key == 'headers':
                                # headers保留旧的（通常是完整的）
                                pass
                            elif key == 'cve_ids':
                                # cve_ids合并去重
                                old_cves = merged_content.get('cve_ids', [])
                                new_cves = content.get('cve_ids', [])
                                if isinstance(old_cves, list) and isinstance(new_cves, list):
                                    merged_cves = list(set(old_cves + new_cves))
                                    merged_content['cve_ids'] = merged_cves
                                elif new_cves:
                                    merged_content['cve_ids'] = new_cves
                            else:
                                # 其他字段：如果新值非空则使用新值，否则保留旧值
                                new_value = content.get(key, '')
                                if new_value and str(new_value).strip():
                                    merged_content[key] = new_value
                                    # 记录重要字段的更新
                                    if key == 'severity':
                                        self.log_info(f"更新CVE {cve_id}的危害等级: {existing.content.get('severity', '空')} -> {new_value}")
                        content = merged_content
                    
                    # 更新其他字段
                    existing.title = subject[:500]
                    existing.description = description
                    existing.message_id = message_id[:100]
                    existing.raw_content = raw_content
                    existing.content = content
                    existing.updated_at = timezone.now()
                    existing.save()
                    created = False
                    vulnerability = existing
                else:
                    # 如果不存在，创建新记录
                    vulnerability = Vulnerability.objects.create(
                        cve_id=cve_id,
                        title=subject[:500],
                        description=description,
                        url=email_url,
                        message_id=message_id[:100],
                        published_date=published_date,
                        raw_content=raw_content,
                        content=content,
                        source='oss_security'
                    )
                    created = True
            
            status = 'created' if created else 'updated'
            self.log_info(f"{'新增' if created else '更新'}漏洞: {cve_id} - {subject[:50]}")
            
            return {'status': status, 'cve_id': cve_id}
        
        except Exception as e:
            self.log_error(f"处理邮件失败 {email_url}: {str(e)}")
            raise
    
    def _parse_email_headers(self, content: str) -> Dict[str, str]:
        """解析邮件头信息"""
        headers = {}
        lines = content.split('\n')
        current_header = None
        
        for line in lines:
            line = line.rstrip('\r')
            if not line:
                break  # 空行表示头部结束
            
            # 检查是否是新的头部字段
            if ':' in line and not line.startswith(' '):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    current_header = parts[0].strip()
                    headers[current_header] = parts[1].strip()
            elif current_header and line.startswith(' '):
                # 续行
                headers[current_header] += ' ' + line.strip()
        
        return headers
    
    def _extract_cve_ids(self, text: str) -> List[str]:
        """从文本中提取CVE编号"""
        # CVE编号格式: CVE-YYYY-NNNN 或 CVE-YYYY-NNNNN
        pattern = r'CVE-\d{4}-\d{4,}'
        cve_ids = re.findall(pattern, text, re.IGNORECASE)
        # 去重并排序
        return sorted(list(set([cve.upper() for cve in cve_ids])))
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """解析日期字符串"""
        if not date_str:
            return None
        
        try:
            # 尝试多种日期格式
            date_formats = [
                '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822格式
                '%a, %d %b %Y %H:%M:%S %Z',
                '%d %b %Y',
                '%Y-%m-%d',
                '%Y/%m/%d',
            ]
            
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.date()
                except ValueError:
                    continue
            
            # 如果都失败了，尝试使用dateutil
            from dateutil import parser
            dt = parser.parse(date_str)
            return dt.date()
        
        except Exception:
            return None
    
    def _extract_description(self, content: str, max_length: int = 5000) -> str:
        """从邮件内容中提取描述（前几段）"""
        lines = content.split('\n')
        
        # 跳过邮件头
        body_start = 0
        for i, line in enumerate(lines):
            if not line.strip():
                body_start = i + 1
                break
        
        # 获取正文部分
        body_lines = lines[body_start:]
        body_text = '\n'.join(body_lines).strip()
        
        # 取前max_length个字符
        if len(body_text) > max_length:
            body_text = body_text[:max_length] + '...'
        
        return body_text
    
    def _parse_vulnerability_info(self, content: str, target_cve_id: str = None, subject: str = '') -> Dict[str, Any]:
        """从邮件内容中解析结构化漏洞信息（增强版）
        
        Args:
            content: 邮件原始内容
            target_cve_id: 目标CVE ID，如果提供则只解析该CVE的段落
        """
        result = {
            'basic_description': '',
            'vulnerability_description': '',
            'impact': '',
            'severity': '',
            'affected_component': '',
            'affected_versions': '',
            'solution': '',
            'mitigation': '',
            'references': []
        }
        
        # 跳过邮件头，获取正文
        lines = content.split('\n')
        body_start = 0
        for i, line in enumerate(lines):
            if not line.strip():
                body_start = i + 1
                break
        
        body_lines = lines[body_start:]
        full_body_text = '\n'.join(body_lines)
        
        # 如果指定了target_cve_id，先提取该CVE的段落
        if target_cve_id:
            body_text = self._extract_cve_section(full_body_text, target_cve_id)
            if not body_text:
                # 如果没找到特定段落，使用全文
                body_text = full_body_text
        else:
            body_text = full_body_text
        
        # 从全文提取版本信息（通常在邮件开头）
        version_info = self._extract_version_from_full_text(full_body_text)
        if version_info:
            if version_info.get('versions'):
                result['affected_versions'] = version_info['versions']
            if version_info.get('component') and not result['affected_component']:
                result['affected_component'] = version_info['component']
        
        # 从Subject中提取组件名（如果还没提取到）
        if not result['affected_component'] and subject:
            component_from_subject = self._extract_component_from_subject(subject, target_cve_id)
            if component_from_subject:
                result['affected_component'] = component_from_subject
        
        # 提取Severity（危害等级）- 从CVE标题中提取，格式：## (Severity: High) CVE-2025-69223
        severity_patterns = [
            r'\(Severity:\s*([^)]+)\)',  # (Severity: High)
            r'Severity:\s*([^\n]+?)(?=\n\s*[A-Z]|$)',  # Severity: High（后面跟着大写字母或结束）
        ]
        for pattern in severity_patterns:
            severity_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE)
            if severity_match:
                severity_text = severity_match.group(1).strip()
                # 如果Severity后面是空的（如"Severity: \nAffected"），跳过
                if not severity_text or severity_text.lower() in ['affected', 'description', 'impact', 'solution']:
                    continue
                # 清理文本，移除可能的CVE编号和其他无关内容
                severity_text = re.sub(r'CVE-\d{4}-\d+', '', severity_text).strip()
                # 只保留常见的安全等级关键词
                severity_keywords = ['Critical', 'High', 'Medium', 'Moderate', 'Low']
                for keyword in severity_keywords:
                    if keyword.lower() in severity_text.lower():
                        result['severity'] = keyword
                        break
                if result['severity']:
                    break
        
        # 如果还没有找到，尝试从Subject中提取
        if not result['severity'] and subject:
            severity_in_subject = re.search(r'\(Severity:\s*([^)]+)\)', subject, re.IGNORECASE)
            if severity_in_subject:
                severity_text = severity_in_subject.group(1).strip()
                severity_keywords = ['Critical', 'High', 'Medium', 'Moderate', 'Low']
                for keyword in severity_keywords:
                    if keyword.lower() in severity_text.lower():
                        result['severity'] = keyword
                        break
        
        # 提取Affected versions（影响版本）- 优先使用从全文提取的版本信息
        # 如果CVE段落中有更具体的版本信息，则使用CVE段落中的
        affected_patterns = [
            r'Affected\s+versions?:\s*\n?([^\n]+(?:\n(?!\n|(?:Credit|References|Solution|Mitigation|Workaround|Description|Impact|Severity|##|Subject):)[^\n]+)*)',
            r'Vulnerable\s+versions?:\s*\n?([^\n]+(?:\n(?!\n|(?:Credit|References|Solution|Mitigation|Workaround|Description|Impact|Severity|##|Subject):)[^\n]+)*)',
            r'Affected\s+software:\s*\n?([^\n]+(?:\n(?!\n|(?:Credit|References|Solution|Mitigation|Workaround|Description|Impact|Severity|##|Subject):)[^\n]+)*)',
            r'This\s+issue\s+affects\s+[^:]+:\s*(.+?)(?=\n\n|\n(?:Credit|References|Solution|Users):|$)',
        ]
        for pattern in affected_patterns:
            affected_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if affected_match:
                affected_text = affected_match.group(1).strip()
                # 清理文本，移除多余空白，但保留换行（用于列表格式）
                affected_text = re.sub(r'[ \t]+', ' ', affected_text)  # 只压缩空格和制表符
                affected_text = re.sub(r'\n{3,}', '\n\n', affected_text)  # 压缩多个换行
                # 如果提取到的版本信息合理（不超过500字符），使用它
                if len(affected_text) < 500 and affected_text and not affected_text.lower().startswith(('d also', 'we\'d', 'we would', 'thanks', 'credit')):
                    result['affected_versions'] = affected_text
                    # 从版本信息中提取组件名
                    component_from_versions = self._extract_component_from_versions(affected_text)
                    if component_from_versions and not result['affected_component']:
                        result['affected_component'] = component_from_versions
                    break
        
        # 提取Description（漏洞描述）- 改进提取逻辑
        desc_patterns = [
            r'Summary:\s*\n?([^\n]+(?:\n(?!\n|(?:###|##|Credit|References|Solution|Mitigation|Workaround|Affected|Impact|Severity|Patch|Description):)[^\n]+)*)',
            r'Description:\s*\n?([^\n]+(?:\n(?!\n|(?:###|##|Credit|References|Solution|Mitigation|Workaround|Affected|Impact|Severity|Patch|Summary):)[^\n]+)*)',
            r'Overview:\s*\n?([^\n]+(?:\n(?!\n|(?:###|##|Credit|References|Solution|Mitigation|Workaround|Affected|Impact|Severity|Patch|Description|Summary):)[^\n]+)*)',
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if desc_match:
                desc_text = desc_match.group(1).strip()
                # 清理文本，移除多余空白，但保留换行
                desc_text = re.sub(r'[ \t]+', ' ', desc_text)  # 只压缩空格和制表符
                desc_text = re.sub(r'\n{3,}', '\n\n', desc_text)  # 压缩多个换行
                # 确保描述有足够内容且不是无关文本
                if len(desc_text) > 20 and not desc_text.lower().startswith(('d also', 'we\'d', 'we would', 'thanks', 'credit', 'on ')):
                    result['vulnerability_description'] = desc_text[:5000]  # 限制长度
                    break
        
        # 对于回复邮件，尝试从引用中提取描述
        if not result['vulnerability_description'] and ('> ' in body_text or 'On ' in body_text[:200]):
            # 这是回复邮件，尝试从引用块中提取
            quote_pattern = r'>\s*(.+?)(?=\n\n|\n(?:On\s+\d|It\s+would|\n[^\s>]))'
            quote_match = re.search(quote_pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if quote_match:
                quoted_text = quote_match.group(1).strip()
                # 移除引用标记
                quoted_text = re.sub(r'^>\s*', '', quoted_text, flags=re.MULTILINE)
                quoted_text = re.sub(r'\s+', ' ', quoted_text)
                if len(quoted_text) > 20:
                    result['vulnerability_description'] = quoted_text[:5000]
        
        # 提取Impact（漏洞影响）
        impact_patterns = [
            r'Impact:\s*(.+?)(?=\n\n|\n(?:###|##|Credit|References|Solution|Mitigation|Workaround|Affected|Description|Severity|Patch):|$)',
            r'Consequences?:\s*(.+?)(?=\n\n|\n(?:###|##|Credit|References|Solution|Mitigation|Workaround|Affected|Description|Severity|Patch):|$)',
        ]
        for pattern in impact_patterns:
            impact_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if impact_match:
                impact_text = impact_match.group(1).strip()
                impact_text = re.sub(r'\s+', ' ', impact_text)
                # 确保不是无关文本
                if not impact_text.lower().startswith(('d also', 'we\'d', 'we would', 'thanks')):
                    result['impact'] = impact_text[:2000]  # 限制长度
                    break
        
        # 如果没有找到Impact，尝试从Description中提取
        if not result['impact'] and result['vulnerability_description']:
            impact_keywords = ['allows', 'enables', 'bypass', 'leak', 'disclose', 'execute', 'access', 'denial']
            sentences = re.split(r'[.!?]\s+', result['vulnerability_description'])
            impact_sentences = []
            for sentence in sentences:
                for keyword in impact_keywords:
                    if keyword in sentence.lower():
                        impact_sentences.append(sentence)
                        break
            if impact_sentences:
                result['impact'] = '. '.join(impact_sentences[:3])  # 取前3句
        
        # 提取Solution（解决方案）
        solution_patterns = [
            r'(?:Solution|Recommendation|Fix|Remediation):\s*\n?([^\n]+(?:\n(?!\n|(?:###|##|Credit|References|Mitigation|Workaround|Affected|Description|Impact|Severity|Patch):)[^\n]+)*)',
            r'Users?\s+(?:are\s+)?(?:recommended|advised)\s+to\s+(.+?)(?=\n\n|\.\s+[A-Z]|$)',
            r'upgrade\s+to\s+version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)(?:\s+or\s+upper)?[^.]*(?:which\s+(?:fixes?|will\s+fix|resolves?)\s+the\s+issue)?',
        ]
        for pattern in solution_patterns:
            solution_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if solution_match:
                solution_text = solution_match.group(1).strip()
                # 如果只匹配到了版本号，构造完整的解决方案
                if re.match(r'^[0-9]+\.[0-9]+', solution_text):
                    result['solution'] = f"Upgrade to version {solution_text} or higher"
                else:
                    solution_text = re.sub(r'[ \t]+', ' ', solution_text)  # 只压缩空格和制表符
                    solution_text = re.sub(r'\n{3,}', '\n\n', solution_text)  # 压缩多个换行
                    result['solution'] = solution_text[:2000]  # 限制长度
                break
        
        # 如果没有找到Solution，但找到了Patch链接，使用Patch链接
        if not result['solution']:
            patch_match = re.search(r'Patch:\s*(https?://[^\s\n]+)', body_text, re.IGNORECASE)
            if patch_match:
                result['solution'] = f"Apply patch: {patch_match.group(1)}"
        
        # 提取Mitigation/Workaround（缓解措施）
        mitigation_patterns = [
            r'(?:Mitigation|Workaround):\s*\n?([^\n]+(?:\n(?!\n|(?:Credit|References|Solution|Affected|Description|Impact|Severity|###|##):)[^\n]+)*)',
            r'Workaround[s]?:\s*\n?([^\n]+(?:\n(?!\n|(?:Credit|References|Solution|Affected|Description|Impact|Severity|###|##):)[^\n]+)*)',
            r'In\s+the\s+meantime[^:]*:\s*(.+?)(?=\n\n|\n(?:Credit|References|Solution|Users|The\s+related):|$)',
            r'can\s+be\s+avoided\s+by\s+(.+?)(?=\n\n|\n(?:Credit|References|Solution|Users|The\s+related|For\s+example):|$)',
        ]
        for pattern in mitigation_patterns:
            mitigation_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if mitigation_match:
                mitigation_text = mitigation_match.group(1).strip()
                # 清理文本，保留换行
                mitigation_text = re.sub(r'[ \t]+', ' ', mitigation_text)
                mitigation_text = re.sub(r'\n{3,}', '\n\n', mitigation_text)
                if len(mitigation_text) > 10 and not mitigation_text.lower().startswith(('d also', 'we\'d', 'we would', 'thanks')):
                    result['mitigation'] = mitigation_text[:2000]  # 限制长度
                    break
        
        # 对于回复邮件，尝试从引用中提取缓解措施
        if not result['mitigation'] and ('> ' in body_text):
            mitigation_in_quote = re.search(r'>\s*[^>]*(?:In\s+the\s+meantime|can\s+be\s+avoided|javax\.xml)(.+?)(?=\n\n|\n[^\s>]|For\s+example:)', body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if mitigation_in_quote:
                mitigation_text = mitigation_in_quote.group(1).strip()
                mitigation_text = re.sub(r'^>\s*', '', mitigation_text, flags=re.MULTILINE)
                mitigation_text = re.sub(r'\s+', ' ', mitigation_text)
                if len(mitigation_text) > 10:
                    result['mitigation'] = mitigation_text[:2000]
        
        # 提取References（参考链接）- 改进提取逻辑，从整个正文中提取所有URL
        ref_patterns = [
            r'References?:\s*(.+?)(?=\n\n|\n[A-Z][a-z]+:|$)',
            r'Links?:\s*(.+?)(?=\n\n|\n[A-Z][a-z]+:|$)',
        ]
        ref_urls = set()
        
        # 首先尝试从References段落提取
        for pattern in ref_patterns:
            ref_match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if ref_match:
                ref_text = ref_match.group(1)
                urls = re.findall(r'https?://[^\s\n<>\)]+', ref_text)
                ref_urls.update(urls)
        
        # 如果References段落没有找到，从整个正文中提取所有URL（但排除邮件链接）
        if not ref_urls:
            all_urls = re.findall(r'https?://[^\s\n<>\)]+', body_text)
            for url in all_urls:
                # 排除明显的邮件链接和openwall链接
                if 'openwall.com' not in url and 'mailto:' not in url:
                    ref_urls.add(url)
        
        result['references'] = sorted(list(ref_urls))  # 排序并去重
        
        # 基本描述（从标题或第一段提取）
        if result['vulnerability_description']:
            # 取描述的第一句话作为基本描述
            first_sentence = re.split(r'[.!?]\s+', result['vulnerability_description'])[0]
            result['basic_description'] = first_sentence[:200]  # 限制长度
        elif result['impact']:
            # 如果没有描述，使用impact的第一句话
            first_sentence = re.split(r'[.!?]\s+', result['impact'])[0]
            result['basic_description'] = first_sentence[:200]
        
        # 如果没有从CVE段落提取到组件名，尝试从CVE标题中提取
        if not result['affected_component'] and target_cve_id:
            component_from_title = self._extract_component_from_cve_title(body_text, target_cve_id)
            if component_from_title:
                result['affected_component'] = component_from_title
        
        return result
    
    def _extract_cve_section(self, body_text: str, cve_id: str) -> str:
        """从邮件正文中提取特定CVE的段落"""
        # 查找CVE段落，格式通常是：
        # ## (Severity: High) CVE-2025-69223 - component name
        # 或
        # CVE-2025-69223 - component name
        cve_pattern = rf'(?:##\s*\([^)]+\)\s*)?{re.escape(cve_id)}\s*-\s*[^\n]+'
        match = re.search(cve_pattern, body_text, re.IGNORECASE | re.MULTILINE)
        
        if not match:
            return ''
        
        start_pos = match.start()
        
        # 查找下一个CVE段落或邮件结束
        next_cve_pattern = r'\n##\s*\([^)]+\)\s*CVE-\d{4}-\d+'
        next_match = re.search(next_cve_pattern, body_text[start_pos + 100:], re.IGNORECASE | re.MULTILINE)
        
        if next_match:
            end_pos = start_pos + 100 + next_match.start()
        else:
            end_pos = len(body_text)
        
        return body_text[start_pos:end_pos]
    
    def _extract_version_from_full_text(self, body_text: str) -> Dict[str, str]:
        """从邮件全文提取版本信息（通常在开头）"""
        result = {}
        
        # 查找版本信息，常见格式：
        # "All of the below issues have been fixed in version X.Y.Z"
        # "Fixed in version X.Y.Z"
        # "Affected versions: X.Y.Z through Y.Z.W"
        version_patterns = [
            r'(?:All\s+of\s+the\s+below\s+issues\s+have\s+been\s+fixed|Fixed)\s+in\s+version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)',
            r'upgrade\s+to\s+version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)',
            r'version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)\s+and\s+earlier',
            r'versions?\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)\s+through\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)',
            r'Affected\s+versions?:\s*([^\n]+?)(?:\n\n|\n[A-Z]|$)',
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE)
            if match:
                if len(match.groups()) == 2:
                    # 版本范围
                    result['versions'] = f"{match.group(1)} through {match.group(2)}"
                else:
                    # 单个版本
                    version = match.group(1).strip()
                    # 判断是修复版本还是受影响版本
                    pattern_lower = pattern.lower()
                    if 'upgrade to version' in pattern_lower or 'fixed in version' in pattern_lower:
                        result['versions'] = f"< {version}"  # 表示低于此版本的都受影响
                    else:
                        result['versions'] = version
                break
        
        # 尝试从邮件开头提取组件名
        # 通常在Subject或第一段中
        component_patterns = [
            r'Multiple\s+vulnerabilities\s+in\s+([A-Za-z][A-Za-z0-9\s\-\.]+)',
            r'([A-Za-z][A-Za-z0-9\s\-\.]+)\s+is\s+an?\s+',
            r'([A-Za-z][A-Za-z0-9\s\-\.]+)\s+vulnerabilities?',
        ]
        
        # 只在前500个字符中查找组件名（通常在开头）
        header_text = body_text[:500]
        for pattern in component_patterns:
            match = re.search(pattern, header_text, re.IGNORECASE)
            if match:
                component = match.group(1).strip()
                # 清理组件名，只取前两个词（通常是"Apache XXX"格式）
                component_words = component.split()[:2]
                component = ' '.join(component_words)
                if len(component) < 50:  # 避免提取到过长的文本
                    result['component'] = component
                    break
        
        return result
    
    def _extract_component_from_subject(self, subject: str, cve_id: str = None) -> str:
        """从邮件Subject中提取组件名"""
        if not subject:
            return ''
        
        # Subject格式通常是：
        # "CVE-2025-68280: Apache SIS: XML External Entity (XXE) vulnerability"
        # "Re: CVE-2025-68280: Apache SIS: ..."
        # "CVE-2025-66518: Apache Kyuubi: Unauthorized directory access..."
        patterns = [
            rf'{re.escape(cve_id)}\s*:\s*([A-Za-z][A-Za-z0-9\s\-\.]+?)(?:\s*:|$)',  # CVE-XXX: Component Name:
            r':\s*([A-Za-z][A-Za-z0-9\s\-\.]+?)\s*:',  # : Component Name:
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*:',  # Apache XXX:
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                component = match.group(1).strip()
                # 只取前两个词（通常是"Apache XXX"或"Component Name"格式）
                component_words = component.split()[:2]
                component = ' '.join(component_words)
                # 过滤掉常见的非组件名
                if component.lower() not in ['re', 'xml', 'xxe', 'unauthorized', 'directory', 'access', 'missing', 'path']:
                    if len(component) < 50:
                        return component
        
        return ''
    
    def _extract_component_from_versions(self, versions_text: str) -> str:
        """从版本信息中提取组件名"""
        if not versions_text:
            return ''
        
        # 版本信息格式通常是：
        # "- Apache Kyuubi (org.apache.kyuubi:kyuubi-server) 1.6.0 through <=1.10.2"
        # "Apache SIS 0.4 through 1.5"
        patterns = [
            r'[-*\s]*([A-Za-z][A-Za-z0-9\s\-\.]+?)\s*\(org\.[^)]+\)',  # Component (org.package)
            r'[-*\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+[0-9]',  # Apache XXX 1.2.3
            r'[-*\s]*([A-Za-z][A-Za-z0-9\s\-\.]+?)\s+[0-9]+\.[0-9]+',  # Component 1.2.3
        ]
        
        for pattern in patterns:
            match = re.search(pattern, versions_text, re.MULTILINE)
            if match:
                component = match.group(1).strip()
                # 只取前两个词
                component_words = component.split()[:2]
                component = ' '.join(component_words)
                if len(component) < 50:
                    return component
        
        return ''
    
    def _extract_component_from_cve_title(self, cve_section: str, cve_id: str) -> str:
        """从CVE标题中提取组件名"""
        # CVE标题格式：CVE-2025-69223 - component name description
        pattern = rf'{re.escape(cve_id)}\s*-\s*([A-Za-z][A-Za-z0-9\s\-\.]+?)(?:\s+(?:susceptible|vulnerability|DoS|denial|issue|bug)|$)'
        match = re.search(pattern, cve_section, re.IGNORECASE)
        if match:
            component = match.group(1).strip()
            # 清理组件名
            component = re.sub(r'\s+', ' ', component)
            if len(component) < 50:
                return component
        
        # 如果上面没找到，尝试更简单的模式
        pattern2 = rf'{re.escape(cve_id)}\s*-\s*([A-Za-z][A-Za-z0-9\s\-\.]+)'
        match2 = re.search(pattern2, cve_section, re.IGNORECASE)
        if match2:
            component = match2.group(1).strip().split()[0]  # 只取第一个词
            if len(component) < 50:
                return component
        
        return ''
