"""
国家信息安全漏洞共享平台（CNVD）漏洞列表采集插件
从 https://www.cnvd.org.cn/flaw/list 直接抓取列表页与详情页获取漏洞信息。
默认只采集最近 1 天的数据。

521 根因说明：
站点使用动态 Cookie + JS 挑战：首次请求返回混淆 JS，要求浏览器执行后生成 __jsl_clearance_s（或类似）
cookie，携带该 cookie 再次请求才返回 200。纯 requests 不执行 JS，无法拿到 clearance cookie，故会持续 521。
可选安装 cloudscraper（pip install cloudscraper）由插件尝试绕过；若仍 521，需使用能执行 JS 的客户端（如 Selenium/Playwright）。
"""
import re
import logging
import io
import time
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from urllib.parse import urljoin, urlparse

BASE_DIR = __import__('pathlib').Path(__file__).resolve().parent.parent.parent
import sys
sys.path.insert(0, str(BASE_DIR))

from app.lib.base_plugin import BasePlugin

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# 可选：cloudscraper 可尝试解析 JS 挑战并获取 clearance cookie，部分环境可绕过 521
CLOUDSCRAPER_AVAILABLE = False
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    pass

# 可选：Playwright 执行真实浏览器 JS，可拿到 521 的 clearance cookie；需 pip install playwright && playwright install chromium
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

PLUGIN_INFO = {
    'description': '从国家信息安全漏洞共享平台（CNVD）采集漏洞列表数据，仅使用 www.cnvd.org.cn',
}

CNVD_BASE_URL = 'https://www.cnvd.org.cn'
CNVD_LIST_URL = f'{CNVD_BASE_URL}/flaw/list.htm'


class Plugin(BasePlugin):
    """CNVD 漏洞列表采集插件（直接抓取列表页 + 详情页）"""

    def __init__(self, config=None):
        super().__init__(config)
        if not REQUESTS_AVAILABLE:
            raise ImportError("缺少依赖: pip install requests beautifulsoup4 lxml")

        self.max_days = self.config.get('max_days', 1)  # 默认只采集最近 1 天
        self.max_pages = self.config.get('max_pages', 1)  # 默认只抓第 1 页
        self.page_size = self.config.get('page_size', 20)  # 每页条数
        self.playwright_headless = self.config.get('playwright_headless', True)  # False 时开真实窗口，需图形界面
        self.request_delay = self.config.get('request_delay', 2)
        self.detail_delay = self.config.get('detail_delay', 1)
        self.retry_times = self.config.get('retry_times', 2)

        self.BASE_URL = CNVD_BASE_URL
        self.LIST_URL = CNVD_LIST_URL

        # 优先使用 cloudscraper（可尝试解析 JS 挑战拿到 clearance cookie），否则用普通 Session
        if CLOUDSCRAPER_AVAILABLE:
            self.session = cloudscraper.create_scraper()
        else:
            self.session = requests.Session()

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': f'{self.BASE_URL}/',
        })

        self.log_buffer = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_buffer)
        self.log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        log_info = self.log_info
        log_error = self.log_error
        log_warning = self.log_warning

        try:
            log_info("开始采集国家信息安全漏洞共享平台（CNVD）漏洞列表（仅 www.cnvd.org.cn）")
            log_info(f"采集范围: 最近 {self.max_days} 天, 最多 {self.max_pages} 页列表")
            if CLOUDSCRAPER_AVAILABLE:
                log_info("已使用 cloudscraper 尝试绕过 JS 挑战")
            else:
                log_info("未安装 cloudscraper，纯 requests 请求；若遇 521 可 pip install cloudscraper 后重试")
            if PLAYWRIGHT_AVAILABLE:
                log_info("已启用 Playwright 回退（521 时将用浏览器获取 cookie）")

            from app.models import Vulnerability

            flaw_links = self._fetch_flaw_links()
            log_info(f"从列表页获取到 {len(flaw_links)} 条漏洞链接")

            if not flaw_links:
                log_warning(
                    "未获取到任何漏洞链接。521 根因：站点使用动态 Cookie + JS 挑战。"
                    "可尝试在任务配置中设置 playwright_headless: false（需有图形界面）；或改用其他漏洞情报源。"
                )
                logs = self.log_buffer.getvalue()
                return {
                    'success': True,
                    'message': '未获取到漏洞链接',
                    'data': {'collected': 0, 'updated': 0, 'skipped': 0, 'errors': 0},
                    'logs': logs
                }

            total_collected = 0
            total_updated = 0
            total_skipped = 0
            errors = []

            for i, detail_url in enumerate(flaw_links):
                if i > 0:
                    time.sleep(max(0, self.detail_delay))
                try:
                    result = self._process_flaw_detail(detail_url, Vulnerability)
                    if result and isinstance(result, dict):
                        status = result.get('status')
                        if status == 'created':
                            total_collected += 1
                        elif status == 'updated':
                            total_updated += 1
                        elif status == 'skipped':
                            total_skipped += 1
                except Exception as e:
                    error_msg = f"处理漏洞失败 {detail_url}: {str(e)}"
                    log_error(error_msg)
                    errors.append(error_msg)
                    continue

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
                    'error_details': errors[:10]
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

    def _ensure_playwright_cookies(self) -> bool:
        """用 Playwright 打开首页执行 JS 挑战，将获得的 cookie 写入 self.session。成功返回 True。"""
        if not PLAYWRIGHT_AVAILABLE:
            return False
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                page.goto(f'{self.BASE_URL}/', wait_until='load', timeout=20000)
                time.sleep(3)
                cookies = context.cookies(self.BASE_URL)
                browser.close()
            if not cookies:
                return False
            for c in cookies:
                self.session.cookies.set(
                    c['name'], c.get('value', ''),
                    domain=c.get('domain') or '',
                    path=c.get('path') or '/'
                )
            return True
        except Exception as e:
            self.log_error(f"Playwright 获取 cookie 失败: {e}")
            return False

    def _fetch_flaw_links_via_playwright(self) -> List[str]:
        """用 Playwright 直接打开列表页，等 521 的 JS 执行完、表格出现后再解析；并把 cookie 写入 self.session。"""
        if not PLAYWRIGHT_AVAILABLE:
            return []
        links = []
        seen = set()
        try:
            with sync_playwright() as p:
                launch_opts = {
                    'headless': self.playwright_headless,
                    'args': ['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage']
                }
                try:
                    browser = p.chromium.launch(**launch_opts)
                except Exception:
                    launch_opts['headless'] = True
                    browser = p.chromium.launch(**launch_opts)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    extra_http_headers={'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', 'Referer': f'{self.BASE_URL}/'}
                )
                page = context.new_page()
                if not self.playwright_headless and self.max_pages > 0:
                    self.log_info("Playwright: 先打开首页建立会话，请完成验证码（如有）后脚本再进入列表页。")
                    page.goto(f'{self.BASE_URL}/', wait_until='domcontentloaded', timeout=35000)
                    time.sleep(15)
                for page_idx in range(self.max_pages):
                    offset = page_idx * self.page_size
                    list_url = f'{CNVD_LIST_URL}?max={self.page_size}&offset={offset}'
                    self.log_info(f"Playwright: 打开列表页(第 {page_idx + 1} 页) headless={self.playwright_headless} {list_url}")
                    if not self.playwright_headless and page_idx == 0:
                        self.log_info("若出现验证码请手动完成；提交后若跳转 404，将自动用表单 POST 获取列表。")
                    page.goto(list_url, wait_until='domcontentloaded', timeout=35000)
                    try:
                        page.wait_for_response(
                            lambda r: list_url in r.url and r.status == 200,
                            timeout=60000
                        )
                    except Exception:
                        pass
                    time.sleep(5)
                    table_timeout = 120000 if not self.playwright_headless else 15000
                    try:
                        page.wait_for_selector('table.tlist tbody tr, #flawList table tbody tr, #flawList tr', timeout=table_timeout)
                    except Exception:
                        if page_idx == 0:
                            try:
                                page.fill('input[name="max"]', str(self.page_size))
                                page.fill('input[name="offset"]', str(offset))
                                page.click('input[type="submit"], button[type="submit"], .btn_search')
                                time.sleep(5)
                                page.wait_for_selector('table.tlist tbody tr, #flawList table tbody tr, #flawList tr', timeout=table_timeout)
                            except Exception:
                                pass
                    time.sleep(2)
                    html = page.content()
                    if page_idx == 0 and ('未找到' in html or '404' in html) and 'flawList' not in html and 'tlist' not in html:
                        self.log_info("当前页为 404/未找到，在浏览器内用表单 POST 提交到列表页（由浏览器发起，保留 cookie 与指纹）...")
                        try:
                            page.evaluate("""(args) => {
                                const form = document.createElement('form');
                                form.method = 'POST';
                                form.action = args.url;
                                const maxInput = document.createElement('input');
                                maxInput.name = 'max';
                                maxInput.value = String(args.max);
                                form.appendChild(maxInput);
                                const offsetInput = document.createElement('input');
                                offsetInput.name = 'offset';
                                offsetInput.value = String(args.offset);
                                form.appendChild(offsetInput);
                                document.body.appendChild(form);
                                form.submit();
                            }""", {'url': CNVD_LIST_URL, 'max': self.page_size, 'offset': offset})
                            page.wait_for_load_state('networkidle', timeout=20000)
                            time.sleep(3)
                            try:
                                page.wait_for_selector('table.tlist tbody tr, #flawList table tbody tr, #flawList tr', timeout=15000)
                            except Exception:
                                pass
                            html = page.content()
                        except Exception as e:
                            self.log_error(f"浏览器内表单 POST 失败: {e}")
                    soup = BeautifulSoup(html, 'html.parser')
                    page_links = 0
                    for container in (soup.select_one('#flawList table') or soup.select_one('#flawList'), soup.select_one('table.tlist')):
                        if not container:
                            continue
                        tbody = container.find('tbody') or container
                        for tr in tbody.select('tr'):
                            tds = tr.find_all('td')
                            if not tds:
                                continue
                            first_td = tds[0]
                            a = first_td.find('a', href=True)
                            if not a:
                                continue
                            href = (a.get('href') or '').strip()
                            if '/flaw/show/' not in href and not re.search(r'CNVD-\d{4}-\d+', href):
                                continue
                            full_url = urljoin(self.BASE_URL + '/', href.lstrip('/'))
                            if full_url not in seen:
                                seen.add(full_url)
                                links.append(full_url)
                                page_links += 1
                        if page_links > 0:
                            break
                    if page_links == 0:
                        for a in soup.find_all('a', href=True):
                            href = (a.get('href') or '').strip()
                            if '/flaw/show/' in href or re.search(r'CNVD-\d{4}-\d+', href):
                                full_url = urljoin(self.BASE_URL + '/', href.lstrip('/'))
                                if full_url not in seen:
                                    seen.add(full_url)
                                    links.append(full_url)
                                    page_links += 1
                    if page_links == 0 and page_idx == 0:
                        break
                    if page_idx < self.max_pages - 1:
                        time.sleep(max(0, self.request_delay) + random.uniform(0, 1))
                cookies = context.cookies(self.BASE_URL)
                browser.close()
                for c in cookies:
                    self.session.cookies.set(
                        c['name'], c.get('value', ''),
                        domain=c.get('domain') or '',
                        path=c.get('path') or '/'
                    )
        except Exception as e:
            self.log_error(f"Playwright 抓取列表失败: {e}")
        return links

    def _request(self, url: str, method: str = 'GET', data: Optional[Dict] = None) -> Optional[requests.Response]:
        for attempt in range(self.retry_times + 1):
            try:
                if method.upper() == 'POST':
                    resp = self.session.post(url, data=data or {}, timeout=30)
                else:
                    resp = self.session.get(url, timeout=30)
                resp.encoding = resp.apparent_encoding or 'utf-8'
                if resp.status_code == 521:
                    self.log_warning("收到 521（Cloudflare/源站未响应）")
                    return None
                resp.raise_for_status()
                return resp
            except requests.exceptions.RequestException as e:
                self.log_error(f"请求失败 {url}: {e}")
                if attempt < self.retry_times:
                    time.sleep(1 + attempt)
        return None

    def _fetch_flaw_links(self) -> List[str]:
        """从列表页获取漏洞详情页链接。POST 提交 max/offset，解析 #flawList 或 table.tlist。"""
        links = []
        seen = set()
        _playwright_tried = False

        self.log_info("预访问首页以建立会话...")
        try:
            self.session.get(f'{self.BASE_URL}/', timeout=15)
            time.sleep(max(0, self.request_delay))
        except Exception:
            pass

        for page in range(self.max_pages):
            offset = page * self.page_size
            self.log_info(f"抓取列表页(第 {page + 1} 页): POST {CNVD_LIST_URL} max={self.page_size} offset={offset}")

            resp = None
            try:
                resp = self.session.post(
                    CNVD_LIST_URL,
                    data={'max': self.page_size, 'offset': offset},
                    timeout=30
                )
                resp.encoding = resp.apparent_encoding or 'utf-8'
            except requests.exceptions.RequestException as e:
                self.log_error(f"请求列表页失败: {e}")
                break

            if resp and resp.status_code == 521:
                self.log_warning("POST 返回 521，尝试 GET 方式...")
                try:
                    get_url = f'{CNVD_LIST_URL}?max={self.page_size}&offset={offset}'
                    resp = self.session.get(get_url, timeout=30)
                    resp.encoding = resp.apparent_encoding or 'utf-8'
                except requests.exceptions.RequestException as e:
                    self.log_error(f"GET 列表页失败: {e}")
                    resp = None

            if (not resp or resp.status_code == 521) and PLAYWRIGHT_AVAILABLE and not _playwright_tried:
                self.log_info("收到 521，改用 Playwright 在浏览器内直接请求列表页...")
                _playwright_tried = True
                pw_links = self._fetch_flaw_links_via_playwright()
                if pw_links:
                    links.extend(pw_links)
                    return links
                resp = None

            if not resp or resp.status_code == 521:
                self.log_warning(
                    "收到 521：站点使用 JS 挑战 + 动态 Cookie（如 __jsl_clearance_s），纯 requests 无法绕过。"
                    "若 Playwright 仍 521，可在任务配置中设置 playwright_headless: false（需有图形界面）尝试非无头浏览器；或改用其他漏洞情报源。"
                )
                break
            try:
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                self.log_error(f"请求列表页失败: {e}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            page_links = 0

            for container in (soup.select_one('#flawList table') or soup.select_one('#flawList'), soup.select_one('table.tlist')):
                if not container:
                    continue
                tbody = container.find('tbody') or container
                for tr in tbody.select('tr'):
                    tds = tr.find_all('td')
                    if not tds:
                        continue
                    first_td = tds[0]
                    a = first_td.find('a', href=True)
                    if not a:
                        continue
                    href = (a.get('href') or '').strip()
                    if '/flaw/show/' not in href and not re.search(r'CNVD-\d{4}-\d+', href):
                        continue
                    full_url = urljoin(self.BASE_URL + '/', href.lstrip('/'))
                    if full_url not in seen:
                        seen.add(full_url)
                        links.append(full_url)
                        page_links += 1
                if page_links > 0:
                    break

            if page_links == 0:
                for a in soup.find_all('a', href=True):
                    href = (a.get('href') or '').strip()
                    if '/flaw/show/' in href or re.search(r'CNVD-\d{4}-\d+', href):
                        full_url = urljoin(self.BASE_URL + '/', href.lstrip('/'))
                        if full_url not in seen:
                            seen.add(full_url)
                            links.append(full_url)
                            page_links += 1

            if page_links == 0:
                break

            if page < self.max_pages - 1:
                time.sleep(max(0, self.request_delay) + random.uniform(0, 1))

        return links

    def _request_detail(self, url: str) -> Optional[requests.Response]:
        for attempt in range(self.retry_times + 1):
            try:
                resp = self.session.get(url, timeout=30)
                resp.encoding = resp.apparent_encoding or 'utf-8'
                if resp.status_code == 521:
                    self.log_warning("详情页 521（Cloudflare/源站未响应）")
                    return None
                resp.raise_for_status()
                return resp
            except requests.exceptions.RequestException as e:
                self.log_error(f"请求详情失败 {url}: {e}")
                if attempt < self.retry_times:
                    time.sleep(1 + attempt)
        return None

    def _process_flaw_detail(self, detail_url: str, Vulnerability) -> Optional[Dict[str, Any]]:
        """抓取并解析单条漏洞详情页，写入数据库。"""
        from django.db import transaction
        from django.utils import timezone

        resp = self._request_detail(detail_url)
        if resp is None:
            raise RuntimeError(f"请求详情页失败: {detail_url}")

        soup = BeautifulSoup(resp.text, 'html.parser')
        raw_content = resp.text

        cnvd_match = re.search(r'CNVD-\d{4}-\d+', detail_url)
        if not cnvd_match:
            cnvd_match = re.search(r'CNVD-\d{4}-\d+', raw_content)
        cnvd_id = cnvd_match.group(0) if cnvd_match else None
        if not cnvd_id:
            self.log_warning(f"未解析到 CNVD 编号: {detail_url}")
            return {'status': 'skipped', 'reason': '未找到 CNVD 编号'}

        title = ''
        h1 = soup.select_one('.blkContainerSblk h1') or soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
        if not title:
            for row in soup.select('table tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    if '漏洞名称' in label or '漏洞标题' in label:
                        title = cells[1].get_text(strip=True)
                        break
        if not title:
            title = f"{cnvd_id} - 漏洞"

        table_data = self._parse_detail_table(soup)
        description = (table_data.get('漏洞描述') or table_data.get('description') or '').strip()
        pub_str = (
            table_data.get('公开日期') or table_data.get('发布时间') or
            table_data.get('提交时间') or table_data.get('public_time') or ''
        )
        published_date = self._parse_published_date(pub_str)
        severity = (table_data.get('危害级别') or table_data.get('level') or '').strip()
        cve_id = (table_data.get('CVE ID') or table_data.get('cve_id') or '').strip()
        if not cve_id and 'CVE-' in raw_content:
            cve_match = re.search(r'CVE-\d{4}-\d{4,}', raw_content)
            if cve_match:
                cve_id = cve_match.group(0)

        if self.max_days and self.max_days > 0 and published_date is not None:
            cutoff = date.today() - timedelta(days=self.max_days)
            if published_date < cutoff:
                self.log_info(f"跳过 {cnvd_id}：发布日期 {published_date} 早于 {cutoff}（仅采集最近 {self.max_days} 天）")
                return {'status': 'skipped', 'reason': f'超出采集日期范围（仅采集最近 {self.max_days} 天）'}

        identifier = cnvd_id
        content = {
            'cnvd_id': cnvd_id,
            'cve_ids': [cve_id] if cve_id else [],
            'basic_description': (description[:500] if description else title[:500]),
            'vulnerability_description': description,
            'impact': table_data.get('危害描述') or table_data.get('impact') or '',
            'severity': severity,
            'affected_component': table_data.get('影响产品') or table_data.get('vendor') or '',
            'affected_versions': table_data.get('影响版本') or '',
            'solution': table_data.get('漏洞解决方案') or table_data.get('修复方案') or table_data.get('solution') or '',
            'references': [],
        }
        ref_links = table_data.get('参考链接') or ''
        if ref_links:
            content['references'] = [r.strip() for r in ref_links.split() if r.strip()]

        with transaction.atomic():
            existing = Vulnerability.objects.filter(source='cnvd', url=detail_url).first()
            if not existing:
                existing = Vulnerability.objects.filter(source='cnvd', cve_id=identifier).first()

            if existing:
                existing.title = title[:500]
                existing.description = description
                existing.content = {**(existing.content or {}), **content}
                if published_date:
                    existing.published_date = published_date
                existing.raw_content = raw_content[:50000]
                existing.updated_at = timezone.now()
                existing.save()
                self.log_info(f"更新漏洞: {identifier} - {title[:40]}")
                return {'status': 'updated', 'cnvd_id': identifier}
            else:
                Vulnerability.objects.create(
                    cve_id=identifier,
                    title=title[:500],
                    description=description,
                    url=detail_url,
                    message_id='',
                    published_date=published_date,
                    raw_content=raw_content[:50000],
                    content=content,
                    source='cnvd'
                )
                self.log_info(f"新增漏洞: {identifier} - {title[:40]}")
                return {'status': 'created', 'cnvd_id': identifier}

    def _parse_detail_table(self, soup: BeautifulSoup) -> Dict[str, str]:
        result = {}
        for row in soup.select('table tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).strip('：:')
                value = cells[1].get_text(strip=True)
                if key and value:
                    result[key] = value
            if len(cells) >= 2 and '参考链接' in (cells[0].get_text(strip=True) or ''):
                a = cells[1].find('a', href=True)
                if a:
                    result['参考链接'] = a.get('href', '').strip()
        return result

    def _parse_published_date(self, date_str: str) -> Optional[date]:
        if not date_str or not str(date_str).strip():
            return None
        s = str(date_str).strip()
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日'):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
        return None


