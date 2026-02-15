"""
HexStrike 分阶段扫描工具
支持实时进度推送和分阶段执行
"""
import asyncio
import logging
import subprocess
import json
from typing import Optional, Dict, Any, AsyncGenerator
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from django.conf import settings

from app.utils.sse_manager import SSEManager

logger = logging.getLogger(__name__)


class HexStrikeScanArgs(BaseModel):
    """HexStrike 扫描参数"""
    target: str = Field(..., description="要扫描的目标（IP地址或域名）")
    user_id: Optional[str] = Field(None, description="用户ID（可选）")


class HexStrikeProgressiveTool(BaseTool):
    """
    HexStrike 分阶段扫描工具

    特点：
    1. 分阶段执行（Ping → 快速扫描 → 完整扫描）
    2. 实时推送进度（通过 SSE）
    3. 支持异步执行
    4. 自动提交后台任务
    """

    name: str = "hexstrike_progressive_scan"
    description: str = """分阶段执行安全扫描（推荐使用）：

    阶段1: Ping + 主机存活检测（秒级）
    阶段2: 快速端口扫描 Top 100（10-30秒）
    阶段3: 完整扫描 + 漏洞检测（后台任务，分钟级）

    参数：
    - target: 要扫描的目标（IP/域名）
    - user_id: 用户ID（可选，用于进度推送）

    返回：快速结果 + 后台任务ID
    """

    args_schema: type[BaseModel] = HexStrikeScanArgs

    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
    
    def _run(
        self,
        target: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步执行（兼容 LangChain）
        
        注意：建议使用 _arun 异步方法以获得更好的性能
        """
        # 使用 asyncio 运行异步方法
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._arun(target, user_id))
    
    async def _arun(
        self,
        target: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        异步执行分阶段扫描
        
        Args:
            target: 扫描目标
            user_id: 用户ID（用于 SSE 推送）
            
        Returns:
            Dict: 包含快速结果和任务ID
        """
        # 初始化 SSE 管理器
        channel = f"user_{user_id}" if user_id else "scan_progress"
        sse = SSEManager(channel)
        
        results = {
            "target": target,
            "stages_completed": [],
            "task_id": None,
        }
        
        # ========== 阶段1: Ping + 主机存活检测 ==========
        sse.send_progress("ping", 10, f"📡 正在 Ping 目标主机 {target}...")
        logger.info(f"[阶段1] 开始 Ping: {target}")
        
        ping_result = await self._ping_target(target)
        
        if ping_result["alive"]:
            sse.send_progress("ping", 20, f"✅ 主机存活: {target} 响应正常")
            results["stages_completed"].append("ping")
            logger.info(f"[阶段1] Ping 成功: {target}")
        else:
            # Ping失败不阻止后续扫描，很多服务器禁用ICMP但端口开放
            sse.send_progress("ping", 20, f"⚠️  Ping无响应，但继续扫描（目标可能禁用ICMP）...")
            results["stages_completed"].append("ping")
            logger.warning(f"[阶段1] Ping失败，但继续扫描: {target}")
        
        # ========== 阶段2: 快速端口扫描 ==========
        sse.send_progress("quick_scan", 30, f"🔍 正在执行快速端口扫描（Top 100）...")
        logger.info(f"[阶段2] 开始快速端口扫描: {target}")
        
        quick_scan_result = await self._quick_port_scan(target, sse)
        
        open_ports = quick_scan_result.get("ports", [])
        sse.send_progress(
            "quick_scan", 
            60, 
            f"✅ 快速扫描完成：发现 {len(open_ports)} 个开放端口"
        )
        results["stages_completed"].append("quick_scan")
        results["quick_scan"] = quick_scan_result
        logger.info(f"[阶段2] 快速扫描完成: 发现 {len(open_ports)} 个端口")
        
        # ========== 阶段3: 提交后台完整扫描任务 ==========
        sse.send_progress("submit_task", 70, "🚀 正在启动后台完整扫描...")
        logger.info(f"[阶段3] 提交后台扫描任务: {target}")
        
        task_id = await self._submit_full_scan_task(target, user_id)
        
        if task_id:
            sse.send_progress(
                "task_submitted", 
                100, 
                f"✅ 后台扫描已启动 (任务ID: {task_id})"
            )
            sse.send_complete({
                "message": "后台扫描已启动，完成后将自动通知您",
                "task_id": task_id,
                "quick_results": quick_scan_result
            })
            
            results["task_id"] = task_id
            results["success"] = True
            logger.info(f"[阶段3] 后台任务已提交: {task_id}")
        else:
            sse.send_error("无法提交后台扫描任务", "submit_task")
            results["success"] = False
            results["error"] = "无法提交后台扫描任务"
        
        return results
    
    async def _ping_target(self, target: str, timeout: int = 5) -> Dict[str, Any]:
        """
        Ping 目标主机
        
        Args:
            target: 目标地址
            timeout: 超时时间（秒）
            
        Returns:
            Dict: {"alive": bool, "output": str}
        """
        try:
            # 使用 ping 命令
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", str(timeout), target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            alive = proc.returncode == 0
            output = stdout.decode() if stdout else ""
            
            return {
                "alive": alive,
                "output": output,
                "target": target
            }
        except Exception as e:
            logger.error(f"Ping 失败: {e}")
            return {"alive": False, "output": str(e), "target": target}
    
    async def _quick_port_scan(
        self, 
        target: str, 
        sse: SSEManager,
        top_ports: int = 100
    ) -> Dict[str, Any]:
        """
        快速端口扫描（Top N 端口）
        
        Args:
            target: 目标地址
            sse: SSE 管理器
            top_ports: 扫描端口数量
            
        Returns:
            Dict: {"ports": [...], "scan_time": float}
        """
        import time
        start_time = time.time()
        
        # 方案1: 使用 HexStrike 快速扫描 API
        if getattr(settings, 'HEXSTRIKE_ENABLED', True):
            try:
                from app.services.hexstrike_client import HexStrikeClient
                
                client = HexStrikeClient(
                    base_url=getattr(settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888'),
                    timeout=60,  # 快速扫描超时 1 分钟
                )
                
                # 执行快速 Nmap 扫描（仅 Top 100 端口）
                sse.send_tool_stream("nmap", "正在调用 HexStrike 执行快速 Nmap 扫描...")
                
                nmap_result = client.run_command("nmap_scan", {
                    "target": target,
                    "-F": True,  # 快速扫描（Top 100 端口）
                    "-T4": True,  # 激进时序
                    "--version-intensity": "0",  # 减少版本探测
                })
                
                if nmap_result.get("success"):
                    # 解析端口
                    ports = self._parse_nmap_ports(nmap_result["data"].get("stdout", ""))
                    scan_time = time.time() - start_time
                    
                    return {
                        "ports": ports,
                        "scan_time": scan_time,
                        "raw_output": nmap_result["data"].get("stdout", "")
                    }
                else:
                    logger.warning(f"HexStrike 快速扫描失败: {nmap_result.get('message')}")
                    # 回退到本地 nmap
                    
            except Exception as e:
                logger.error(f"HexStrike 调用失败: {e}，回退到本地 nmap")
        
        # 方案2: 回退到本地 nmap
        try:
            sse.send_tool_stream("nmap", "使用本地 nmap 执行快速扫描...")
            
            proc = await asyncio.create_subprocess_exec(
                "nmap", "-F", "-T4", "-oX", "-", target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), 
                timeout=60.0
            )
            
            ports = self._parse_nmap_ports(stdout.decode())
            scan_time = time.time() - start_time
            
            return {
                "ports": ports,
                "scan_time": scan_time,
                "raw_output": stdout.decode()
            }
            
        except asyncio.TimeoutError:
            logger.error(f"本地 nmap 超时: {target}")
            return {"ports": [], "scan_time": time.time() - start_time, "error": "超时"}
        except FileNotFoundError:
            logger.warning("nmap 未安装，返回空结果")
            return {"ports": [], "scan_time": 0, "error": "nmap 未安装"}
        except Exception as e:
            logger.error(f"本地 nmap 执行失败: {e}")
            return {"ports": [], "scan_time": time.time() - start_time, "error": str(e)}
    
    def _parse_nmap_ports(self, stdout: str) -> list:
        """从 nmap 输出中解析开放端口"""
        import re
        ports = []
        
        # 匹配端口行：<port protocol="tcp" portid="22"><state state="open"/>
        pattern = re.compile(r'portid="(\d+)".*?state="(\w+)"')
        
        for match in pattern.finditer(stdout):
            port_num = match.group(1)
            state = match.group(2)
            
            if state == "open":
                ports.append({
                    "port": port_num,
                    "protocol": "tcp",
                    "state": state
                })
        
        return ports
    
    async def _submit_full_scan_task(
        self, 
        target: str, 
        user_id: Optional[str]
    ) -> Optional[str]:
        """
        提交后台完整扫描任务
        
        Args:
            target: 目标地址
            user_id: 用户ID
            
        Returns:
            str: Celery 任务ID，失败返回 None
        """
        try:
            # 动态导入避免循环依赖
            from app.celery_tasks.hexstrike_tasks import full_hexstrike_scan
            
            # 提交 Celery 异步任务
            task = full_hexstrike_scan.delay(target, user_id)
            
            logger.info(f"已提交后台扫描任务: {task.id}, target={target}")
            return task.id
            
        except Exception as e:
            logger.error(f"提交后台扫描任务失败: {e}", exc_info=True)
            return None


# 创建工具实例
hexstrike_progressive_tool = HexStrikeProgressiveTool()
