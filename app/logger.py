import logging
import os
from logging.handlers import RotatingFileHandler

# 建立 logs 目錄（如果不存在）
log_directory = 'logs'
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# 設置 logger
def get_logger(name='app'):
    logger = logging.getLogger(name)
    
    # 如果 logger 已經有處理器，則直接返回（避免重複配置）
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # 終端輸出格式
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    
    # 檔案輸出格式（使用 RotatingFileHandler 進行日誌輪替）
    file_handler = RotatingFileHandler(
        os.path.join(log_directory, f'{name}.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    
    # 添加處理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# 預設 logger 實例
logger = get_logger()