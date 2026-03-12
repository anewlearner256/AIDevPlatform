"""数据库模型定义

使用SQLAlchemy定义数据表结构。
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    Float,
    JSON,
    ForeignKey,
    Enum,
    Table,
    Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config.settings import settings
from config.database_config import DATABASE_CONFIG

# 创建基类
Base = declarative_base()

# 关联表
project_members = Table(
    'project_members',
    Base.metadata,
    Column('project_id', String, ForeignKey('projects.id'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('role', String(50), default='member'),
    Column('joined_at', DateTime, default=datetime.utcnow)
)

task_dependencies = Table(
    'task_dependencies',
    Base.metadata,
    Column('task_id', String, ForeignKey('tasks.id'), primary_key=True),
    Column('depends_on_id', String, ForeignKey('tasks.id'), primary_key=True)
)

class User(Base):
    """用户表"""
    __tablename__ = 'users'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    projects = relationship("Project", secondary=project_members, back_populates="members")
    tasks = relationship("Task", back_populates="assigned_user")

    def __repr__(self):
        return f"<User(id='{self.id}', username='{self.username}')>"


class Project(Base):
    """项目表"""
    __tablename__ = 'projects'
    __table_args__ = (
        Index('idx_project_status', 'status'),
        Index('idx_project_created', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    status = Column(String(50), default='active')  # active, archived, completed
    visibility = Column(String(50), default='private')  # private, public
    created_by = Column(String, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default=dict)  # 项目元数据

    # 关系
    owner = relationship("User", foreign_keys=[created_by])
    members = relationship("User", secondary=project_members, back_populates="projects")
    requirements = relationship("Requirement", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id='{self.id}', name='{self.name}')>"


class Requirement(Base):
    """需求表"""
    __tablename__ = 'requirements'
    __table_args__ = (
        Index('idx_requirement_project', 'project_id'),
        Index('idx_requirement_status', 'status'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id'), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    document_path = Column(String(500))  # 原始文档路径
    analysis_result = Column(JSON)  # 需求分析结果
    status = Column(String(50), default='pending')  # pending, analyzing, analyzed, failed
    priority = Column(String(50), default='medium')  # low, medium, high, critical
    created_by = Column(String, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default=dict)

    # 关系
    project = relationship("Project", back_populates="requirements")
    creator = relationship("User", foreign_keys=[created_by])
    tasks = relationship("Task", back_populates="requirement", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Requirement(id='{self.id}', title='{self.title[:50]}...')>"


class Task(Base):
    """任务表"""
    __tablename__ = 'tasks'
    __table_args__ = (
        Index('idx_task_project', 'project_id'),
        Index('idx_task_status', 'status'),
        Index('idx_task_priority', 'priority'),
        Index('idx_task_assigned', 'assigned_to'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id'), nullable=False, index=True)
    requirement_id = Column(String, ForeignKey('requirements.id'), index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    task_type = Column(String(50), default='development')  # development, review, test, deployment
    status = Column(String(50), default='pending')  # pending, in_progress, completed, failed, blocked
    priority = Column(String(50), default='medium')  # low, medium, high, critical
    estimated_hours = Column(Float, default=1.0)
    actual_hours = Column(Float, default=0.0)
    assigned_to = Column(String, ForeignKey('users.id'), index=True)
    due_date = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default=dict)

    # 关系
    project = relationship("Project", back_populates="tasks")
    requirement = relationship("Requirement", back_populates="tasks")
    assigned_user = relationship("User", back_populates="tasks")
    dependencies = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin=id == task_dependencies.c.task_id,
        secondaryjoin=id == task_dependencies.c.depends_on_id,
        backref="dependent_tasks"
    )
    executions = relationship("TaskExecution", back_populates="task", cascade="all, delete-orphan")
    code_artifacts = relationship("CodeArtifact", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Task(id='{self.id}', title='{self.title[:50]}...')>"


class TaskExecution(Base):
    """任务执行记录表"""
    __tablename__ = 'task_executions'
    __table_args__ = (
        Index('idx_execution_task', 'task_id'),
        Index('idx_execution_status', 'status'),
        Index('idx_execution_created', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False, index=True)
    execution_type = Column(String(50), default='auto')  # auto, manual
    status = Column(String(50), default='running')  # running, completed, failed, cancelled
    agent_type = Column(String(50))  # development, review, test, etc.
    input_data = Column(JSON)  # 执行输入
    output_data = Column(JSON)  # 执行输出
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    execution_time = Column(Float)  # 执行时间（秒）
    resource_usage = Column(JSON)  # 资源使用情况
    metadata = Column(JSON, default=dict)

    # 关系
    task = relationship("Task", back_populates="executions")

    def __repr__(self):
        return f"<TaskExecution(id='{self.id}', task_id='{self.task_id}', status='{self.status}')>"


class CodeArtifact(Base):
    """代码工件表"""
    __tablename__ = 'code_artifacts'
    __table_args__ = (
        Index('idx_artifact_task', 'task_id'),
        Index('idx_artifact_type', 'artifact_type'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False)  # source_code, test_code, config, documentation
    filename = Column(String(500))
    file_path = Column(String(1000))
    content = Column(Text)
    language = Column(String(50))
    checksum = Column(String(64))  # 文件校验和
    size = Column(Integer)  # 文件大小（字节）
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default=dict)

    # 关系
    task = relationship("Task", back_populates="code_artifacts")
    reviews = relationship("ReviewFeedback", back_populates="code_artifact", cascade="all, delete-orphan")
    test_results = relationship("TestResult", back_populates="code_artifact", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CodeArtifact(id='{self.id}', filename='{self.filename}')>"


class ReviewFeedback(Base):
    """评审反馈表"""
    __tablename__ = 'review_feedbacks'
    __table_args__ = (
        Index('idx_review_artifact', 'code_artifact_id'),
        Index('idx_review_created', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code_artifact_id = Column(String, ForeignKey('code_artifacts.id'), nullable=False, index=True)
    reviewer_type = Column(String(50), default='agent')  # agent, human
    reviewer_id = Column(String)  # 评审者ID（用户ID或智能体ID）
    review_result = Column(JSON)  # 评审结果
    score = Column(Float)  # 评分（0-100）
    issues = Column(JSON)  # 发现的问题
    suggestions = Column(JSON)  # 改进建议
    status = Column(String(50), default='completed')  # pending, in_progress, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default=dict)

    # 关系
    code_artifact = relationship("CodeArtifact", back_populates="reviews")

    def __repr__(self):
        return f"<ReviewFeedback(id='{self.id}', artifact_id='{self.code_artifact_id}')>"


class TestResult(Base):
    """测试结果表"""
    __tablename__ = 'test_results'
    __table_args__ = (
        Index('idx_test_artifact', 'code_artifact_id'),
        Index('idx_test_status', 'status'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code_artifact_id = Column(String, ForeignKey('code_artifacts.id'), nullable=False, index=True)
    test_type = Column(String(50), default='unit')  # unit, integration, system, performance
    test_framework = Column(String(50), default='pytest')
    test_result = Column(JSON)  # 测试结果
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    coverage_percentage = Column(Float)  # 测试覆盖率
    execution_time = Column(Float)  # 执行时间（秒）
    status = Column(String(50), default='completed')  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default=dict)

    # 关系
    code_artifact = relationship("CodeArtifact", back_populates="test_results")

    def __repr__(self):
        return f"<TestResult(id='{self.id}', artifact_id='{self.code_artifact_id}')>"


class ExecutionResult(Base):
    """执行结果表"""
    __tablename__ = 'execution_results'
    __table_args__ = (
        Index('idx_execution_task_execution', 'task_execution_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_execution_id = Column(String, ForeignKey('task_executions.id'), nullable=False, index=True)
    execution_output = Column(Text)  # 执行输出
    execution_error = Column(Text)  # 执行错误
    exit_code = Column(Integer)
    resource_usage = Column(JSON)  # 资源使用详情
    environment_snapshot = Column(JSON)  # 环境快照
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    task_execution = relationship("TaskExecution")

    def __repr__(self):
        return f"<ExecutionResult(id='{self.id}', execution_id='{self.task_execution_id}')>"


class KnowledgeDocument(Base):
    """知识库文档表（与RAG系统同步）"""
    __tablename__ = 'knowledge_documents'
    __table_args__ = (
        Index('idx_knowledge_document_type', 'document_type'),
        Index('idx_knowledge_project', 'project_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id'), index=True)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000))
    document_type = Column(String(50))  # requirement, design, api_doc, code, etc.
    content_hash = Column(String(64))  # 内容哈希
    chunk_count = Column(Integer, default=0)
    vector_store_ids = Column(JSON)  # 向量存储中的ID列表
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    project = relationship("Project")

    def __repr__(self):
        return f"<KnowledgeDocument(id='{self.id}', filename='{self.filename}')>"


class WorkflowState(Base):
    """工作流状态表"""
    __tablename__ = 'workflow_states'
    __table_args__ = (
        Index('idx_workflow_state_created', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state_data = Column(JSON, nullable=False)  # 工作流状态数据
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    executions = relationship("WorkflowExecution", back_populates="state", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkflowState(id='{self.id}')>"


class WorkflowExecution(Base):
    """工作流执行记录表"""
    __tablename__ = 'workflow_executions'
    __table_args__ = (
        Index('idx_workflow_execution_workflow', 'workflow_id'),
        Index('idx_workflow_execution_status', 'status'),
        Index('idx_workflow_execution_created', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)  # 工作流实例ID
    workflow_type = Column(String(100), nullable=False)  # 工作流类型
    state_id = Column(String, ForeignKey('workflow_states.id'), nullable=False, index=True)
    status = Column(String(50), default='pending')  # pending, running, completed, failed, paused, cancelled
    input_data = Column(JSON)  # 输入数据
    output_data = Column(JSON)  # 输出数据
    error_message = Column(Text)  # 错误信息
    metadata = Column(JSON, default=dict)  # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)  # 开始执行时间
    completed_at = Column(DateTime)  # 完成时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    state = relationship("WorkflowState", back_populates="executions")

    def __repr__(self):
        return f"<WorkflowExecution(id='{self.id}', workflow_id='{self.workflow_id}', status='{self.status}')>"


# 数据库引擎和会话管理
_async_engine = None
_async_session_local = None
_sync_engine = None
_sync_session_local = None

def get_async_engine():
    """获取异步数据库引擎"""
    global _async_engine
    if _async_engine is None:
        # 创建异步引擎
        db_url = str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://")
        _async_engine = create_async_engine(
            db_url,
            pool_size=DATABASE_CONFIG.pool_size,
            max_overflow=DATABASE_CONFIG.max_overflow,
            pool_recycle=DATABASE_CONFIG.pool_recycle,
            pool_pre_ping=DATABASE_CONFIG.pool_pre_ping,
            pool_timeout=DATABASE_CONFIG.pool_timeout,
            echo=DATABASE_CONFIG.echo,
            echo_pool=DATABASE_CONFIG.echo_pool,
        )
    return _async_engine

def get_async_session() -> async_sessionmaker[AsyncSession]:
    """获取异步会话工厂"""
    global _async_session_local
    if _async_session_local is None:
        engine = get_async_engine()
        _async_session_local = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=DATABASE_CONFIG.expire_on_commit,
            autoflush=DATABASE_CONFIG.autoflush,
        )
    return _async_session_local

def get_sync_engine():
    """获取同步数据库引擎（用于迁移等）"""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            str(settings.database_url),
            pool_size=DATABASE_CONFIG.pool_size,
            max_overflow=DATABASE_CONFIG.max_overflow,
            pool_recycle=DATABASE_CONFIG.pool_recycle,
            pool_pre_ping=DATABASE_CONFIG.pool_pre_ping,
            pool_timeout=DATABASE_CONFIG.pool_timeout,
            echo=DATABASE_CONFIG.echo,
            echo_pool=DATABASE_CONFIG.echo_pool,
        )
    return _sync_engine

def get_sync_session() -> sessionmaker[Session]:
    """获取同步会话工厂"""
    global _sync_session_local
    if _sync_session_local is None:
        engine = get_sync_engine()
        _sync_session_local = sessionmaker(
            engine,
            expire_on_commit=DATABASE_CONFIG.expire_on_commit,
            autoflush=DATABASE_CONFIG.autoflush,
        )
    return _sync_session_local

async def init_db():
    """初始化数据库连接池"""
    # 引擎会在首次访问时自动创建
    logger.info("数据库连接池初始化完成")

async def close_db():
    """关闭数据库连接"""
    global _async_engine, _sync_engine
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
    logger.info("数据库连接已关闭")