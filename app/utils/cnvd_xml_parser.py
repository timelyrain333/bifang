# -*- coding: utf-8 -*-
"""
CNVD 漏洞 XML 解析器
解析从 CNVD 导出的 vulnerabilitys/vulnerability 格式 XML，转换为漏洞结构化数据。
"""
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime


def _text(el: Optional[ET.Element]) -> str:
    """获取元素文本，空元素返回空字符串。"""
    if el is None:
        return ''
    return (el.text or '').strip()


def _normalize_text(s: str) -> str:
    """规范化文本：去除 \\r、多余空白。"""
    if not s:
        return ''
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    return ' '.join(s.split())


def _parse_date(s: str):
    """解析日期字符串 YYYY-MM-DD，失败返回 None。"""
    if not s or not s.strip():
        return None
    s = s.strip()[:10]
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_cnvd_xml(xml_content: str) -> List[Dict[str, Any]]:
    """
    解析 CNVD 格式的 XML 内容。

    XML 结构示例：
    <vulnerabilitys>
      <vulnerability>
        <number>CNVD-2026-06831</number>
        <cves><cve><cveNumber>CVE-xxx</cveNumber><cveUrl>...</cveUrl></cve></cves>
        <title>...</title>
        <serverity>高</serverity>
        <products><product>...</product></products>
        <isEvent>...</isEvent>
        <submitTime>...</submitTime>
        <openTime>...</openTime>
        <referenceLink>...</referenceLink>
        <formalWay>...</formalWay>
        <description>...</description>
        <patchName>...</patchName>
        <patchDescription>...</patchDescription>
      </vulnerability>
    </vulnerabilitys>

    Returns:
        漏洞字典列表，每个元素包含：cnvd_id, title, description, published_date,
        severity, products, cve_list, content (与 Vulnerability.content 兼容的字段) 等。
    """
    root = ET.fromstring(xml_content)
    # 根节点可能是 vulnerabilitys 或 vulnerabilitys（拼写与样例一致）
    if root.tag.endswith('vulnerabilitys'):
        items = root.findall('vulnerability')
    else:
        items = root.findall('.//vulnerability')
    if not items:
        items = root.findall('vulnerability')

    result = []
    for vuln_el in items:
        number_el = vuln_el.find('number')
        cnvd_id = _text(number_el) if number_el is not None else ''
        if not cnvd_id:
            continue

        title_el = vuln_el.find('title')
        title = _normalize_text(_text(title_el) or cnvd_id)[:500]

        desc_el = vuln_el.find('description')
        description = _normalize_text(_text(desc_el) or '')

        # serverity 为原文拼写
        sev_el = vuln_el.find('serverity')
        severity = _text(sev_el) or ''

        # CVE 列表
        cve_list = []
        cves_el = vuln_el.find('cves')
        if cves_el is not None:
            for cve_el in cves_el.findall('cve'):
                cve_num = _text(cve_el.find('cveNumber'))
                cve_url = _text(cve_el.find('cveUrl'))
                if cve_num:
                    cve_list.append({'cveNumber': cve_num, 'cveUrl': cve_url or ''})

        # 产品列表
        products = []
        products_el = vuln_el.find('products')
        if products_el is not None:
            for p in products_el.findall('product'):
                t = _normalize_text(_text(p))
                if t:
                    products.append(t)

        ref_link = _normalize_text(_text(vuln_el.find('referenceLink')) or '')
        formal_way = _normalize_text(_text(vuln_el.find('formalWay')) or '')
        is_event = _text(vuln_el.find('isEvent')) or ''
        submit_time = _text(vuln_el.find('submitTime')) or ''
        open_time = _text(vuln_el.find('openTime')) or ''
        patch_name = _normalize_text(_text(vuln_el.find('patchName')) or '')
        patch_desc = _normalize_text(_text(vuln_el.find('patchDescription')) or '')

        # 发布日期优先用 openTime，其次 submitTime
        published_date = _parse_date(open_time) or _parse_date(submit_time)

        content = {
            'cnvd_id': cnvd_id,
            'cve_ids': [c.get('cveNumber', '') for c in cve_list if c.get('cveNumber')],
            'basic_description': (description[:500] if description else title[:500]),
            'vulnerability_description': description,
            'severity': severity,
            'affected_component': ', '.join(products)[:500] if products else '',
            'affected_versions': '',  # XML 样例中无单独版本字段，产品名中可能包含版本
            'solution': formal_way,
            'references': [ref_link] if ref_link else [],
            'is_event': is_event,
            'submit_time': submit_time,
            'open_time': open_time,
            'reference_link': ref_link,
            'patch_name': patch_name,
            'patch_description': patch_desc,
        }

        result.append({
            'cnvd_id': cnvd_id,
            'title': title,
            'description': description,
            'published_date': published_date,
            'severity': severity,
            'products': products,
            'cve_list': cve_list,
            'reference_link': ref_link,
            'formal_way': formal_way,
            'content': content,
        })
    return result
