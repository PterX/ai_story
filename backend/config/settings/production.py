"""
生产环境配置
"""

from .base import *

DEBUG = False
ALLOWED_HOSTS = ['*']

# CORS配置 - 按需放开来源
CORS_ALLOW_ALL_ORIGINS = True

# 数据库 - 默认使用SQLite，提供 MySQL 环境变量时自动切换
DATABASES = build_database_config()

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
