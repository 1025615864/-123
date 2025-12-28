"""日志配置"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    app_name: str = "baixing_law"
) -> None:
    """
    配置日志系统
    
    Args:
        log_level: 日志级别
        log_dir: 日志目录
        app_name: 应用名称
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 日志格式
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)
    
    # 文件处理器 - 普通日志
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        log_path / f"{app_name}_{today}.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(file_handler)
    
    # 文件处理器 - 错误日志
    error_handler = logging.FileHandler(
        log_path / f"{app_name}_error_{today}.log",
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(error_handler)
    
    # 降低第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    logging.info("Logging configured: level=%s, dir=%s", log_level, log_dir)


class RequestLogger:
    """请求日志记录器"""
    
    def __init__(self, logger_name: str = "api"):
        self.logger = logging.getLogger(logger_name)
    
    def log_request(
        self,
        method: str,
        path: str,
        user_id: int | None = None,
        ip: str | None = None,
        extra: dict[str, object] | None = None
    ) -> None:
        """记录请求"""
        msg = f"REQUEST {method} {path}"
        if user_id:
            msg += f" user={user_id}"
        if ip:
            msg += f" ip={ip}"
        if extra:
            msg += f" {extra}"
        self.logger.info(msg)
    
    def log_response(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: int | None = None
    ) -> None:
        """记录响应"""
        msg = f"RESPONSE {method} {path} status={status_code} duration={duration_ms:.2f}ms"
        if user_id:
            msg += f" user={user_id}"
        
        if status_code >= 500:
            self.logger.error(msg)
        elif status_code >= 400:
            self.logger.warning(msg)
        else:
            self.logger.info(msg)
    
    def log_error(
        self,
        method: str,
        path: str,
        error: str,
        user_id: int | None = None,
        traceback: str | None = None
    ) -> None:
        """记录错误"""
        msg = f"ERROR {method} {path} error={error}"
        if user_id:
            msg += f" user={user_id}"
        if traceback:
            msg += f"\n{traceback}"
        self.logger.error(msg)


# 单例实例
request_logger = RequestLogger()
