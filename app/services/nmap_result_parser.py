"""
Nmap 扫描结果解析和格式化工具

功能：
1. 解析 Nmap XML/文本输出
2. 提取端口信息、服务版本、操作系统指纹等
3. 格式化为可读的 Markdown 输出
4. 生成安全评估和建议
"""

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from collections import defaultdict


class NmapResultParser:
    """Nmap 扫描结果解析器"""

    # 端口状态映射
    PORT_STATE_EMOJI = {
        'open': '🟢',
        'closed': '⚫',
        'filtered': '🔵',
        'unfiltered': '⚪',
        'open|filtered': '🟡',
        'closed|filtered': '🟠',
        'open|closed': '🔴'
    }

    # 风险评分映射
    RISK_LEVELS = {
        'critical': {'emoji': '🔴', 'label': '严重', 'min_score': 9},
        'high': {'emoji': '🟠', 'label': '高危', 'min_score': 7},
        'medium': {'emoji': '🟡', 'label': '中危', 'min_score': 4},
        'low': {'emoji': '🟢', 'label': '低危', 'min_score': 1},
        'info': {'emoji': '🔵', 'label': '信息', 'min_score': 0}
    }

    def __init__(self):
        self.target = None
        self.ports = []
        self.os_guesses = []
        self.hostnames = []
        self.stats = defaultdict(int)

    def parse(self, stdout: str, stderr: str = '') -> Dict[str, Any]:
        """
        解析 Nmap 输出

        Args:
            stdout: 标准输出
            stderr: 标准错误（日志信息）

        Returns:
            解析后的结果字典
        """
        self.ports = []
        self.os_guesses = []
        self.hostnames = []
        self.stats = defaultdict(int)

        # 尝试解析 XML 格式
        if stdout and '<?xml' in stdout:
            self._parse_xml_output(stdout)
        # 尝试解析 JSON 格式
        elif stdout and stdout.strip().startswith('{'):
            self._parse_json_output(stdout)
        # 解析文本格式（备用方案）
        elif stdout:
            self._parse_text_output(stdout)

        # 生成统计信息
        self._calculate_stats()

        return {
            'target': self.target,
            'ports': self.ports,
            'os_guesses': self.os_guesses,
            'hostnames': self.hostnames,
            'stats': dict(self.stats),
            'total_ports': len(self.ports)
        }

    def _parse_xml_output(self, output: str) -> None:
        """解析 XML 格式输出"""
        try:
            root = ET.fromstring(output)

            # 获取目标地址
            host = root.find('.//host')
            if host is not None:
                address_elem = host.find('.//address[@addrtype="ipv4"]')
                if address_elem is not None:
                    self.target = address_elem.get('addr')

                # 获取主机名
                hostnames_elem = host.find('.//hostnames')
                if hostnames_elem is not None:
                    for hostname in hostnames_elem.findall('hostname'):
                        self.hostnames.append({
                            'name': hostname.get('name'),
                            'type': hostname.get('type')
                        })

                # 获取端口信息
                ports_elem = host.find('.//ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        port_id = port.get('portid')
                        protocol = port.get('protocol')
                        state_elem = port.find('state')
                        state = state_elem.get('state') if state_elem is not None else 'unknown'

                        service_elem = port.find('service')
                        service_info = {}
                        if service_elem is not None:
                            service_info = {
                                'name': service_elem.get('name', ''),
                                'product': service_elem.get('product', ''),
                                'version': service_info.get('version', ''),
                                'extrainfo': service_elem.get('extrainfo', ''),
                                'fingerprint': service_elem.get('fingerprint', '')
                            }

                        self.ports.append({
                            'port': port_id,
                            'protocol': protocol,
                            'state': state,
                            'service': service_info
                        })

                # 获取操作系统猜测
                os_elem = host.find('.//os')
                if os_elem is not None:
                    for osmatch in os_elem.findall('osmatch'):
                        self.os_guesses.append({
                            'name': osmatch.get('name'),
                            'accuracy': osmatch.get('accuracy')
                        })

        except ET.ParseError as e:
            print(f"XML 解析错误: {str(e)}")
            # 回退到文本解析
            self._parse_text_output(output)

    def _parse_json_output(self, output: str) -> None:
        """解析 JSON 格式输出"""
        try:
            import json
            data = json.loads(output)

            # 提取目标
            if isinstance(data, dict):
                self.target = data.get('target') or data.get('host')

                # 提取端口
                ports_data = data.get('ports', [])
                for port_info in ports_data:
                    self.ports.append({
                        'port': port_info.get('port'),
                        'protocol': port_info.get('protocol', 'tcp'),
                        'state': port_info.get('state', 'unknown'),
                        'service': {
                            'name': port_info.get('service', ''),
                            'product': port_info.get('product', ''),
                            'version': port_info.get('version', ''),
                            'extrainfo': port_info.get('extrainfo', '')
                        }
                    })

                # 提取操作系统
                os_data = data.get('os', [])
                for os_info in os_data:
                    self.os_guesses.append({
                        'name': os_info.get('name'),
                        'accuracy': os_info.get('accuracy')
                    })

        except json.JSONDecodeError:
            # 回退到文本解析
            self._parse_text_output(output)

    def _parse_text_output(self, output: str) -> None:
        """解析文本格式输出（备用方案）"""
        lines = output.split('\n')

        # 提取目标
        for line in lines:
            if 'Starting Nmap' in line or 'scan initiated' in line:
                # 尝试提取 IP
                ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                if ip_match:
                    self.target = ip_match.group(1)
                break

        # 提取端口信息
        port_pattern = re.compile(r'(\d+)/(tcp|udp)\s+(\S+)\s+(\S+)(?:\s+(.+))?')

        for line in lines:
            match = port_pattern.match(line.strip())
            if match:
                port_id, protocol, state, service, extra = match.groups()

                service_info = {'name': service}
                if extra:
                    # 尝试解析额外信息
                    if 'product' in extra.lower():
                        parts = extra.split(maxsplit=1)
                        if len(parts) > 1:
                            service_info['product'] = parts[1]

                self.ports.append({
                    'port': port_id,
                    'protocol': protocol,
                    'state': state,
                    'service': service_info
                })

    def _calculate_stats(self) -> None:
        """计算统计信息"""
        for port in self.ports:
            state = port.get('state', 'unknown')
            self.stats[state] += 1
            self.stats['total'] += 1

        # 统计开放端口
        self.stats['open_ports'] = len([p for p in self.ports if p.get('state') == 'open'])

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
        md_parts.append("# 🔍 Nmap 端口扫描报告\n")

        # 扫描摘要
        md_parts.append("## 📊 扫描摘要\n")
        md_parts.append(self._format_summary(parsed_result))
        md_parts.append("\n")

        # 目标信息
        md_parts.append("## 🎯 扫描目标\n")
        md_parts.append(self._format_target(parsed_result))
        md_parts.append("\n")

        # 端口详情
        md_parts.append("## 🔌 端口详情\n")
        if self.ports:
            md_parts.append(self._format_ports(parsed_result))
            md_parts.append("\n")
        else:
            md_parts.append("未发现开放端口\n")

        # 操作系统识别
        if self.os_guesses:
            md_parts.append("## 💻 操作系统识别\n")
            md_parts.append(self._format_os(parsed_result))
            md_parts.append("\n")

        # 安全评估
        md_parts.append("## ⚠️ 安全评估\n")
        md_parts.append(self._format_security_assessment(parsed_result))
        md_parts.append("\n")

        # 优化建议
        md_parts.append("## 💡 优化建议\n")
        md_parts.append(self._format_recommendations(parsed_result))
        md_parts.append("\n")

        return ''.join(md_parts)

    def _format_summary(self, result: Dict) -> str:
        """格式化扫描摘要"""
        stats = result.get('stats', {})
        open_ports = stats.get('open_ports', 0)

        lines = []
        lines.append(f"- **扫描目标**: `{result.get('target', 'Unknown')}`")
        lines.append(f"- **发现端口**: {stats.get('total', 0)} 个")
        lines.append(f"- **开放端口**: {open_ports} 个\n")

        if open_ports > 0:
            lines.append("**端口状态分布**:\n")
            for state in ['open', 'closed', 'filtered']:
                if state in stats:
                    emoji = self.PORT_STATE_EMOJI.get(state, '⚪')
                    label = state.capitalize()
                    count = stats[state]
                    lines.append(f"- {emoji} **{label}**: {count} 个")

        return '\n'.join(lines)

    def _format_target(self, result: Dict) -> str:
        """格式化目标信息"""
        lines = []
        lines.append(f"**IP 地址**: `{result.get('target', 'Unknown')}`\n")

        hostnames = result.get('hostnames', [])
        if hostnames:
            lines.append("**主机名**:\n")
            for hostname in hostnames:
                lines.append(f"- `{hostname.get('name')}` ({hostname.get('type')})")
            lines.append("")

        return '\n'.join(lines)

    def _format_ports(self, result: Dict) -> str:
        """格式化端口信息"""
        ports = result.get('ports', [])

        # 按状态分组
        by_state = defaultdict(list)
        for port in ports:
            state = port.get('state', 'unknown')
            by_state[state].append(port)

        lines = []

        # 显示开放端口（最重要）
        if 'open' in by_state:
            lines.append("### 🟢 开放端口\n")
            for port in sorted(by_state['open'], key=lambda x: int(x.get('port', 0))):
                lines.append(self._format_port_detail(port))
                lines.append("")

        # 显示其他状态
        for state in ['open|filtered', 'filtered', 'closed']:
            if state in by_state and by_state[state]:
                emoji = self.PORT_STATE_EMOJI.get(state, '⚪')
                label = state.capitalize()
                lines.append(f"### {emoji} {label} 端口\n")

                for port in sorted(by_state[state], key=lambda x: int(x.get('port', 0))):
                    lines.append(f"**端口 {port.get('port')}/{port.get('protocol')}**")

                lines.append("")

        return '\n'.join(lines)

    def _format_port_detail(self, port: Dict) -> str:
        """格式化单个端口的详细信息"""
        port_num = port.get('port')
        protocol = port.get('protocol', 'tcp')
        service = port.get('service', {})

        lines = []
        lines.append(f"#### 端口 {port_num}/{protocol}\n")

        # 服务名称
        service_name = service.get('name', 'unknown')
        lines.append(f"- **服务**: {service_name}")

        # 产品和版本
        if service.get('product'):
            product = service['product']
            if service.get('version'):
                product += f" {service['version']}"
            lines.append(f"- **版本**: `{product}`")

        # 额外信息
        if service.get('extrainfo'):
            lines.append(f"- **额外信息**: {service['extrainfo']}")

        # 风险评估
        risk = self._assess_port_risk(port)
        if risk:
            lines.append(f"- **风险等级**: {risk}")

        return '\n'.join(lines)

    def _assess_port_risk(self, port: Dict) -> str:
        """评估端口风险"""
        port_num = int(port.get('port', 0))
        service = port.get('service', {})
        service_name = service.get('name', '').lower()

        # 高危端口和服务
        critical_ports = [22, 23, 135, 139, 445, 3389, 5900]
        critical_services = ['telnet', 'ftp', 'rsh', 'rlogin', 'smtp']

        # 中危端口
        medium_ports = [21, 25, 53, 110, 143, 3306, 5432, 6379, 27017]

        if port_num in critical_ports or service_name in critical_services:
            return "🔴 **严重** - 未加密的敏感服务"
        elif port_num in medium_ports:
            return "🟠 **高危** - 可能存在已知漏洞"
        elif port_num < 1024:
            return "🟡 **中危** - 系统端口，需关注"
        else:
            return "🟢 **低危** - 应用端口"

    def _format_os(self, result: Dict) -> str:
        """格式化操作系统信息"""
        os_guesses = result.get('os_guesses', [])

        lines = []
        lines.append("**猜测结果**:\n")

        for i, os_guess in enumerate(os_guesses[:3], 1):
            name = os_guess.get('name', 'Unknown')
            accuracy = os_guess.get('accuracy', '0')
            lines.append(f"{i}. **{name}** (准确度: {accuracy}%)")

        if len(os_guesses) > 3:
            lines.append(f"\n> 还有 {len(os_guesses) - 3} 个猜测未显示")

        return '\n'.join(lines)

    def _format_security_assessment(self, result: Dict) -> str:
        """格式化安全评估"""
        ports = result.get('ports', [])
        open_ports = [p for p in ports if p.get('state') == 'open']

        lines = []

        # 检查高危服务
        high_risk_services = []
        medium_risk_services = []

        for port in open_ports:
            port_num = int(port.get('port', 0))
            service = port.get('service', {})
            service_name = service.get('name', '').lower()

            # 识别高风险服务
            if port_num == 22 and 'ssh' in service_name:
                high_risk_services.append({
                    'port': port_num,
                    'service': 'SSH',
                    'issue': '可能存在暴力破解风险'
                })
            elif port_num in [23, 21] or service_name in ['telnet', 'ftp']:
                high_risk_services.append({
                    'port': port_num,
                    'service': service_name.upper(),
                    'issue': '明文传输协议，存在窃听风险'
                })
            elif port_num == 3389:
                high_risk_services.append({
                    'port': port_num,
                    'service': 'RDP',
                    'issue': '远程桌面，可能存在蓝屏漏洞'
                })
            elif port_num == 9200 or 'elasticsearch' in service_name:
                high_risk_services.append({
                    'port': port_num,
                    'service': 'Elasticsearch',
                    'issue': '可能存在未授权访问漏洞'
                })

        if high_risk_services:
            lines.append("### 🚨 高危服务\n")
            for service in high_risk_services:
                lines.append(f"- **端口 {service['port']}** ({service['service']}): {service['issue']}")
            lines.append("")

        # 端口暴露评估
        exposed_count = len(open_ports)
        if exposed_count > 10:
            lines.append(f"### ⚠️ 攻击面过大\n")
            lines.append(f"- 发现 {exposed_count} 个开放端口，攻击面过大")
            lines.append(f"- 建议：关闭不必要的端口，使用防火墙限制访问\n")
        elif exposed_count > 5:
            lines.append(f"### ⚠️ 端口暴露较多\n")
            lines.append(f"- 发现 {exposed_count} 个开放端口")
            lines.append(f"- 建议：审查每个端口的必要性\n")

        return '\n'.join(lines) if lines else "未发现明显的安全问题\n"

    def _format_recommendations(self, result: Dict) -> str:
        """生成优化建议"""
        ports = result.get('ports', [])
        open_ports = [p for p in ports if p.get('state') == 'open']

        lines = []

        # 基于端口生成建议
        port_nums = [int(p.get('port', 0)) for p in open_ports]

        if 22 in port_nums:
            lines.append("### 🔐 SSH 安全加固")
            lines.append("1. 禁用密码登录，只允许密钥认证")
            lines.append("2. 修改默认端口（22）")
            lines.append("3. 配置 fail2ban 防暴力破解")
            lines.append("4. 限制访问来源 IP（防火墙）")
            lines.append("")

        if 9200 in port_nums or any('elasticsearch' in p.get('service', {}).get('name', '').lower() for p in open_ports):
            lines.append("### 🔍 Elasticsearch 安全加固")
            lines.append("1. 启用 X-Pack 安全认证")
            lines.append("2. 配置访问控制列表（ACL）")
            lines.append("3. 禁用或限制 HTTP 接口")
            lines.append("4. 升级到最新版本（当前版本过旧）")
            lines.append("")

        if any(p in port_nums for p in [80, 443, 8080, 8443]):
            lines.append("### 🌐 Web 服务加固")
            lines.append("1. 配置 HTTPS（使用 Let's Encrypt 免费证书）")
            lines.append("2. 启用安全头部（HSTS, X-Frame-Options 等）")
            lines.append("3. 配置 WAF 防护")
            lines.append("4. 定期更新 Web 服务器软件")
            lines.append("")

        if 3306 in port_nums or 5432 in port_nums or 27017 in port_nums:
            lines.append("### 💾 数据库安全加固")
            lines.append("1. 不要暴露在公网（绑定 127.0.0.1）")
            lines.append("2. 启用强密码认证")
            lines.append("3. 限制访问来源 IP")
            lines.append("4. 定期备份数据")
            lines.append("")

        # 通用建议
        lines.append("### 📋 通用建议")
        lines.append("1. **最小化暴露原则**: 只开放必要的端口")
        lines.append("2. **防火墙配置**: 使用 iptables/UFW/firewalld 限制访问")
        lines.append("3. **定期扫描**: 每月进行端口扫描和漏洞扫描")
        lines.append("4. **入侵检测**: 配置 IDS/IPS 监控异常连接")
        lines.append("5. **访问控制**: 使用 VPN 或堡垒机管理服务器")

        return '\n'.join(lines)


def format_nmap_result(stdout: str, stderr: str = '') -> str:
    """
    便捷函数：格式化 Nmap 扫描结果

    Args:
        stdout: Nmap 标准输出
        stderr: Nmap 标准错误

    Returns:
        格式化后的 Markdown 字符串
    """
    parser = NmapResultParser()
    parsed = parser.parse(stdout, stderr)
    return parser.format_markdown(parsed)


# 测试代码
if __name__ == '__main__':
    # 示例 XML 输出
    sample_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="nmap">
  <host>
    <address addr="101.37.29.229" addrtype="ipv4"/>
    <hostnames>
      <hostname name="example.com" type="PTR"/>
    </hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="7.4"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="nginx"/>
      </port>
      <port protocol="tcp" portid="9200">
        <state state="open"/>
        <service name="unknown" product="Elasticsearch" version="1.1.1"/>
      </port>
    </ports>
    <os>
      <osmatch name="Linux 3.10" accuracy="98"/>
    </os>
  </host>
</nmaprun>'''

    parser = NmapResultParser()
    result = parser.parse(sample_xml)
    print(parser.format_markdown(result))