"""
消息格式化工具
用于将智能体回复格式化为钉钉Markdown格式
"""
import re
from typing import List


def format_to_dingtalk_markdown(text: str) -> str:
    """
    将文本格式化为钉钉Markdown格式
    
    钉钉Markdown支持的语法：
    - 标题: # ## ###
    - 加粗: **text**
    - 斜体: *text*
    - 链接: [text](url)
    - 代码: `code`
    - 列表: - item 或 1. item
    - 引用: > text
    - 分割线: ---
    
    Args:
        text: 原始文本
        
    Returns:
        str: 格式化后的Markdown文本
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    formatted_lines = []
    in_list = False
    in_code_block = False
    
    for line in lines:
        line = line.rstrip()
        
        # 跳过空行（但保留用于分隔）
        if not line.strip():
            if in_list:
                in_list = False
            formatted_lines.append('')
            continue
        
        # 处理代码块
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            formatted_lines.append(line)
            continue
        
        if in_code_block:
            formatted_lines.append(line)
            continue
        
        # 处理标题（如果已经是markdown格式，保持不变）
        if line.startswith('#'):
            if in_list:
                in_list = False
            formatted_lines.append(line)
            continue
        
        # 处理列表项
        # 匹配 "1. " 或 "- " 或 "   - " 等格式
        list_match = re.match(r'^(\s*)([-*]|\d+\.)\s+(.+)$', line)
        if list_match:
            indent = list_match.group(1)
            marker = list_match.group(2)
            content = list_match.group(3)
            
            # 统一使用 "- " 格式
            formatted_line = f"{indent}- {content}"
            
            # 处理嵌套列表
            if indent:
                formatted_line = f"{indent}- {content}"
            
            formatted_lines.append(formatted_line)
            in_list = True
            continue
        
        # 处理加粗文本（**text**）
        # 确保加粗格式正确
        line = re.sub(r'\*\*([^*]+)\*\*', r'**\1**', line)
        
        # 处理emoji和文本的组合
        # 保持emoji不变
        
        # 处理分割线
        if re.match(r'^=+$', line.strip()):
            formatted_lines.append('---')
            if in_list:
                in_list = False
            continue
        
        # 普通文本
        if in_list:
            in_list = False
        
        formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def format_vulnerability_list_markdown(vulnerabilities: List, max_items: int = 20) -> str:
    """
    格式化漏洞列表为Markdown格式
    
    Args:
        vulnerabilities: 漏洞列表
        max_items: 最大显示数量
        
    Returns:
        str: Markdown格式的文本
    """
    if not vulnerabilities:
        return "暂无漏洞信息"
    
    lines = []
    lines.append("## 📋 捕获的漏洞列表\n")
    
    for idx, vuln in enumerate(vulnerabilities[:max_items], 1):
        content = vuln.content if isinstance(vuln.content, dict) else {}
        severity = content.get('severity', '未知')
        affected_component = content.get('affected_component', '').strip()
        
        # 构建漏洞项
        lines.append(f"### {idx}. {vuln.cve_id}")
        
        if vuln.published_date:
            lines.append(f"**披露时间**: {vuln.published_date}")
        
        lines.append(f"**标题**: {vuln.title[:80]}{'...' if len(vuln.title) > 80 else ''}")
        
        if severity and severity != '未知':
            # 根据危害等级添加颜色标记（钉钉markdown不支持颜色，但可以用emoji）
            severity_emoji = {
                'Critical': '🔴',
                'High': '🟠',
                'Medium': '🟡',
                'Moderate': '🟡',
                'Low': '🟢',
                'Important': '🟠'
            }
            emoji = severity_emoji.get(severity, '⚪')
            lines.append(f"**危害等级**: {emoji} {severity}")
        elif severity:
            lines.append(f"**危害等级**: {severity}")
        
        # 只显示有效的组件名称
        if affected_component and affected_component not in ['未知', '']:
            from app.services.secops_agent import SecOpsAgent
            agent = SecOpsAgent('', '', '')
            if agent._is_valid_component_name(affected_component):
                lines.append(f"**影响组件**: {affected_component}")
        
        lines.append("")  # 空行分隔
    
    if len(vulnerabilities) > max_items:
        lines.append(f"\n> 还有 {len(vulnerabilities) - max_items} 个漏洞未显示")
    
    return '\n'.join(lines)


def format_match_result_markdown(matches: List, vuln_count: int) -> str:
    """
    格式化匹配结果为Markdown格式
    
    Args:
        matches: 匹配结果列表
        vuln_count: 漏洞总数
        
    Returns:
        str: Markdown格式的文本
    """
    if not matches:
        lines = [
            "## ✅ 好消息！未发现受影响的资产",
            "",
            f"共检查了 **{vuln_count}** 个漏洞，未发现受影响的资产。"
        ]
        return '\n'.join(lines)
    
    # 按漏洞分组
    vuln_groups = {}
    for match in matches:
        cve_id = match['vulnerability'].cve_id
        if cve_id not in vuln_groups:
            vuln_groups[cve_id] = {
                'vulnerability': match['vulnerability'],
                'assets': []
            }
        vuln_groups[cve_id]['assets'].append(match)
    
    lines = []
    lines.append(f"## ⚠️ 发现 {len(vuln_groups)} 个漏洞影响了资产\n")
    lines.append("---\n")
    
    for idx, (cve_id, group) in enumerate(vuln_groups.items(), 1):
        vuln = group['vulnerability']
        assets = group['assets']
        content = vuln.content if isinstance(vuln.content, dict) else {}
        
        lines.append(f"### 【{idx}】 {cve_id}")
        lines.append(f"**标题**: {vuln.title}")
        
        severity = content.get('severity', '')
        if severity:
            severity_emoji = {
                'Critical': '🔴',
                'High': '🟠',
                'Medium': '🟡',
                'Moderate': '🟡',
                'Low': '🟢',
                'Important': '🟠'
            }
            emoji = severity_emoji.get(severity, '⚪')
            lines.append(f"**危害等级**: {emoji} {severity}")
        
        affected_component = content.get('affected_component', '').strip()
        if affected_component:
            from app.services.secops_agent import SecOpsAgent
            agent = SecOpsAgent('', '', '')
            if agent._is_valid_component_name(affected_component):
                lines.append(f"**影响组件**: {affected_component}")
        
        affected_versions = content.get('affected_versions', '').strip()
        if affected_versions:
            lines.append(f"**受影响版本**: {affected_versions[:200]}")
        
        lines.append(f"**受影响资产数量**: {len(assets)}")
        lines.append("")
        lines.append("**受影响资产列表**:")
        
        for asset_match in assets[:10]:  # 最多显示10个资产
            asset = asset_match['asset']
            reason = asset_match.get('reason', '')
            asset_type = asset.get_asset_type_display() if hasattr(asset, 'get_asset_type_display') else asset.asset_type
            
            asset_name = asset.name or asset.uuid
            asset_version = ""
            if isinstance(asset.data, dict):
                asset_version = asset.data.get('Version', '') or asset.data.get('version', '')
            
            if asset_version:
                lines.append(f"- **{asset_name}** ({asset_version}) - {asset_type}")
            else:
                lines.append(f"- **{asset_name}** - {asset_type}")
            
            if reason:
                lines.append(f"  - 匹配原因: {reason[:100]}")
        
        if len(assets) > 10:
            lines.append(f"  - ... 还有 {len(assets) - 10} 个资产")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    lines.append("💡 **建议**: 请尽快处理这些受影响的资产，根据漏洞详情采取相应的修复措施。")
    
    return '\n'.join(lines)

