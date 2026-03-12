"""应用配置管理

使用Pydantic Settings管理环境变量和配置。
"""

from typing import List, Optional
from pydantic import Field, PostgresDsn, RedisDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    app_name: str = Field(default="AI自动开发平台", description="应用名称")
    app_env: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=True, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")
    secret_key: str = Field(default="your-secret-key-here-change-in-production", description="应用密钥")
    api_prefix: str = Field(default="/api/v1", description="API前缀")

    # 数据库配置
    database_url: PostgresDsn = Field(
        default="postgresql://user:password@localhost:5432/aidevplatform",
        description="PostgreSQL数据库连接URL"
    )
    database_test_url: Optional[PostgresDsn] = Field(
        default=None,
        description="测试数据库连接URL"
    )

    # Redis配置
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis连接URL"
    )
    redis_cache_ttl: int = Field(default=3600, description="Redis缓存TTL(秒)")

    # LLM配置
    claude_api_key: Optional[str] = Field(default=None, description="Claude API密钥")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", description="Claude模型")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API密钥")
    openai_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI模型")
    embedding_model: str = Field(default="text-embedding-3-small", description="嵌入模型")

    # 向量数据库配置
    chroma_persist_dir: str = Field(default="./chroma-data", description="ChromaDB持久化目录")
    chroma_collection_name: str = Field(default="knowledge_base", description="ChromaDB集合名称")

    # 执行引擎配置
    docker_network: str = Field(default="aidev-sandbox", description="Docker网络名称")
    execution_timeout: int = Field(default=300, description="执行超时时间(秒)")
    max_memory_limit: str = Field(default="1g", description="最大内存限制")
    max_cpu_limit: float = Field(default=1.0, description="最大CPU限制")

    # 任务队列配置
    celery_broker_url: RedisDsn = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL"
    )
    celery_result_backend: RedisDsn = Field(
        default="redis://localhost:6379/2",
        description="Celery结果后端URL"
    )

    # CORS配置
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="CORS允许的来源"
    )

    # 文件上传配置
    max_upload_size: int = Field(default=104857600, description="最大上传文件大小(字节)")
    upload_dir: str = Field(default="./uploads", description="上传文件目录")
    knowledge_base_dir: str = Field(default="./knowledge_base", description="知识库文档目录")

    # 计算属性
    @property
    def is_development(self) -> bool:
        """是否开发环境"""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        """是否测试环境"""
        return self.app_env == "testing"

    # 验证器
    @validator("database_test_url", pre=True)
    def set_database_test_url(cls, v, values):
        """设置测试数据库URL"""
        if v is None:
            # 如果没有提供测试URL，使用主数据库URL但修改数据库名
            db_url = values.get("database_url")
            if db_url:
                # 将数据库名修改为_test后缀
                db_str = str(db_url)
                if "/" in db_str:
                    parts = db_str.rsplit("/", 1)
                    return f"{parts[0]}/{parts[1]}_test"
        return v

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """解析CORS来源"""
        if isinstance(v, str):
            # 如果是以逗号分隔的字符串，转换为列表
            if v.startswith("[") and v.endswith("]"):
                # JSON数组格式
                import json
                return json.loads(v)
            else:
                return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        """Pydantic配置"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()