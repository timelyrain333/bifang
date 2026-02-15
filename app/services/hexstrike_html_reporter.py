"""
HexStrike 扫描报告生成器
生成美观的 HTML 安全评估报告
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from django.conf import settings


class HexStrikeHTMLReporter:
    """HexStrike HTML 报告生成器"""

    def __init__(self, reports_dir: Optional[str] = None):
        """
        初始化报告生成器

        Args:
            reports_dir: 报告保存目录，默认为 BASE_DIR/reports
        """
        if reports_dir is None:
            from pathlib import Path
            base_dir = Path(settings.BASE_DIR)
            reports_dir = base_dir / 'reports'

        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_report(
        self,
        target: str,
        nmap_results: Optional[Dict] = None,
        nuclei_results: Optional[Dict] = None,
        target_profile: Optional[Dict] = None
    ) -> str:
        """
        生成 HTML 报告

        Args:
            target: 扫描目标
            nmap_results: Nmap 扫描结果
            nuclei_results: Nuclei 扫描结果
            target_profile: 目标画像

        Returns:
            报告文件路径（相对于 reports 目录）
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"hexstrike_report_{target.replace('.', '_').replace(':', '_')}_{timestamp}.html"
        filepath = self.reports_dir / filename

        # 生成 HTML 内容
        html_content = self._generate_html(
            target=target,
            nmap_results=nmap_results,
            nuclei_results=nuclei_results,
            target_profile=target_profile,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filename

    def _generate_html(
        self,
        target: str,
        nmap_results: Optional[Dict],
        nuclei_results: Optional[Dict],
        target_profile: Optional[Dict],
        timestamp: str
    ) -> str:
        """生成 HTML 内容"""

        # 提取统计数据
        stats = self._extract_stats(nmap_results, nuclei_results)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>安全评估报告 - {target}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
                'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f7fa;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}

        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 16px;
            opacity: 0.9;
        }}

        .header .meta {{
            margin-top: 20px;
            font-size: 14px;
            opacity: 0.85;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}

        .summary-card .number {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .summary-card .label {{
            color: #666;
            font-size: 14px;
        }}

        .summary-card.risk-critical .number {{ color: #f56c6c; }}
        .summary-card.risk-high .number {{ color: #e6a23c; }}
        .summary-card.risk-medium .number {{ color: #409eff; }}
        .summary-card.risk-low .number {{ color: #67c23a; }}
        .summary-card.risk-info .number {{ color: #909399; }}

        .section {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}

        .section-title {{
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
            color: #667eea;
        }}

        .vulnerability-list {{
            list-style: none;
        }}

        .vulnerability-item {{
            padding: 15px;
            margin-bottom: 10px;
            border-left: 4px solid #ddd;
            background: #f9f9f9;
            border-radius: 4px;
        }}

        .vulnerability-item.critical {{ border-left-color: #f56c6c; }}
        .vulnerability-item.high {{ border-left-color: #e6a23c; }}
        .vulnerability-item.medium {{ border-left-color: #409eff; }}
        .vulnerability-item.low {{ border-left-color: #67c23a; }}
        .vulnerability-item.info {{ border-left-color: #909399; }}

        .vulnerability-item .title {{
            font-weight: bold;
            margin-bottom: 5px;
            font-size: 16px;
        }}

        .vulnerability-item .severity {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 10px;
        }}

        .severity-critical {{ background: #f56c6c; color: white; }}
        .severity-high {{ background: #e6a23c; color: white; }}
        .severity-medium {{ background: #409eff; color: white; }}
        .severity-low {{ background: #67c23a; color: white; }}
        .severity-info {{ background: #909399; color: white; }}

        .port-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}

        .port-item {{
            padding: 15px;
            background: #f9f9f9;
            border-radius: 5px;
            border-left: 4px solid #67c23a;
        }}

        .port-item.open {{ border-left-color: #67c23a; }}
        .port-item.closed {{ border-left-color: #909399; }}
        .port-item.filtered {{ border-left-color: #409eff; }}

        .port-item .port-number {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .port-item .service {{
            color: #666;
            font-size: 14px;
        }}

        .recommendations {{
            background: #f0f9ff;
            border-left: 4px solid #409eff;
            padding: 15px;
            border-radius: 4px;
        }}

        .recommendations ul {{
            margin-left: 20px;
            margin-top: 10px;
        }}

        .recommendations li {{
            margin-bottom: 8px;
        }}

        .risk-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }}

        .risk-critical {{ background: #fee; color: #f56c6c; }}
        .risk-high {{ background: #fef0e0; color: #e6a23c; }}
        .risk-medium {{ background: #ecf5ff; color: #409eff; }}
        .risk-low {{ background: #f0f9ff; color: #67c23a; }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 14px;
            margin-top: 40px;
        }}

        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #eee;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }}

        .tag {{
            display: inline-block;
            padding: 2px 8px;
            background: #ecf5ff;
            color: #409eff;
            border-radius: 3px;
            font-size: 12px;
            margin: 2px;
        }}

        @media print {{
            .container {{ max-width: 100%; }}
            .section {{ page-break-inside: avoid; }}
            .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            body {{ background: white; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 报告头部 -->
        <div class="header">
            <h1>🔒 安全评估报告</h1>
            <div class="subtitle">目标：{target}</div>
            <div class="meta">
                <div>生成时间：{timestamp}</div>
                <div>评估工具：HexStrike AI (Nmap + Nuclei)</div>
            </div>
        </div>

        <!-- 统计摘要 -->
        <div class="summary">
            <div class="summary-card risk-critical">
                <div class="number">{stats['vulnerabilities']['critical']}</div>
                <div class="label">严重漏洞</div>
            </div>
            <div class="summary-card risk-high">
                <div class="number">{stats['vulnerabilities']['high']}</div>
                <div class="label">高危漏洞</div>
            </div>
            <div class="summary-card risk-medium">
                <div class="number">{stats['vulnerabilities']['medium']}</div>
                <div class="label">中危漏洞</div>
            </div>
            <div class="summary-card risk-low">
                <div class="number">{stats['vulnerabilities']['low']}</div>
                <div class="label">低危漏洞</div>
            </div>
            <div class="summary-card">
                <div class="number">{stats['ports']['open']}</div>
                <div class="label">开放端口</div>
            </div>
        </div>

        {self._generate_vulnerabilities_section(nuclei_results)}

        {self._generate_ports_section(nmap_results)}

        {self._generate_recommendations_section(nmap_results, nuclei_results)}

        <!-- 报告尾部 -->
        <div class="footer">
            <p>本报告由 HexStrike AI 自动生成</p>
            <p>建议：定期进行安全评估，及时修复发现的漏洞</p>
            <p>生成时间：{timestamp}</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _extract_stats(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict]) -> Dict:
        """提取统计数据"""
        stats = {
            'vulnerabilities': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0, 'total': 0},
            'ports': {'open': 0, 'closed': 0, 'filtered': 0, 'total': 0}
        }

        # 提取漏洞统计
        if nuclei_results and nuclei_results.get('success'):
            try:
                stdout = nuclei_results.get('stdout', '')
                if stdout:
                    # 尝试解析 JSON 格式的 Nuclei 输出
                    lines = stdout.strip().split('\n')
                    for line in lines:
                        try:
                            vuln = json.loads(line)
                            severity = vuln.get('info', {}).get('severity', 'info').lower()
                            if severity in stats['vulnerabilities']:
                                stats['vulnerabilities'][severity] += 1
                                stats['vulnerabilities']['total'] += 1
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                pass

        # 提取端口统计
        if nmap_results and nmap_results.get('success'):
            try:
                stdout = nmap_results.get('stdout', '')
                if stdout:
                    # 简单的端口统计（从文本输出中提取）
                    import re
                    port_matches = re.findall(r'(\d+)/tcp\s+open', stdout)
                    stats['ports']['open'] = len(port_matches)
                    stats['ports']['total'] = len(port_matches)
            except Exception as e:
                pass

        return stats

    def _generate_vulnerabilities_section(self, nuclei_results: Optional[Dict]) -> str:
        """生成漏洞列表部分"""
        if not nuclei_results or not nuclei_results.get('success'):
            return ''

        try:
            stdout = nuclei_results.get('stdout', '')
            if not stdout:
                return ''

            # 解析漏洞
            vulnerabilities = []
            lines = stdout.strip().split('\n')
            for line in lines:
                try:
                    vuln = json.loads(line)
                    vulnerabilities.append(vuln)
                except json.JSONDecodeError:
                    pass

            if not vulnerabilities:
                return '<div class="section"><h2 class="section-title">🎉 未发现漏洞</h2><p>扫描完成，未发现已知漏洞。</p></div>'

            # 按严重性分组
            by_severity = {'critical': [], 'high': [], 'medium': [], 'low': [], 'info': []}
            for vuln in vulnerabilities:
                severity = vuln.get('info', {}).get('severity', 'info').lower()
                if severity not in by_severity:
                    severity = 'info'
                by_severity[severity].append(vuln)

            # 生成 HTML
            html = '<div class="section"><h2 class="section-title">🔍 漏洞扫描结果</h2>'

            for severity in ['critical', 'high', 'medium', 'low', 'info']:
                vulns = by_severity.get(severity, [])
                if not vulns:
                    continue

                severity_labels = {
                    'critical': '严重',
                    'high': '高危',
                    'medium': '中危',
                    'low': '低危',
                    'info': '信息'
                }

                html += f'<h3>{severity_labels[severity].upper()} ({len(vulns)})</h3>'
                html += '<ul class="vulnerability-list">'

                for vuln in vulns[:20]:  # 最多显示 20 个
                    info = vuln.get('info', {})
                    name = info.get('name', 'Unknown')
                    cve_ids = info.get('tags', [])
                    description = info.get('description', '')[:200]

                    html += f'''
                    <li class="vulnerability-item {severity}">
                        <div class="title">
                            <span class="severity severity-{severity}">{severity_labels[severity]}</span>
                            {name}
                        </div>
                        <div style="margin-top: 10px;">
                            {' '.join([f'<span class="tag">{tag}</span>' for tag in cve_ids[:5]])}
                        </div>
                        {f'<div style="margin-top: 8px; color: #666;">{description}...</div>' if description else ''}
                    </li>'''

                if len(vulns) > 20:
                    html += f'<li style="padding: 10px; color: #999;">还有 {len(vulns) - 20} 个{severity_labels[severity]}漏洞未显示</li>'

                html += '</ul>'

            html += '</div>'
            return html

        except Exception as e:
            return f'<div class="section"><h2 class="section-title">漏洞扫描结果</h2><p>解析失败: {str(e)}</p></div>'

    def _generate_ports_section(self, nmap_results: Optional[Dict]) -> str:
        """生成端口列表部分"""
        if not nmap_results or not nmap_results.get('success'):
            return ''

        try:
            stdout = nmap_results.get('stdout', '')
            if not stdout:
                return ''

            # 解析端口信息
            import re
            port_pattern = re.compile(r'(\d+)/tcp\s+open\s+(\S+)(?:\s+(.+))?')

            ports = []
            for match in port_pattern.finditer(stdout):
                port = match.group(1)
                service = match.group(2)
                version = match.group(3) or ''

                ports.append({
                    'port': port,
                    'service': service,
                    'version': version
                })

            if not ports:
                return '<div class="section"><h2 class="section-title">端口扫描结果</h2><p>未发现开放端口。</p></div>'

            html = '<div class="section"><h2 class="section-title">🔌 端口扫描结果</h2>'
            html += '<div class="port-list">'

            for port_info in ports:
                port = port_info['port']
                service = port_info['service']
                version = port_info['version']

                # 风险评估
                risk = self._assess_port_risk(port, service)

                html += f'''
                <div class="port-item open">
                    <div class="port-number">端口 {port}/tcp</div>
                    <div class="service">
                        服务：{service}
                        {f'<span class="risk-badge risk-{risk["level"]}">{risk["label"]}</span>' if risk else ''}
                    </div>
                    {f'<div style="font-size: 12px; color: #999; margin-top: 5px;">{version}</div>' if version else ''}
                </div>'''

            html += '</div></div>'
            return html

        except Exception as e:
            return f'<div class="section"><h2 class="section-title">端口扫描结果</h2><p>解析失败: {str(e)}</p></div>'

    def _generate_recommendations_section(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict]) -> str:
        """生成修复建议部分"""
        recommendations = []

        # 基于 Nmap 结果的建议
        if nmap_results and nmap_results.get('success'):
            stdout = nmap_results.get('stdout', '')

            if 'ssh' in stdout.lower():
                recommendations.append({
                    'title': '🔐 SSH 安全加固',
                    'items': [
                        '禁用密码登录，只允许密钥认证',
                        '修改默认端口（22）',
                        '配置 fail2ban 防暴力破解',
                        '限制访问来源 IP（防火墙）'
                    ]
                })

            if 'elasticsearch' in stdout.lower() or ':9200' in stdout:
                recommendations.append({
                    'title': '🔍 Elasticsearch 安全加固',
                    'items': [
                        '启用 X-Pack 安全认证',
                        '配置访问控制列表（ACL）',
                        '禁用或限制 HTTP 接口',
                        '升级到最新版本'
                    ]
                })

        # 基于 Nuclei 结果的建议
        if nuclei_results and nuclei_results.get('success'):
            try:
                stdout = nuclei_results.get('stdout', '')
                if 'critical' in stdout.lower() or 'high' in stdout.lower():
                    recommendations.append({
                        'title': '🚨 漏洞修复优先级',
                        'items': [
                            '立即修复严重和高危漏洞',
                            '隔离受影响的系统',
                            '检查是否存在已遭受攻击的迹象',
                            '应用最新的安全补丁'
                        ]
                    })
            except:
                pass

        if not recommendations:
            return ''

        html = '<div class="section"><h2 class="section-title">💡 安全建议</h2>'

        for rec in recommendations:
            html += f'''
            <div class="recommendations">
                <h3 style="margin-bottom: 10px;">{rec['title']}</h3>
                <ul>
                    {''.join([f'<li>{item}</li>' for item in rec['items']])}
                </ul>
            </div>
            '''

        html += '</div>'
        return html

    def _assess_port_risk(self, port: str, service: str) -> Optional[Dict]:
        """评估端口风险"""
        port_num = int(port) if port.isdigit() else 0
        service_lower = service.lower()

        critical_ports = [22, 23, 135, 139, 445, 3389]
        critical_services = ['telnet', 'ftp', 'rsh', 'rlogin']

        if port_num in critical_ports or service_lower in critical_services:
            return {'level': 'critical', 'label': '严重'}
        elif port_num < 1024:
            return {'level': 'medium', 'label': '中危'}
        else:
            return {'level': 'low', 'label': '低危'}