"""Pydantic模型

API请求和响应的数据模型，与数据库模型分离。
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid


# 基础模型
class BaseSchema(BaseModel):
    """基础模式"""
    class Config:
        from_attributes = True  # 替换orm_mode
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v) if v else None,
        }


# 用户相关
class UserBase(BaseSchema):
    """用户基础信息"""
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    full_name: Optional[str] = Field(None, max_length=200)


class UserCreate(UserBase):
    """创建用户"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseSchema):
    """更新用户"""
    email: Optional[str] = Field(None, regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    full_name: Optional[str] = Field(None, max_length=200)
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    """用户响应"""
    id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 项目相关
class ProjectBase(BaseSchema):
    """项目基础信息"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    visibility: str = Field("private", regex="^(private|public)$")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectCreate(ProjectBase):
    """创建项目"""
    pass


class ProjectUpdate(BaseSchema):
    """更新项目"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(active|archived|completed)$")
    visibility: Optional[str] = Field(None, regex="^(private|public)$")
    metadata: Optional[Dict[str, Any]] = None


class ProjectResponse(ProjectBase):
    """项目响应"""
    id: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


# 需求相关
class RequirementBase(BaseSchema):
    """需求基础信息"""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = Field("medium", regex="^(low|medium|high|critical)$")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RequirementCreate(RequirementBase):
    """创建需求"""
    project_id: str
    document_path: Optional[str] = None


class RequirementUpdate(BaseSchema):
    """更新需求"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(pending|analyzing|analyzed|failed)$")
    priority: Optional[str] = Field(None, regex="^(low|medium|high|critical)$")
    analysis_result: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class RequirementResponse(RequirementBase):
    """需求响应"""
    id: str
    project_id: str
    document_path: Optional[str]
    analysis_result: Optional[Dict[str, Any]]
    status: str
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


# 任务相关
class TaskBase(BaseSchema):
    """任务基础信息"""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    task_type: str = Field("development", regex="^(development|review|test|deployment)$")
    priority: str = Field("medium", regex="^(low|medium|high|critical)$")
    estimated_hours: float = Field(1.0, ge=0.0)
    due_date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskCreate(TaskBase):
    """创建任务"""
    project_id: str
    requirement_id: Optional[str] = None
    assigned_to: Optional[str] = None
    dependencies: Optional[List[str]] = Field(default_factory=list)


class TaskUpdate(BaseSchema):
    """更新任务"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = Field(
        None,
        regex="^(pending|in_progress|completed|failed|blocked)$"
    )
    priority: Optional[str] = Field(None, regex="^(low|medium|high|critical)$")
    estimated_hours: Optional[float] = Field(None, ge=0.0)
    actual_hours: Optional[float] = Field(None, ge=0.0)
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskResponse(TaskBase):
    """任务响应"""
    id: str
    project_id: str
    requirement_id: Optional[str]
    status: str
    assigned_to: Optional[str]
    actual_hours: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    dependencies: List[str] = Field(default_factory=list)


# 任务执行相关
class TaskExecutionBase(BaseSchema):
    """任务执行基础信息"""
    execution_type: str = Field("auto", regex="^(auto|manual)$")
    agent_type: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskExecutionCreate(TaskExecutionBase):
    """创建任务执行"""
    task_id: str


class TaskExecutionUpdate(BaseSchema):
    """更新任务执行"""
    status: Optional[str] = Field(
        None,
        regex="^(running|completed|failed|cancelled)$"
    )
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = Field(None, ge=0.0)
    resource_usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskExecutionResponse(TaskExecutionBase):
    """任务执行响应"""
    id: str
    task_id: str
    status: str
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    execution_time: Optional[float]
    resource_usage: Optional[Dict[str, Any]]


# 代码工件相关
class CodeArtifactBase(BaseSchema):
    """代码工件基础信息"""
    artifact_type: str = Field(
        ...,
        regex="^(source_code|test_code|config|documentation)$"
    )
    filename: str = Field(..., min_length=1, max_length=500)
    file_path: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CodeArtifactCreate(CodeArtifactBase):
    """创建代码工件"""
    task_id: str


class CodeArtifactUpdate(BaseSchema):
    """更新代码工件"""
    content: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CodeArtifactResponse(CodeArtifactBase):
    """代码工件响应"""
    id: str
    task_id: str
    checksum: Optional[str]
    size: Optional[int]
    created_at: datetime


# 评审反馈相关
class ReviewFeedbackBase(BaseSchema):
    """评审反馈基础信息"""
    reviewer_type: str = Field("agent", regex="^(agent|human)$")
    review_result: Dict[str, Any] = Field(default_factory=dict)
    score: Optional[float] = Field(None, ge=0.0, le=100.0)
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewFeedbackCreate(ReviewFeedbackBase):
    """创建评审反馈"""
    code_artifact_id: str
    reviewer_id: Optional[str] = None


class ReviewFeedbackUpdate(BaseSchema):
    """更新评审反馈"""
    review_result: Optional[Dict[str, Any]] = None
    score: Optional[float] = Field(None, ge=0.0, le=100.0)
    issues: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = Field(None, regex="^(pending|in_progress|completed)$")
    metadata: Optional[Dict[str, Any]] = None


class ReviewFeedbackResponse(ReviewFeedbackBase):
    """评审反馈响应"""
    id: str
    code_artifact_id: str
    reviewer_id: Optional[str]
    status: str
    created_at: datetime


# 测试结果相关
class TestResultBase(BaseSchema):
    """测试结果基础信息"""
    test_type: str = Field("unit", regex="^(unit|integration|system|performance)$")
    test_framework: str = Field("pytest", regex="^(pytest|unittest|jest|mocha)$")
    test_result: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TestResultCreate(TestResultBase):
    """创建测试结果"""
    code_artifact_id: str


class TestResultUpdate(BaseSchema):
    """更新测试结果"""
    test_result: Optional[Dict[str, Any]] = None
    passed_count: Optional[int] = Field(None, ge=0)
    failed_count: Optional[int] = Field(None, ge=0)
    skipped_count: Optional[int] = Field(None, ge=0)
    total_count: Optional[int] = Field(None, ge=0)
    coverage_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    execution_time: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = Field(None, regex="^(pending|running|completed|failed)$")
    metadata: Optional[Dict[str, Any]] = None


class TestResultResponse(TestResultBase):
    """测试结果响应"""
    id: str
    code_artifact_id: str
    passed_count: int
    failed_count: int
    skipped_count: int
    total_count: int
    coverage_percentage: Optional[float]
    execution_time: Optional[float]
    status: str
    created_at: datetime


# 知识库文档相关
class KnowledgeDocumentBase(BaseSchema):
    """知识库文档基础信息"""
    filename: str = Field(..., min_length=1, max_length=500)
    document_type: Optional[str] = Field(
        None,
        regex="^(requirement|design|api_doc|code|manual|other)$"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    """创建知识库文档"""
    project_id: Optional[str] = None
    file_path: Optional[str] = None


class KnowledgeDocumentUpdate(BaseSchema):
    """更新知识库文档"""
    document_type: Optional[str] = Field(
        None,
        regex="^(requirement|design|api_doc|code|manual|other)$"
    )
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeDocumentResponse(KnowledgeDocumentBase):
    """知识库文档响应"""
    id: str
    project_id: Optional[str]
    file_path: Optional[str]
    content_hash: Optional[str]
    chunk_count: int
    vector_store_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# API响应包装
class PaginatedResponse(BaseSchema):
    """分页响应"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class SuccessResponse(BaseSchema):
    """成功响应"""
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseSchema):
    """错误响应"""
    error: str
    detail: Optional[str] = None
    code: Optional[int] = None


# 文档上传相关
class DocumentUploadResponse(BaseSchema):
    """文档上传响应"""
    document_id: str
    filename: str
    message: str
    chunk_count: int


class RequirementAnalysisResponse(BaseSchema):
    """需求分析响应"""
    task_id: str
    message: str
    status: str


# 知识检索相关
class KnowledgeRetrievalRequest(BaseSchema):
    """知识检索请求"""
    query: str = Field(..., min_length=1, max_length=1000)
    n_results: int = Field(5, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    use_hybrid: bool = True
    rerank: bool = True


class RetrievalResultResponse(BaseSchema):
    """检索结果响应"""
    document_id: str
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    relevance_score: float
    retrieval_method: str


class KnowledgeRetrievalResponse(BaseSchema):
    """知识检索响应"""
    query: str
    results: List[RetrievalResultResponse]
    total_results: int


# 智能体相关
class AgentRequest(BaseSchema):
    """智能体请求"""
    input_data: Dict[str, Any] = Field(default_factory=dict)
    agent_type: str = Field(
        ...,
        regex="^(requirement|task_planner|development|review|test)$"
    )
    config_overrides: Optional[Dict[str, Any]] = None


class AgentResponse(BaseSchema):
    """智能体响应"""
    agent_type: str
    output_data: Dict[str, Any]
    execution_time: float
    status: str


# 统计信息
class StatisticsResponse(BaseSchema):
    """统计信息响应"""
    total_projects: int
    total_requirements: int
    total_tasks: int
    total_executions: int
    total_documents: int
    active_tasks_by_type: Dict[str, int]
    completion_rate: float
    avg_execution_time: float