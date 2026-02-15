"""
HexStrike Celery 异步任务
用于后台执行长时间扫描操作
"""
import logging
import time
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from app.services.hexstrike_client import HexStrikeClient
from app.utils.sse_manager import SSEManager
from app.models import HexStrikeExecution

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def full_hexstrike_scan(self, target: str, user_id: str = None):
    """
    后台执行完整 HexStrike 扫描
    
    特点：
    1. 异步执行，不阻塞用户交互
    2. 实时推送进度（通过 SSE）
    3. 自动生成 PDF 报告
    4. 保存执行记录到数据库
    
    Args:
        target: 扫描目标
        user_id: 用户ID（用于进度推送）
        
    Returns:
        Dict: 扫描结果
    """
    # 创建执行记录
    execution = HexStrikeExecution.objects.create(
        target=target,
        analysis_type='comprehensive',
        status='running',
        created_by=user_id or '',
    )
    
    # 初始化 SSE 管理器
    channel = f"user_{user_id}" if user_id else "scan_progress"
    sse = SSEManager(channel)
    
    start_time = time.time()
    
    try:
        # ========== 阶段1: Nmap 端口扫描 ==========
        self.update_state(state='PROGRESS', meta={'stage': 'nmap', 'progress': 10})
        sse.send_progress("nmap", 10, f"🔍 开始 Nmap 端口扫描: {target}")
        logger.info(f"[后台任务] 开始 Nmap 扫描: {target}")
        
        client = HexStrikeClient(
            base_url=getattr(settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888'),
            timeout=600,  # 10 分钟
        )
        
        nmap_result = client.run_command("nmap_scan", {
            "target": target,
            "-sV": True,  # 版本检测
            "-O": True,   # OS 检测
        })
        
        if nmap_result.get("success"):
            self.update_state(state='PROGRESS', meta={'stage': 'nmap_done', 'progress': 40})
            sse.send_progress("nmap_done", 40, "✅ Nmap 扫描完成")
            
            # 推送 Nmap 结果
            sse.publish({
                "type": "nmap_complete",
                "message": "Nmap 扫描完成",
                "data": nmap_result.get("data", {})
            })
        else:
            logger.error(f"Nmap 扫描失败: {nmap_result.get('message')}")
            sse.send_error(f"Nmap 扫描失败: {nmap_result.get('message')}", "nmap")
        
        # ========== 阶段2: Nuclei 漏洞扫描 ==========
        self.update_state(state='PROGRESS', meta={'stage': 'nuclei', 'progress': 50})
        sse.send_progress("nuclei", 50, "🔍 开始 Nuclei 漏洞扫描...")
        logger.info(f"[后台任务] 开始 Nuclei 扫描: {target}")
        
        nuclei_result = client.run_command("nuclei_scan", {
            "target": target,
            "severity": "critical,high,medium",  # 只扫描高危以上
            "-rl": "50",  # 限制速率
            "-c": "10",   # 限制并发
            "-timeout": "10",
        })
        
        if nuclei_result.get("success"):
            self.update_state(state='PROGRESS', meta={'stage': 'nuclei_done', 'progress': 80})
            sse.send_progress("nuclei_done", 80, "✅ Nuclei 扫描完成")
            
            # 推送 Nuclei 结果
            sse.publish({
                "type": "nuclei_complete",
                "message": "Nuclei 扫描完成",
                "data": nuclei_result.get("data", {})
            })
        else:
            logger.error(f"Nuclei 扫描失败: {nuclei_result.get('message')}")
            sse.send_error(f"Nuclei 扫描失败: {nuclei_result.get('message')}", "nuclei")
        
        # ========== 阶段3: 生成 PDF 报告 ==========
        self.update_state(state='PROGRESS', meta={'stage': 'report', 'progress': 90})
        sse.send_progress("report", 90, "📄 正在生成 PDF 报告...")
        logger.info(f"[后台任务] 生成 PDF 报告: {target}")
        
        from app.services.hexstrike_pdf_reporter import HexStrikePDFReporter
        
        reporter = HexStrikePDFReporter()
        pdf_file = reporter.generate_pdf_report(
            target=target,
            nmap_results=nmap_result.get("data"),
            nuclei_results=nuclei_result.get("data"),
        )
        
        if pdf_file:
            sse.send_progress("report_done", 100, f"✅ PDF 报告生成成功: {pdf_file}")
            logger.info(f"[后台任务] PDF 报告生成成功: {pdf_file}")
        else:
            logger.warning("[后台任务] PDF 报告生成失败")
        
        # ========== 完成 ==========
        execution_time = time.time() - start_time
        
        # 更新执行记录
        execution.status = 'success'
        execution.finished_at = timezone.now()
        execution.execution_time = execution_time
        execution.result = {
            "nmap": nmap_result.get("data"),
            "nuclei": nuclei_result.get("data"),
            "pdf_file": pdf_file
        }
        execution.save()
        
        # 发送完成通知
        sse.send_complete({
            "message": "✅ 完整扫描完成！",
            "execution_id": execution.id,
            "execution_time": execution_time,
            "pdf_file": pdf_file,
            "target": target
        })
        
        self.update_state(state='SUCCESS', meta={
            'stage': 'complete',
            'progress': 100,
            'execution_id': execution.id,
            'pdf_file': pdf_file
        })
        
        logger.info(f"[后台任务] 扫描完成: {target}, 耗时: {execution_time:.2f}秒")
        
        return {
            "success": True,
            "execution_id": execution.id,
            "target": target,
            "nmap_result": nmap_result.get("data"),
            "nuclei_result": nuclei_result.get("data"),
            "pdf_file": pdf_file,
            "execution_time": execution_time
        }
        
    except Exception as e:
        # 更新为失败状态
        execution_time = time.time() - start_time
        execution.status = 'failed'
        execution.finished_at = timezone.now()
        execution.execution_time = execution_time
        execution.error_message = str(e)
        execution.save()
        
        logger.error(f"[后台任务] 扫描失败: {e}", exc_info=True)
        
        sse.send_error(f"扫描失败: {str(e)}", "full_scan")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        
        return {
            "success": False,
            "error": str(e),
            "execution_id": execution.id
        }
