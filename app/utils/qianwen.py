"""
通义千问AI模型调用工具
用于解析漏洞详情信息
"""
import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 尝试导入openai库
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai库未安装，AI解析功能不可用。请运行: pip install openai")


def parse_vulnerability_with_ai(raw_content: str, cve_id: str, api_key: str, 
                                api_base: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                                model: str = 'qwen-plus') -> Dict[str, Any]:
    """
    使用通义千问AI模型解析漏洞详情
    
    Args:
        raw_content: 漏洞原始邮件内容
        cve_id: CVE编号
        api_key: 通义千问API Key
        api_base: API地址
        model: 模型名称
    
    Returns:
        dict: 解析后的结构化字段
    """
    if not OPENAI_AVAILABLE:
        logger.error("openai库未安装，无法使用AI解析")
        return {}
    
    if not api_key:
        logger.warning("通义千问API Key未配置")
        return {}
    
    try:
        # 初始化客户端，设置超时时间（5分钟）
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=300.0  # 5分钟超时
        )
        
        # 构建提示词
        system_prompt = """你是一个专业的网络安全漏洞分析助手。你的任务是从漏洞邮件内容中提取结构化信息。

请仔细分析邮件内容，提取以下字段：
1. basic_description: 漏洞基本描述（一句话概括）
2. vulnerability_description: 漏洞详细描述
3. impact: 漏洞影响和危害
4. severity: 漏洞危害等级（Critical/High/Medium/Low/Moderate/Important，必须从邮件内容中准确提取，如果确实没有提到则留空）
5. affected_component: 受影响组件名称（**重要**：只提取组件名称，如"Apache Struts"、"Apache SIS"、"Apache Kyuubi"等，**不要包含版本号或版本范围**）
6. affected_versions: 受影响版本（**重要**：只提取版本范围，格式如："2.0.0 before 2.2.1" 或 "2.2.1 through 6.1.0" 或 "< 3.13.3" 或 "1.6.0 through <=1.10.2" 等，**不要包含组件名称**）
7. solution: 解决方案（升级建议、补丁信息等）
8. mitigation: 临时缓解措施（如果邮件中有提到）

要求：
- 提取的信息要准确，不能编造
- 如果没有找到某个字段的信息，则该字段返回空字符串
- 优先从邮件正文中提取，而不是从邮件头
- 对于回复邮件，需要从引用块中提取相关信息
- 版本信息要尽可能完整和准确
- 所有文本字段返回纯文本，不要包含Markdown格式
- **特别注意1**：severity（危害等级）字段非常重要，请仔细查找邮件中的"Severity:"、"严重程度"、"Critical/High/Medium/Low"等关键词，确保准确提取
- **特别注意2**：affected_component（影响组件）字段**只能包含组件名称**，不能包含版本号、版本范围、漏洞类型描述或其他信息。组件名称必须是软件/库/框架的实际名称，如"Apache Struts"、"OpenSSL"、"Python"等。**绝对不能**是以下内容：
  - 版本信息：如"before 2.2.1"、"2.2.1"等
  - 漏洞类型：如"XXE vulnerability"、"heap"等
  - 代词或描述性词语：如"this"、"two"等
  - 其他非组件名称的内容
  例如：如果邮件中提到"Apache Struts 2.0.0 before 2.2.1"，affected_component应该是"Apache Struts"，affected_versions应该是"2.0.0 before 2.2.1"
- **特别注意3**：affected_versions（影响版本）字段**只能包含版本范围**，不能包含组件名称。如果有多个组件或包受影响，请用换行符分隔，但每个条目只包含版本范围，不包含组件名称
        
请以JSON格式返回结果，格式如下：
{
    "basic_description": "...",
    "vulnerability_description": "...",
    "impact": "...",
    "severity": "...",
    "affected_component": "Apache Struts",
    "affected_versions": "2.0.0 before 2.2.1\\n2.2.1 through 6.1.0",
    "solution": "...",
    "mitigation": "..."
}"""

        user_prompt = f"""请分析以下CVE漏洞邮件内容（CVE编号：{cve_id}），提取结构化信息：

邮件内容：
{raw_content[:8000]}

**特别提醒**：
1. 请仔细查找邮件中关于"Severity"或"严重程度"的信息，通常格式为"Severity: High"或"(Severity: Critical)"等
2. 如果邮件中明确提到了危害等级（如Critical、High、Medium、Low等），请务必提取到severity字段
3. **关键要求 - affected_component字段**：
   - 必须从邮件中提取软件/库/框架的实际名称，如"Apache Struts"、"NodeJS"、"libpng"、"curl"等
   - 如果邮件标题是"NodeJS Security Releases"，affected_component应该是"NodeJS"
   - 如果邮件标题是"libpng 1.6.54: two heap buffer over-read"，affected_component应该是"libpng"
   - 如果邮件标题是"Apache Struts: XXE vulnerability"，affected_component应该是"Apache Struts"
   - **绝对不能**提取以下内容作为组件名称：
     * 版本号或版本范围（如"before 2.2.1"、"2.2.1"）
     * 漏洞类型描述（如"XXE vulnerability"、"heap"、"buffer over-read"）
     * 代词或描述性词语（如"this"、"two"、"all"）
     * 邮件头信息（如"Subject"、"From"等）
   - 如果无法确定组件名称，affected_component应该返回空字符串""
4. **关键要求 - affected_versions字段**：
   - 只提取版本范围，如"2.0.0 before 2.2.1"、"1.6.54"等
   - 不要包含组件名称
5. 请返回JSON格式的解析结果。"""

        # 调用模型，设置超时时间
        logger.info(f"开始调用通义千问模型 {model} 解析CVE: {cve_id}")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},  # 明确要求JSON格式输出
                temperature=0.1,  # 降低温度以获得更稳定的输出
                max_tokens=2000
            )
        except openai.APITimeoutError as timeout_error:
            logger.warning(f"AI API调用超时（5分钟）: {timeout_error}，将使用规则解析结果")
            return {}  # 返回空字典，让插件使用规则解析结果
        except Exception as api_error:
            logger.warning(f"调用通义千问API时发生异常: {api_error}，将使用规则解析结果")
            return {}  # 返回空字典，让插件使用规则解析结果，而不是抛出异常
        
        # 解析返回结果
        if not response.choices or len(response.choices) == 0:
            logger.error("通义千问API返回的响应中没有choices")
            return {}
        
        content = response.choices[0].message.content.strip()
        logger.debug(f"AI模型返回内容（前500字符）: {content[:500]}")
        
        # 尝试从返回内容中提取JSON
        # 模型可能返回Markdown格式的代码块，需要提取JSON部分
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            try:
                result = json.loads(json_str)
                logger.info(f"成功解析CVE {cve_id} 的字段信息，提取到 {len(result)} 个字段")
                
                # 验证和修正解析结果
                result = _validate_and_fix_parsed_result(result, raw_content, cve_id)
                
                return result
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON失败: {e}, JSON字符串: {json_str[:200]}")
                return {}
        else:
            logger.warning(f"AI返回内容中未找到有效的JSON格式，完整内容: {content[:500]}")
            return {}
            
    except json.JSONDecodeError as e:
        logger.error(f"解析AI返回的JSON失败: {e}, 内容: {content[:500]}")
        return {}
    except Exception as e:
        logger.error(f"调用通义千问API失败: {e}", exc_info=True)
        return {}


def test_qianwen_connection(api_key: str, api_base: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                           model: str = 'qwen-plus') -> Dict[str, Any]:
    """
    测试通义千问API连接
    
    Args:
        api_key: API Key
        api_base: API地址
        model: 模型名称
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    if not OPENAI_AVAILABLE:
        return {'success': False, 'message': 'openai库未安装，请运行: pip install openai'}
    
    if not api_key:
        return {'success': False, 'message': 'API Key未提供'}
    
    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        # 发送测试请求
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个测试助手。"},
                {"role": "user", "content": "请回复'测试成功'"}
            ],
            max_tokens=50
        )
        
        result = response.choices[0].message.content
        return {'success': True, 'message': f'连接成功！模型响应: {result}'}
        
    except Exception as e:
        logger.error(f"测试通义千问API连接失败: {e}", exc_info=True)
        return {'success': False, 'message': f'连接失败: {str(e)}'}


def _is_invalid_component_name(component: str) -> bool:
    """
    检查组件名称是否无效
    
    Args:
        component: 组件名称
        
    Returns:
        bool: 如果组件名称无效返回True，否则返回False
    """
    if not component or not component.strip():
        return False
    
    component_lower = component.lower().strip()
    
    # 有效组件名称白名单（常见编程语言、框架、库等）
    valid_components = [
        'go', 'golang',  # Go语言
        'python', 'nodejs', 'node.js', 'java', 'javascript', 'typescript',
        'rust', 'c', 'cpp', 'c++', 'csharp', 'c#', 'php', 'ruby', 'perl',
        'apache', 'nginx', 'tomcat', 'jetty',
        'openssl', 'curl', 'wget', 'git',
        'docker', 'kubernetes', 'k8s',
        'mysql', 'postgresql', 'mongodb', 'redis',
        'libpng', 'libjpeg', 'zlib', 'gzip',
    ]
    
    # 如果组件名称在白名单中，直接返回False（有效）
    if component_lower in valid_components:
        return False
    
    # 无效的组件名称列表
    invalid_exact = [
        'this', 'that', 'these', 'those',  # 代词
        'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',  # 数字
        'one', 'first', 'second', 'third',
        'heap', 'stack', 'buffer', 'memory',  # 技术词汇（但如果是组件名称的一部分则允许）
        'unknown', 'unknown component', 'n/a', 'na',  # 未知
        '未知', '未知组件',
        'we have just', 'we have', 'have just',  # 邮件开头常见短语
    ]
    
    if component_lower in invalid_exact:
        return True
    
    # 无效的组件名称模式（更精确的匹配）
    invalid_patterns = [
        r'^(two|three|four|five|six|seven|eight|nine|ten)\s+',  # 数字开头的描述（如"two heap"）
        r'^(xxe|xss|csrf|sql\s*injection|rce|rfi|lfi)',  # 漏洞类型
        r'^(before|after|through|to|until|up\s+to|from)\s+',  # 版本范围关键词（必须后面跟内容）
        r'^[<>=]+\s*\d+',  # 版本比较符
        r'^\d+\.\d+',  # 版本号开头
        r'^(before|after|through|to|until|up\s+to|from)\s+\d+',  # 版本范围（如"before 2.2.1"）
        r'^\d+\s+(before|after|through|to|until|up\s+to|from)\s+\d+',  # 版本范围（如"2.0.0 before 2.2.1"）
        r'^[\d\s<>=]+$',  # 只包含数字、空格、比较符（不包含字母，避免误判"go"等）
    ]
    
    for pattern in invalid_patterns:
        if re.match(pattern, component_lower, re.IGNORECASE):
            return True
    
    # 检查是否包含"vulnerability"、"issue"、"bug"等关键词（这些不是组件名称）
    if any(keyword in component_lower for keyword in ['vulnerability', 'issue', 'bug', 'problem', 'error']):
        return True
    
    # 检查是否是邮件开头常见短语
    if component_lower.startswith('we have') or component_lower.startswith('have just'):
        return True
    
    return False


def _extract_component_from_text(text: str) -> str:
    """
    从文本中提取组件名称（从标题或内容中）
    
    Args:
        text: 文本内容
        
    Returns:
        str: 提取的组件名称，如果无法提取则返回空字符串
    """
    if not text:
        return ""
    
    # 尝试匹配常见的组件名称模式
    # 优先级从高到低
    component_patterns = [
        # 模式1: "Go 1.25.6" 或 "Go versions" -> "Go"
        r'\b(Go|golang)\s+(?:versions?|\d+\.\d+)',
        # 模式2: "NodeJS Security Releases" -> "NodeJS"
        r'\b(NodeJS|nodejs|Node\.js)\b',
        # 模式3: "libpng 1.6.54" -> "libpng"
        r'\b(libpng|libPNG)\s+\d+\.\d+',
        # 模式4: "Apache Struts: XXE vulnerability" -> "Apache Struts"
        r'\b(Apache\s+[A-Z][a-zA-Z]+)\s*:',
        # 模式5: "Apache Struts vulnerability" -> "Apache Struts"
        r'\b(Apache\s+[A-Z][a-zA-Z]+)\s+(?:Security|vulnerability|issue|Release|Releases)',
        # 模式6: "Apache Struts 2.0.0" -> "Apache Struts"
        r'\b(Apache\s+[A-Z][a-zA-Z]+)\s+\d+\.\d+',
        # 模式7: "Apache Struts" 单独出现（在描述中）
        r'\b(Apache\s+Struts)\b',
        # 模式8: "in Apache Struts" 或 "of Apache Struts" -> "Apache Struts"
        r'\b(in|of|for|with)\s+(Apache\s+[A-Z][a-zA-Z]+)',
        # 模式9: "Apache Struts" 在句子中（前面可能有其他词）
        r'\b(Apache\s+[A-Z][a-zA-Z]+)(?:\s|,|\.|:|;|$)',
        # 模式10: 其他常见组件名称（大写字母开头的单词序列）
        r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s*(?:Security|vulnerability|issue|Release|Releases)',
        # 模式11: 小写开头的组件名称（如"libpng"、"curl"）
        r'\b([a-z]+)\s+\d+\.\d+',
        # 模式12: "Go" 单独出现（在Subject或标题中）
        r'\b(Go|golang)\b(?!\s+(?:have|is|are|was|were|will|can|should))',  # 排除"Go have"等
    ]
    
    for idx, pattern in enumerate(component_patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # 对于模式8（"in Apache Struts"），组件名称在group(2)
            if idx == 7:  # 模式8的索引（"in Apache Struts"）
                component = match.group(2).strip()
            else:
                component = match.group(1).strip()
            # 验证提取的组件名称是否有效
            if not _is_invalid_component_name(component):
                return component
    
    return ""


def _validate_and_fix_parsed_result(result: Dict[str, Any], raw_content: str, cve_id: str) -> Dict[str, Any]:
    """
    验证和修正AI解析的结果
    
    Args:
        result: AI解析的结果
        raw_content: 原始邮件内容
        cve_id: CVE编号
        
    Returns:
        Dict[str, Any]: 修正后的结果
    """
    if not result or not isinstance(result, dict):
        return result
    
    # 验证和修正 affected_component
    affected_component = result.get('affected_component', '').strip()
    if affected_component and _is_invalid_component_name(affected_component):
        logger.warning(f"AI解析的组件名称无效: '{affected_component}' (CVE: {cve_id})，尝试从邮件内容中重新提取")
        
        # 尝试从邮件内容中提取组件名称
        # 优先从邮件标题中提取（通常在Subject行）
        extracted_component = ""
        
        # 从邮件开头提取Subject行
        subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', raw_content, re.IGNORECASE | re.MULTILINE)
        if subject_match:
            subject = subject_match.group(1).strip()
            extracted_component = _extract_component_from_text(subject)
        
        # 如果从Subject中提取失败，尝试从前500字符中提取
        if not extracted_component:
            extracted_component = _extract_component_from_text(raw_content[:500])
        
        # 如果还是失败，尝试从前2000字符中提取（扩大范围）
        if not extracted_component:
            extracted_component = _extract_component_from_text(raw_content[:2000])
        
        # 如果还是失败，尝试从整个邮件内容中提取（但限制在8000字符内）
        if not extracted_component:
            extracted_component = _extract_component_from_text(raw_content[:8000])
        
        # 如果还是失败，尝试从邮件正文中提取（跳过邮件头）
        if not extracted_component:
            # 查找邮件正文开始位置（通常是第一个空行之后）
            body_start = raw_content.find('\n\n')
            if body_start > 0:
                body_content = raw_content[body_start:body_start+2000]
                extracted_component = _extract_component_from_text(body_content)
        
        if extracted_component:
            logger.info(f"从邮件内容中提取到组件名称: '{extracted_component}' (CVE: {cve_id})")
            result['affected_component'] = extracted_component
        else:
            logger.warning(f"无法从邮件内容中提取有效的组件名称 (CVE: {cve_id})，将affected_component设为空")
            result['affected_component'] = ""
    
    # 验证和修正 affected_versions（如果包含组件名称，需要清理）
    affected_versions = result.get('affected_versions', '').strip()
    if affected_versions:
        # 检查是否包含组件名称
        component_pattern = r'[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*'
        if re.search(component_pattern, affected_versions):
            # 清理版本信息，移除组件名称
            lines = affected_versions.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 移除行首的 "- " 或 "-"
                if line.startswith('-'):
                    line = line.lstrip('-').strip()
                # 尝试匹配版本范围模式
                version_pattern = r'(\d+\.\d+(?:\.\d+)?(?:\s+(?:before|through|to)\s+(?:<[=>]?\s*)?\d+\.\d+(?:\.\d+)?)?|<[=>]?\s*\d+\.\d+(?:\.\d+)?|>\s*=\s*\d+\.\d+(?:\.\d+)?)'
                match = re.search(version_pattern, line)
                if match:
                    cleaned_lines.append(match.group(1))
            if cleaned_lines:
                result['affected_versions'] = '\n'.join(cleaned_lines)
                logger.info(f"已清理affected_versions中的组件名称 (CVE: {cve_id})")
    
    return result

