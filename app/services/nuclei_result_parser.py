"""
Nuclei 扫描结果解析和格式化工具

功能：
1. 解析 Nuclei JSON 输出
2. 提取漏洞信息（严重性、CVE ID、描述等）
3. 格式化为可读的 Markdown 输出
4. 生成统计摘要和修复建议
"""

import json
import re
from typing import Dict, List, Any, Optional
from collections import defaultdict


class NucleiResultParser:
    """Nuclei 扫描结果解析器"""

    # 严重性等级映射
    SEVERITY_LEVELS = {
        'critical': {'emoji': '🔴', 'label': '严重', 'priority': 5},
        'high': {'emoji': '🟠', 'label': '高危', 'priority': 4},
        'medium': {'emoji': '🟡', 'label': '中危', 'priority': 3},
        'low': {'emoji': '🟢', 'label': '低危', 'priority': 2},
        'info': {'emoji': '🔵', 'label': '信息', 'priority': 1}
    }

    def __init__(self):
        self.vulnerabilities = []
        self.stats = defaultdict(int)
        self.by_severity = defaultdict(list)

    def parse(self, stdout: str, stderr: str = '') -> Dict[str, Any]:
        """
        解析 Nuclei 输出

        Args:
            stdout: 标准输出（JSON 格式）
            stderr: 标准错误（日志信息）

        Returns:
            解析后的结果字典
        """
        self.vulnerabilities = []
        self.stats = defaultdict(int)
        self.by_severity = defaultdict(list)

        # 尝试从 stdout 解析 JSON
        if stdout and stdout.strip():
            self._parse_json_output(stdout)

        # 尝试从 stderr 解析（如果是非 JSON 格式）
        if not self.vulnerabilities and stderr:
            self._parse_text_output(stderr)

        # 生成统计信息
        self._calculate_stats()

        return {
            'vulnerabilities': self.vulnerabilities,
            'stats': dict(self.stats),
            'by_severity': dict(self.by_severity),
            'total_count': len(self.vulnerabilities)
        }

    def _parse_json_output(self, output: str) -> None:
        """解析 JSON 格式输出"""
        try:
            # Nuclei JSON 输出是每行一个 JSON 对象
            lines = output.strip().split('\n')
            for line in lines:
                if not line.strip():
                    continue
                try:
                    vuln = json.loads(line)
                    parsed_vuln = self._extract_vulnerability_info(vuln)
                    if parsed_vuln:
                        self.vulnerabilities.append(parsed_vuln)
                        severity = parsed_vuln.get('severity', 'info').lower()
                        self.by_severity[severity].append(parsed_vuln)
                except json.JSONDecodeError:
                    # 可能是多个 JSON 对象连在一起
                    continue
        except Exception as e:
            print(f"JSON 解析错误: {str(e)}")

    def _parse_text_output(self, output: str) -> None:
        """解析文本格式输出（备用方案）"""
        # 移除 ANSI 颜色代码
        clean_output = self._remove_ansi_codes(output)

        # 查找漏洞相关的行
        lines = clean_output.split('\n')
        for line in lines:
            # 尝试提取漏洞信息
            if any(sev in line.lower() for sev in ['critical', 'high', 'medium', 'low']):
                # 这里是简化的文本解析，实际可能需要更复杂的正则
                self.vulnerabilities.append({
                    'severity': self._extract_severity(line),
                    'name': 'Unknown',
                    'description': line.strip(),
                    'url': 'N/A',
                    'tags': []
                })

    def _extract_vulnerability_info(self, vuln: Dict) -> Optional[Dict]:
        """从 Nuclei JSON 结果提取关键信息"""
        try:
            info = vuln.get('info', {})

            # 提取 CVE ID
            tags = info.get('tags', [])
            cve_ids = [tag for tag in tags if tag.startswith('CVE-') or tag.startswith('cve-')]

            # 提取严重性
            severity = vuln.get('severity', 'info').lower()
            if severity not in self.SEVERITY_LEVELS:
                severity = 'info'

            # 提取匹配位置
            matched_at = vuln.get('matched-at', 'N/A')

            return {
                'template_id': vuln.get('template-id', 'unknown'),
                'name': info.get('name', 'Unknown'),
                'severity': severity,
                'description': info.get('description', ''),
                'url': matched_at,
                'tags': tags,
                'cve_ids': cve_ids,
                'cvss': info.get('classification', {}).get('cvss-metrics', ''),
                'references': info.get('reference', [])
            }
        except Exception as e:
            print(f"提取漏洞信息错误: {str(e)}")
            return None

    def _extract_severity(self, line: str) -> str:
        """从文本行提取严重性"""
        for sev in ['critical', 'high', 'medium', 'low', 'info']:
            if sev in line.lower():
                return sev
        return 'info'

    def _remove_ansi_codes(self, text: str) -> str:
        """移除 ANSI 颜色代码"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _calculate_stats(self) -> None:
        """计算统计信息"""
        for vuln in self.vulnerabilities:
            severity = vuln.get('severity', 'info').lower()
            self.stats[severity] += 1
            self.stats['total'] += 1

    def format_markdown(self, parsed_result: Dict[str, Any]) -> str:
        """
        格式化为可读的 Markdown

        Args:
            parsed_result: parse() 方法返回的解析结果

        Returns:
            Markdown 格式的字符串
        """
        md_parts = []

        # 标题
        md_parts.append("# 🔍 Nuclei 漏洞扫描报告\n")

        # 统计摘要
        md_parts.append("## 📊 扫描摘要\n")
        md_parts.append(self._format_summary(parsed_result))
        md_parts.append("\n")

        # 按严重性分组显示
        md_parts.append("## 🎯 漏洞详情\n")

        vulnerabilities = parsed_result.get('vulnerabilities', [])
        by_severity = parsed_result.get('by_severity', {})

        if not vulnerabilities:
            md_parts.append("✅ **未发现漏洞**\n\n")
            md_parts.append("扫描完成，未发现安全漏洞。但这不代表系统绝对安全，建议定期进行深度扫描。\n")
        else:
            # 按严重性排序显示
            for severity in ['critical', 'high', 'medium', 'low', 'info']:
                if severity in by_severity and by_severity[severity]:
                    md_parts.append(self._format_severity_section(severity, by_severity[severity]))
                    md_parts.append("\n")

        # 修复建议
        md_parts.append("## 💡 修复建议\n")
        md_parts.append(self._format_recommendations(parsed_result))
        md_parts.append("\n")

        return ''.join(md_parts)

    def _format_summary(self, result: Dict) -> str:
        """格式化统计摘要"""
        stats = result.get('stats', {})
        total = stats.get('total', 0)

        lines = []
        lines.append(f"- **扫描时间**: {self._get_timestamp()}")
        lines.append(f"- **发现漏洞**: {total} 个\n")

        if total == 0:
            return '\n'.join(lines)

        lines.append("**漏洞分布**:\n")

        for severity in ['critical', 'high', 'medium', 'low', 'info']:
            if severity in stats:
                level_info = self.SEVERITY_LEVELS[severity]
                count = stats[severity]
                emoji = level_info['emoji']
                label = level_info['label']
                lines.append(f"- {emoji} **{label}**: {count} 个")

        return '\n'.join(lines)

    def _format_severity_section(self, severity: str, vulns: List[Dict]) -> str:
        """格式化单个严重性级别的漏洞"""
        level_info = self.SEVERITY_LEVELS[severity]
        emoji = level_info['emoji']
        label = level_info['label']

        lines = []
        lines.append(f"### {emoji} {label}漏洞 ({len(vulns)} 个)\n")

        for i, vuln in enumerate(vulns, 1):
            lines.append(f"#### {i}. {vuln.get('name', 'Unknown')}\n")

            # CVE ID
            if vuln.get('cve_ids'):
                cve_list = ', '.join(vuln['cve_ids'])
                lines.append(f"- **CVE**: `{cve_list}`")

            # 受影响 URL
            lines.append(f"- **受影响地址**: `{vuln.get('url', 'N/A')}`")

            # 描述
            if vuln.get('description'):
                lines.append(f"- **描述**: {vuln['description']}")

            # CVSS 评分
            if vuln.get('cvss'):
                lines.append(f"- **CVSS**: {vuln['cvss']}")

            # 标签
            if vuln.get('tags'):
                tags_str = ' '.join([f"`{tag}`" for tag in vuln['tags'][:5]])
                lines.append(f"- **标签**: {tags_str}")

            # 参考链接
            if vuln.get('references'):
                ref_links = '\n  '.join([f"- [{ref}]({ref})" for ref in vuln['references'][:3]])
                lines.append(f"- **参考**:\n  {ref_links}")

            lines.append("")

        return '\n'.join(lines)

    def _format_recommendations(self, result: Dict) -> str:
        """生成修复建议"""
        stats = result.get('stats', {})

        lines = []

        # 优先级建议
        if stats.get('critical', 0) > 0:
            lines.append("### 🚨 紧急处理")
            lines.append(f"发现 {stats['critical']} 个严重漏洞，建议立即处理：")
            lines.append("1. 隔离受影响的系统")
            lines.append("2. 应用最新的安全补丁")
            lines.append("3. 检查是否存在已遭受攻击的迹象")
            lines.append("")

        if stats.get('high', 0) > 0:
            lines.append("### ⚠️ 高优先级")
            lines.append(f"发现 {stats['high']} 个高危漏洞，建议尽快修复：")
            lines.append("1. 评估业务影响")
            lines.append("2. 制定修复计划")
            lines.append("3. 在维护窗口期内更新")
            lines.append("")

        # 一般建议
        lines.append("### 📋 通用建议")
        lines.append("1. **定期扫描**: 建议每月至少进行一次完整扫描")
        lines.append("2. **持续监控**: 配置自动化监控和告警")
        lines.append("3. **补丁管理**: 建立漏洞补丁管理流程")
        lines.append("4. **安全加固**: 遵循安全基线和最佳实践")
        lines.append("5. **访问控制**: 限制不必要的网络暴露")

        return '\n'.join(lines)

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def format_nuclei_result(stdout: str, stderr: str = '') -> str:
    """
    便捷函数：格式化 Nuclei 扫描结果

    Args:
        stdout: Nuclei 标准输出
        stderr: Nuclei 标准错误

    Returns:
        格式化后的 Markdown 字符串
    """
    parser = NucleiResultParser()
    parsed = parser.parse(stdout, stderr)
    return parser.format_markdown(parsed)


# 测试代码
if __name__ == '__main__':
    # 示例 JSON 输出
    sample_json = '''
    {"template-id":"cve-2021-22204","info":{"name":"GitLab SSRF","tags":["cve","cve-2021","ssrf","oast"],"severity":"critical"},"severity":"critical","matched-at":"https://example.com"}
    {"template-id":"exposed-panel","info":{"name":"Admin Panel","tags":["exposure","panel"],"severity":"high"},"severity":"high","matched-at":"https://example.com/admin"}
    '''

    parser = NucleiResultParser()
    result = parser.parse(sample_json)
    print(parser.format_markdown(result))