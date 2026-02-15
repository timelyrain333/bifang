
























"""
SecOps 智能体 - 基于 LangChain 重构版本
支持 Streaming 中间步骤推送和分阶段执行
"""
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from django.conf import settings

from app.agent_tools.hexstrike_tools import HexStrikeProgressiveTool
from app.services.task_tools import (
    create_task,
    list_tasks,
    update_task,
    parse_cron_from_natural_language,
    list_assets,
)
from app.utils.sse_manager import SSEManager

logger = logging.getLogger(__name__)


class SecOpsLangChainAgent:
    """
    基于 LangChain 的 SecOps 智能体

    特点：
    1. 支持 Streaming 中间步骤推送
    2. 集成 LangChain 工具生态
    3. 异步执行，不阻塞
    4. 实时反馈用户

    注意：适配 langchain 1.2.x 版本
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-plus",
        temperature: float = 0.3,
    ):
        """
        初始化 LangChain Agent

        Args:
            api_key: 通义千问 API Key
            model: 模型名称
            temperature: 温度参数
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

        # 初始化 LLM
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=model,
            temperature=temperature,
            streaming=True,  # 启用流式输出
        )

        # 定义工具
        self.tools = self._create_tools()

        logger.info(f"SecOps LangChain Agent 初始化完成: model={model}, tools={len(self.tools)}")

    def _create_tools(self) -> List[BaseTool]:
        """创建工具列表"""
        tools = [
            # HexStrike 分阶段扫描工具
            HexStrikeProgressiveTool(),
        ]

        return tools

    def _find_tool(self, tool_name: str) -> Optional[BaseTool]:
        """根据名称查找工具"""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的安全运营(SecOps)智能助手，可以帮助用户执行安全运营任务。

你的核心能力：
1. 安全评估：使用 hexstrike_progressive_scan 工具对目标进行分阶段扫描
2. 任务管理：创建、查询、更新定时任务
3. 资产查询：查询系统中的资产列表
4. 漏洞采集、资产采集等运营任务

重要提示：
- 当用户要求对某资产做安全评估时，优先使用 hexstrike_progressive_scan 工具
- hexstrike_progressive_scan 会分阶段执行：
  * 阶段1: Ping 主机存活检测（秒级）
  * 阶段2: 快速端口扫描（10-30秒）
  * 阶段3: 后台完整扫描 + 漏洞检测（分钟级）
- 只对用户拥有或明确授权的资产进行评估

工作流程：
1. 理解用户意图
2. 如果需要调用工具，使用 TOOLS 格式：`{{"tool": "tool_name", "input": {{...}}}}`
3. 工具执行完成后，总结结果
4. 提供专业建议

请用友好、专业的语气回复用户。"""

    async def astream_chat(
        self,
        message: str,
        user_id: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        异步流式对话（支持中间步骤推送）

        Args:
            message: 用户消息
            user_id: 用户ID（用于 SSE 推送）
            chat_history: 对话历史

        Yields:
            str: 响应文本片段
        """
        # 初始化 SSE 管理器
        channel = f"user_{user_id}" if user_id else "chat_progress"
        sse = SSEManager(channel)

        try:
            # 立即响应
            yield "🤖 正在处理您的请求...\n\n"

            # 构建消息历史
            messages = [SystemMessage(content=self._build_system_prompt())]

            # 添加历史消息
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

            # 添加当前消息
            messages.append(HumanMessage(content=message))

            # 简单的工具调用逻辑（不使用 AgentExecutor）
            # _process_with_tools 是 async generator，需要迭代
            async for chunk in self._process_with_tools(messages, sse, user_id):
                yield chunk

            # 推送完成事件
            sse.send_complete({"final_output": "响应完成"})

        except Exception as e:
            logger.error(f"Agent 执行失败: {e}", exc_info=True)
            error_msg = f"❌ 执行失败: {str(e)}"
            yield error_msg
            sse.send_error(error_msg)

    async def _process_with_tools(
        self,
        messages: List,
        sse: SSEManager,
        user_id: Optional[str] = None
    ) -> str:
        """
        处理消息（带工具调用）

        这是一个简化的实现，不依赖 AgentExecutor
        """
        # 第一步：让 LLM 决定是否需要调用工具
        decision_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个智能助手，可以调用工具来帮助用户。

可用工具：
{tool_descriptions}

如果用户的请求需要调用工具，请按以下 JSON 格式回复：
```json
{{
    "need_tool": true,
    "tool": "tool_name",
    "input": {{
        "parameter1": "value1",
        "parameter2": "value2"
    }}
}}
```

如果不需要调用工具，直接回复用户即可。"""),
            MessagesPlaceholder(variable_name="messages"),
        ])

        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.tools
        ])

        decision_chain = decision_prompt | self.llm | StrOutputParser()

        # 获取决策
        decision_input = {
            "tool_descriptions": tool_descriptions,
            "messages": messages
        }

        decision_result = ""
        async for chunk in decision_chain.astream(decision_input):
            decision_result += chunk
            # 实时流式输出决策过程（让用户看到 AI 正在思考）
            yield chunk

        logger.info(f"LLM 决策: {decision_result}")

        # 尝试解析工具调用
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', decision_result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个结果
                json_str = decision_result

            tool_call = json.loads(json_str)

            if tool_call.get("need_tool") and tool_call.get("tool"):
                # 需要调用工具
                tool_name = tool_call["tool"]
                tool_input = tool_call.get("input", {})

                tool = self._find_tool(tool_name)
                if tool:
                    # 执行工具
                    sse.send_tool_start(tool_name, tool_input)
                    logger.info(f"调用工具: {tool_name}, input: {tool_input}")

                    # Yield工具开始提示给前端
                    yield f"\n🔧 正在调用工具: {tool_name}\n"
                    yield f"📊 参数: {json.dumps(tool_input, ensure_ascii=False)}\n\n"

                    # 调用工具
                    if hasattr(tool, '_arun'):
                        tool_result = await tool._arun(**tool_input)
                    else:
                        tool_result = tool._run(**tool_input)

                    sse.send_tool_end(tool_name, str(tool_result)[:500])

                    # Yield工具执行结果给前端
                    if tool_result.get("success"):
                        task_id = tool_result.get("task_id")
                        if task_id:
                            yield f"✅ 工具执行成功！\n"
                            yield f"📋 后台任务ID: `{task_id}`\n"

                        # 显示快速扫描结果
                        quick_scan = tool_result.get("quick_scan", {})
                        ports = quick_scan.get("ports", [])
                        if ports:
                            yield f"\n🔍 快速扫描结果：\n"
                            yield f"发现 {len(ports)} 个开放端口：\n"
                            for port_info in ports[:10]:  # 只显示前10个
                                yield f"  - 端口 {port_info.get('port')}/{port_info.get('protocol')}: {port_info.get('state')}\n"
                            if len(ports) > 10:
                                yield f"  ... 还有 {len(ports) - 10} 个端口\n"
                        else:
                            yield f"⚠️  未发现开放端口（可能目标禁用了ICMP或防火墙阻止）\n"
                    else:
                        error = tool_result.get("error", "未知错误")
                        yield f"❌ 工具执行失败: {error}\n"

                    # 让 LLM 总结工具结果
                    summary_prompt = ChatPromptTemplate.from_messages([
                        ("system", "你是一个专业的安全运营助手。根据工具执行结果，给用户一个清晰、专业的总结。"),
                        MessagesPlaceholder(variable_name="messages"),
                        ("system", "工具执行结果：\n{tool_result}"),
                    ])

                    summary_chain = summary_prompt | self.llm | StrOutputParser()

                    summary_input = {
                        "messages": messages,
                        "tool_result": json.dumps(tool_result, ensure_ascii=False, indent=2)
                    }

                    final_response = ""
                    async for chunk in summary_chain.astream(summary_input):
                        final_response += chunk
                        yield chunk

                    # 完成
                    return
                else:
                    yield f"❌ 找不到工具: {tool_name}"
                    return
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"无法解析工具调用，使用直接回复: {e}")

        # 如果没有工具调用，直接返回 LLM 响应
        direct_prompt = ChatPromptTemplate.from_messages([
            ("system", self._build_system_prompt()),
            MessagesPlaceholder(variable_name="messages"),
        ])

        direct_chain = direct_prompt | self.llm | StrOutputParser()

        response = ""
        async for chunk in direct_chain.astream({"messages": messages}):
            response += chunk
            yield chunk

        # 完成
        return


# 使用示例
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = SecOpsLangChainAgent(
            api_key="your-api-key",
            model="qwen-plus"
        )

        async for chunk in agent.astream_chat(
            message="对 example.com 进行安全评估",
            user_id="test_user"
        ):
            print(chunk, end="")

    asyncio.run(test())