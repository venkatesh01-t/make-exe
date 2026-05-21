"""
Centralized logging system for Clinic Desktop Application.
Handles file and console logging with rotation.
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging of errors."""

    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logger(log_path: Path, app_name: str = 'Clinic') -> logging.Logger:
    """Configure logging to both file and console."""
    log_path.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / f'{app_name.lower()}.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger('Clinic.' + name if name else 'Clinic')
