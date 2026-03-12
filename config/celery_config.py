"""Celery配置

配置Celery应用，包括任务队列、结果后端和任务路由。
"""

import os
from celery import Celery
from kombu import Queue, Exchange
from config.settings import settings

# 创建Celery应用实例
app = Celery(
    'aidevplatform',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['tasks.celery_tasks']  # 包含的任务模块
)

# 基础配置
app.conf.update(
    # 任务序列化格式
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # 时区设置
    timezone='Asia/Shanghai',
    enable_utc=True,

    # 任务跟踪
    task_track_started=True,
    task_send_sent_event=True,

    # 结果过期时间（24小时）
    result_expires=24 * 3600,

    # 工作进程配置
    worker_prefetch_multiplier=1,  # 每个工作进程每次只取一个任务
    worker_max_tasks_per_child=100,  # 每个工作进程处理100个任务后重启
    worker_max_memory_per_child=200000,  # 200MB内存限制

    # 任务超时设置
    task_time_limit=1800,  # 30分钟
    task_soft_time_limit=1500,  # 25分钟

    # 重试配置
    task_acks_late=True,  # 任务完成后确认
    task_reject_on_worker_lost=True,  # 工作进程丢失时拒绝任务

    # 任务路由和队列配置
    task_routes={
        # 高优先级任务
        'tasks.celery_tasks.execute_high_priority_workflow': {'queue': 'high_priority'},
        'tasks.celery_tasks.process_requirement_analysis': {'queue': 'high_priority'},

        # 中优先级任务
        'tasks.celery_tasks.execute_standard_workflow': {'queue': 'standard'},
        'tasks.celery_tasks.process_task_execution': {'queue': 'standard'},

        # 低优先级任务
        'tasks.celery_tasks.execute_background_workflow': {'queue': 'low_priority'},
        'tasks.celery_tasks.cleanup_old_tasks': {'queue': 'low_priority'},
    },

    # 队列定义
    task_queues=(
        Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
        Queue('standard', Exchange('standard'), routing_key='standard'),
        Queue('low_priority', Exchange('low_priority'), routing_key='low_priority'),
    ),

    # 默认队列
    task_default_queue='standard',
    task_default_exchange='standard',
    task_default_routing_key='standard',

    # 定时任务（beat）配置
    beat_schedule={
        # 每5分钟检查一次待处理任务
        'check-pending-tasks': {
            'task': 'tasks.celery_tasks.check_pending_tasks',
            'schedule': 300.0,  # 300秒 = 5分钟
        },
        # 每小时清理一次旧任务
        'cleanup-old-tasks': {
            'task': 'tasks.celery_tasks.cleanup_old_tasks',
            'schedule': 3600.0,  # 3600秒 = 1小时
        },
        # 每30分钟监控工作流状态
        'monitor-workflows': {
            'task': 'tasks.celery_tasks.monitor_workflows',
            'schedule': 1800.0,  # 1800秒 = 30分钟
        },
    },

    # Redis作为broker的特定配置
    broker_transport_options={
        'visibility_timeout': 1800,  # 30分钟
        'fanout_prefix': True,
        'fanout_patterns': True,
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
        'retry_on_timeout': True,
        'max_connections': 10,
    },

    # 结果后端配置
    redis_backend_use_ssl=False,
    redis_max_connections=10,
)

# 根据环境调整配置
if settings.is_development:
    app.conf.update(
        # 开发环境：更宽松的限制
        worker_concurrency=2,
        worker_prefetch_multiplier=2,
        task_time_limit=3600,  # 1小时
        task_soft_time_limit=3300,  # 55分钟
    )
elif settings.is_production:
    app.conf.update(
        # 生产环境：更严格的限制
        worker_concurrency=os.cpu_count() or 4,
        worker_prefetch_multiplier=1,
        task_time_limit=1800,  # 30分钟
        task_soft_time_limit=1500,  # 25分钟
        broker_transport_options={
            'visibility_timeout': 3600,  # 1小时
            'socket_connect_timeout': 10,
            'socket_timeout': 10,
            'retry_on_timeout': True,
            'max_connections': 20,
        },
    )

# 任务事件配置
if settings.is_development:
    app.conf.worker_send_task_events = True
    app.conf.task_send_sent_event = True

# 监控配置
app.conf.worker_enable_remote_control = True
app.conf.worker_pool_restarts = True

# 导入任务模块
app.autodiscover_tasks(['tasks'])

if __name__ == '__main__':
    app.start()