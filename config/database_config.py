"""数据库配置

数据库连接池和会话管理配置。
"""

from typing import Optional
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    """数据库配置"""
    # 连接池配置
    pool_size: int = 20
    max_overflow: int = 10
    pool_recycle: int = 3600  # 连接回收时间（秒）
    pool_pre_ping: bool = True  # 连接前检查
    pool_timeout: int = 30  # 连接池获取连接超时（秒）

    # 会话配置
    autoflush: bool = False
    expire_on_commit: bool = False

    # 性能配置
    echo: bool = False  # SQL日志输出
    echo_pool: bool = False  # 连接池日志输出

    # Alembic配置
    alembic_script_location: str = "migrations"
    alembic_version_locations: str = "migrations/versions"

    # 迁移配置
    use_migrations: bool = True
    auto_create_tables: bool = False  # 生产环境应设为False


class RedisConfig(BaseModel):
    """Redis配置"""
    # 连接池配置
    max_connections: int = 10
    socket_connect_timeout: int = 5  # 连接超时（秒）
    socket_timeout: int = 5  # 套接字超时（秒）
    retry_on_timeout: bool = True
    health_check_interval: int = 30  # 健康检查间隔（秒）

    # 缓存配置
    default_ttl: int = 3600  # 默认缓存时间（秒）
    key_prefix: str = "aidev:"  # 缓存键前缀

    # 序列化配置
    encode_responses: bool = True
    decode_responses: bool = True


class VectorStoreConfig(BaseModel):
    """向量存储配置"""
    # ChromaDB配置
    persist_directory: str = "./chroma-data"
    collection_name: str = "knowledge_base"
    distance_function: str = "cosine"  # 距离函数：cosine, l2, ip

    # 嵌入配置
    embedding_dimension: int = 1536
    chunk_size: int = 1000  # 文本分块大小
    chunk_overlap: int = 200  # 分块重叠大小

    # 检索配置
    search_kwargs: dict = {"k": 5}  # 默认返回前5个结果
    filter_by_metadata: bool = True  # 是否使用元数据过滤


# 数据库配置实例
DATABASE_CONFIG = DatabaseConfig()
REDIS_CONFIG = RedisConfig()
VECTOR_STORE_CONFIG = VectorStoreConfig()