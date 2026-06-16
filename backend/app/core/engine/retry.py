"""容错重试机制"""

import asyncio
from typing import Callable, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0
    retry_on: tuple = (Exception,)


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        带重试的执行
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            函数返回值
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Operation succeeded after {attempt + 1} attempts")
                return result
                
            except self.config.retry_on as e:
                last_exception = e
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_retries} failed: {str(e)}"
                )
                
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (
                        self.config.backoff_factor ** attempt
                    )
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
        
        logger.error(
            f"All {self.config.max_retries} attempts failed"
        )
        raise last_exception


class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def classify_error(error: Exception) -> dict:
        """
        分类错误类型
        
        Returns:
            错误信息字典
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        # API 错误
        if "401" in error_msg or "Unauthorized" in error_msg:
            return {
                "type": "auth",
                "message": "API Key 无效或已过期",
                "suggestion": "请检查 API Key 配置"
            }
        
        if "429" in error_msg or "rate limit" in error_msg.lower():
            return {
                "type": "rate_limit",
                "message": "请求过于频繁",
                "suggestion": "请稍后再试"
            }
        
        if "404" in error_msg or "Not Found" in error_msg:
            return {
                "type": "not_found",
                "message": "资源不存在",
                "suggestion": "请检查模型 ID 和 URL"
            }
        
        # 网络错误
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            return {
                "type": "network",
                "message": "网络连接失败",
                "suggestion": "请检查网络连接"
            }
        
        # 代码执行错误
        if "SyntaxError" in error_type:
            return {
                "type": "syntax",
                "message": "代码语法错误",
                "suggestion": "请检查代码语法"
            }
        
        if "RuntimeError" in error_type or "NameError" in error_type:
            return {
                "type": "runtime",
                "message": "代码运行时错误",
                "suggestion": "请检查代码逻辑"
            }
        
        # 未知错误
        return {
            "type": "unknown",
            "message": f"{error_type}: {error_msg}",
            "suggestion": "请检查日志获取详细信息"
        }
