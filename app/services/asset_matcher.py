"""
资产匹配服务
根据漏洞的影响组件和版本信息匹配资产
"""
import re
import logging
from typing import List, Dict, Any, Optional
from django.db.models import Q
from app.models import Asset, Vulnerability

logger = logging.getLogger(__name__)


class AssetMatcher:
    """资产匹配器"""
    
    @staticmethod
    def match_vulnerability_to_assets(vulnerability: Vulnerability) -> List[Dict[str, Any]]:
        """
        将漏洞与资产进行匹配
        
        Args:
            vulnerability: 漏洞对象
            
        Returns:
            List[Dict]: 匹配到的资产列表，每个资产包含匹配信息
        """
        if not vulnerability.content:
            return []
        
        content = vulnerability.content if isinstance(vulnerability.content, dict) else {}
        affected_component = content.get('affected_component', '').strip()
        affected_versions = content.get('affected_versions', '').strip()
        
        # 检查affected_component是否看起来像版本号（错误的数据）
        if affected_component:
            version_patterns = [
                r'^\s*(before|after|through|to|until|up\s+to|from)\s+',  # 版本范围关键词
                r'^\s*[<>=]+\s*\d+',  # 版本比较符
                r'^\s*\d+\.\d+',  # 版本号开头
            ]
            for pattern in version_patterns:
                if re.match(pattern, affected_component, re.IGNORECASE):
                    logger.warning(f"漏洞 {vulnerability.cve_id} 的 affected_component '{affected_component}' 看起来像版本信息，可能是错误数据，跳过匹配")
                    return []
        
        if not affected_component:
            logger.warning(f"漏洞 {vulnerability.cve_id} 没有影响组件信息，无法匹配资产")
            return []
        
        # 查找匹配的资产
        matched_assets = []
        
        # 1. 根据组件名称匹配资产（严格模式）
        # 资产名称、软件名称、中间件名称等可能包含组件名
        component_keywords = AssetMatcher._extract_component_keywords(affected_component)
        
        if not component_keywords:
            return []
        
        # 查询可能相关的资产
        asset_query = Q()
        for keyword in component_keywords:
            # 使用更严格的匹配：要求关键词在资产名称中以完整词出现
            # 例如："Apache SIS" 应该匹配 "Apache SIS" 或 "apache-sis"，但不应该匹配 "assist"（包含"sis"）
            
            # 方式1：精确匹配（包含空格分隔的完整关键词）
            asset_query |= Q(name__iregex=rf'\b{re.escape(keyword)}\b')
            # 方式2：匹配包含关键词的完整组件名（如"apache-sis"）
            asset_query |= Q(name__icontains=keyword.replace(' ', '-'))
            asset_query |= Q(name__icontains=keyword.replace(' ', '_'))
            
            # 在data字段中搜索（通常软件、中间件等会有更详细的信息）
            asset_query |= Q(data__icontains=keyword)
        
        if not asset_query:
            return []
        
        assets = Asset.objects.filter(asset_query).distinct()
        
        # 2. 根据版本信息进一步筛选，并验证组件名称匹配的准确性
        for asset in assets:
            # 先验证组件名称是否真的匹配（避免误匹配）
            asset_name_lower = (asset.name or '').lower()
            asset_data_str = str(asset.data).lower() if asset.data else ''
            
            # 检查资产名称或数据中是否真正包含组件关键词
            # 使用更严格的匹配：要求至少匹配一个完整的关键词，且不能是部分匹配
            component_matched = False
            for keyword in component_keywords:
                # 更严格的匹配：要求关键词作为完整词出现
                # 避免部分匹配（如 "chardet" 不应该匹配 "apache struts"）
                keyword_parts = keyword.split()
                
                # 如果关键词是单个词，要求完整匹配
                if len(keyword_parts) == 1:
                    # 完整词匹配
                    if (re.search(rf'\b{re.escape(keyword)}\b', asset_name_lower) or
                        re.search(rf'\b{re.escape(keyword)}\b', asset_data_str)):
                        component_matched = True
                        break
                else:
                    # 多词关键词，要求所有词都出现（顺序可以不同，但必须都在）
                    all_parts_match = True
                    for part in keyword_parts:
                        if not (re.search(rf'\b{re.escape(part)}\b', asset_name_lower) or
                               re.search(rf'\b{re.escape(part)}\b', asset_data_str)):
                            all_parts_match = False
                            break
                    if all_parts_match:
                        component_matched = True
                        break
                    
                    # 也尝试连字符和下划线形式
                    hyphen_keyword = keyword.replace(' ', '-')
                    underscore_keyword = keyword.replace(' ', '_')
                    if (hyphen_keyword in asset_name_lower or 
                        underscore_keyword in asset_name_lower or
                        hyphen_keyword in asset_data_str or
                        underscore_keyword in asset_data_str):
                        component_matched = True
                        break
            
            if not component_matched:
                continue
            
            match_info = AssetMatcher._check_version_match(asset, affected_versions, affected_component)
            if match_info['matched']:
                matched_assets.append({
                    'asset': asset,
                    'match_reason': match_info['reason'],
                    'component': affected_component,
                    'affected_versions': affected_versions,
                    'vulnerability': vulnerability
                })
        
        logger.info(f"漏洞 {vulnerability.cve_id} 匹配到 {len(matched_assets)} 个资产")
        return matched_assets
    
    @staticmethod
    def _extract_component_keywords(component_name: str) -> List[str]:
        """
        从组件名称中提取关键词（严格模式）
        
        Args:
            component_name: 组件名称，如 "Apache SIS" 或 "Apache:sis"
            
        Returns:
            List[str]: 关键词列表（只返回有意义的完整关键词）
        """
        keywords = []
        
        if not component_name:
            return []
        
        # 检查组件名称是否看起来像版本号或版本范围（如 "before 2.2.1", "2.2.1", "< 3.13.3"）
        version_patterns = [
            r'^\s*(before|after|through|to|until|up\s+to|from)\s+',  # 版本范围关键词
            r'^\s*[<>=]+\s*\d+',  # 版本比较符
            r'^\s*\d+\.\d+',  # 版本号开头
            r'^\s*\d+\s*$',  # 纯数字
        ]
        
        for pattern in version_patterns:
            if re.match(pattern, component_name, re.IGNORECASE):
                logger.warning(f"组件名称 '{component_name}' 看起来像版本信息，跳过提取关键词")
                return []  # 如果看起来像版本号，不提取关键词，避免误匹配
        
        # 移除版本号、特殊字符等
        clean_name = re.sub(r'[:\-_\s]+', ' ', component_name.strip())
        parts = clean_name.split()
        
        # 过滤掉明显的版本号部分（如 "2.2.1", "v1.0" 等）
        filtered_parts = []
        for part in parts:
            # 跳过纯数字
            if part.isdigit():
                continue
            # 跳过版本号模式（如 "2.2.1", "v1.0.0"）
            if re.match(r'^v?\d+\.\d+(?:\.\d+)?', part, re.IGNORECASE):
                continue
            # 跳过版本范围关键词
            if part.lower() in ['before', 'after', 'through', 'to', 'until', 'up', 'from', '<', '>', '<=', '>=']:
                continue
            filtered_parts.append(part)
        
        if not filtered_parts:
            logger.warning(f"组件名称 '{component_name}' 过滤后没有有效部分，跳过提取关键词")
            return []
        
        # 只保留长度>=4的单词，避免短字符串误匹配（如"sis"会误匹配）
        # 或者保留完整的组件名称组合
        for part in filtered_parts:
            # 过滤掉常见停用词，且长度至少4个字符
            if part and len(part) >= 4:
                keywords.append(part.lower())
        
        # 保留完整的组件名称（如果包含多个单词，作为完整匹配）
        if len(filtered_parts) > 1:
            # 多词组件名，保留完整名称
            full_name = ' '.join(p.lower() for p in filtered_parts if len(p) >= 3)
            if full_name:
                keywords.append(full_name)
        
        # 如果组件名本身就是单个长词（>=4字符），也保留
        if len(filtered_parts) == 1 and len(filtered_parts[0]) >= 4:
            keywords.append(filtered_parts[0].lower())
        
        # 去重
        return list(set(keywords))
    
    @staticmethod
    def _check_version_match(asset: Asset, affected_versions: str, component_name: str) -> Dict[str, Any]:
        """
        检查资产版本是否在受影响版本范围内
        
        Args:
            asset: 资产对象
            affected_versions: 受影响版本字符串，如 "< 3.13.3" 或 "1.6.0 through <=1.10.2"
            
        Returns:
            Dict: 匹配信息
                - matched: bool, 是否匹配
                - reason: str, 匹配原因
        """
        if not affected_versions or not affected_versions.strip():
            # 如果没有版本信息，只要组件名匹配就认为可能受影响
            return {
                'matched': True,
                'reason': f'组件名称匹配（{component_name}），但无版本信息，建议进一步确认'
            }
        
        # 从资产中提取版本信息
        asset_data = asset.data if isinstance(asset.data, dict) else {}
        asset_version = None
        
        # 尝试从多个字段中提取版本
        version_fields = ['Version', 'version', 'VersionName', 'version_name', 'AppVersion', 'app_version']
        for field in version_fields:
            if field in asset_data:
                asset_version = str(asset_data[field]).strip()
                break
        
        # 如果资产中没有版本信息
        if not asset_version:
            return {
                'matched': True,
                'reason': f'组件名称匹配（{component_name}），但资产无版本信息，建议进一步确认'
            }
        
        # 解析受影响版本范围
        try:
            is_affected = AssetMatcher._parse_version_range(asset_version, affected_versions)
            if is_affected:
                return {
                    'matched': True,
                    'reason': f'组件名称和版本匹配：资产版本 {asset_version} 在受影响版本范围 {affected_versions} 内'
                }
            else:
                return {
                    'matched': False,
                    'reason': f'组件名称匹配，但资产版本 {asset_version} 不在受影响版本范围 {affected_versions} 内'
                }
        except Exception as e:
            logger.warning(f"解析版本范围失败: {e}")
            # 解析失败时，如果组件名匹配，返回可能受影响
            return {
                'matched': True,
                'reason': f'组件名称匹配（{component_name}），但版本解析失败，建议进一步确认'
            }
    
    @staticmethod
    def _parse_version_range(version: str, version_range: str) -> bool:
        """
        解析版本范围，判断给定版本是否在范围内
        
        Args:
            version: 待检查的版本，如 "3.13.2"
            version_range: 版本范围，如 "< 3.13.3" 或 "1.6.0 through <=1.10.2"
            
        Returns:
            bool: 是否在范围内
        """
        def parse_version(v: str) -> tuple:
            """解析版本号为元组，如 "3.13.2" -> (3, 13, 2)"""
            parts = re.findall(r'\d+', v)
            return tuple(int(p) for p in parts)
        
        def compare_version(v1: tuple, v2: tuple) -> int:
            """比较两个版本，返回 -1, 0, 1"""
            max_len = max(len(v1), len(v2))
            v1_padded = v1 + (0,) * (max_len - len(v1))
            v2_padded = v2 + (0,) * (max_len - len(v2))
            for p1, p2 in zip(v1_padded, v2_padded):
                if p1 < p2:
                    return -1
                elif p1 > p2:
                    return 1
            return 0
        
        try:
            version_tuple = parse_version(version)
            
            # 清理版本范围字符串
            version_range = version_range.strip()
            
            # 处理 "< 3.13.3" 格式
            if version_range.startswith('<='):
                max_version = parse_version(version_range[2:].strip())
                return compare_version(version_tuple, max_version) <= 0
            elif version_range.startswith('<'):
                max_version = parse_version(version_range[1:].strip())
                return compare_version(version_tuple, max_version) < 0
            elif version_range.startswith('>='):
                min_version = parse_version(version_range[2:].strip())
                return compare_version(version_tuple, min_version) >= 0
            elif version_range.startswith('>'):
                min_version = parse_version(version_range[1:].strip())
                return compare_version(version_tuple, min_version) > 0
            
            # 处理范围格式，如 "1.6.0 through <=1.10.2"
            if 'through' in version_range.lower():
                parts = re.split(r'\s+through\s+', version_range, flags=re.IGNORECASE)
                if len(parts) == 2:
                    min_part = parts[0].strip()
                    max_part = parts[1].strip()
                    
                    min_version = parse_version(min_part)
                    if max_part.startswith('<='):
                        max_version = parse_version(max_part[2:].strip())
                        return compare_version(version_tuple, min_version) >= 0 and compare_version(version_tuple, max_version) <= 0
                    elif max_part.startswith('<'):
                        max_version = parse_version(max_part[1:].strip())
                        return compare_version(version_tuple, min_version) >= 0 and compare_version(version_tuple, max_version) < 0
            
            # 如果无法解析，返回True（保守处理）
            logger.warning(f"无法解析版本范围: {version_range}")
            return True
            
        except Exception as e:
            logger.error(f"解析版本失败: {e}, version={version}, range={version_range}")
            return True  # 解析失败时保守处理
    
    @staticmethod
    def match_recent_vulnerabilities(days: int = 7) -> List[Dict[str, Any]]:
        """
        匹配最近N天内的漏洞到资产
        
        Args:
            days: 天数，默认7天
            
        Returns:
            List[Dict]: 匹配结果列表
        """
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        since_date = timezone.now() - timedelta(days=days)
        vulnerabilities = Vulnerability.objects.filter(
            collected_at__gte=since_date
        ).order_by('-collected_at')
        
        all_matches = []
        for vuln in vulnerabilities:
            matches = AssetMatcher.match_vulnerability_to_assets(vuln)
            all_matches.extend(matches)
        
        logger.info(f"最近 {days} 天的漏洞匹配到 {len(all_matches)} 个受影响资产")
        return all_matches

