"""数据库种子数据脚本

向数据库添加初始数据，用于开发和测试。
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import uuid

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from models.database import (
    get_async_session,
    User,
    Project,
    Requirement,
    Task,
    KnowledgeDocument,
    WorkflowState,
    WorkflowExecution,
)
from config.settings import settings
import loguru

logger = loguru.logger

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_users(session: AsyncSession):
    """创建初始用户"""
    logger.info("开始创建用户种子数据...")

    users_data = [
        {
            "username": "admin",
            "email": "admin@aidevplatform.com",
            "full_name": "系统管理员",
            "password": "admin123",  # 生产环境应使用强密码
            "is_superuser": True,
            "is_active": True,
        },
        {
            "username": "developer",
            "email": "developer@aidevplatform.com",
            "full_name": "开发人员",
            "password": "dev123",
            "is_superuser": False,
            "is_active": True,
        },
        {
            "username": "tester",
            "email": "tester@aidevplatform.com",
            "full_name": "测试人员",
            "password": "test123",
            "is_superuser": False,
            "is_active": True,
        },
    ]

    created_count = 0
    for user_data in users_data:
        # 检查用户是否已存在
        existing_user = await session.execute(
            select(User).where(User.username == user_data["username"])
        )
        existing_user = existing_user.scalar_one_or_none()

        if existing_user:
            logger.info(f"用户已存在: {user_data['username']}")
            continue

        # 创建用户
        hashed_password = pwd_context.hash(user_data["password"])
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            hashed_password=hashed_password,
            is_superuser=user_data["is_superuser"],
            is_active=user_data["is_active"],
        )

        session.add(user)
        created_count += 1
        logger.info(f"创建用户: {user_data['username']}")

    await session.commit()
    logger.info(f"用户种子数据完成，创建了 {created_count} 个用户")

async def seed_projects(session: AsyncSession):
    """创建初始项目"""
    logger.info("开始创建项目种子数据...")

    # 获取管理员用户
    admin_result = await session.execute(
        select(User).where(User.username == "admin")
    )
    admin = admin_result.scalar_one_or_none()

    if not admin:
        logger.warning("未找到管理员用户，跳过项目创建")
        return

    projects_data = [
        {
            "name": "AI开发平台项目",
            "description": "AI自动开发平台的核心开发项目，用于验证平台功能。",
            "status": "active",
            "visibility": "private",
            "created_by": admin.id,
        },
        {
            "name": "示例Web应用",
            "description": "使用AI平台生成的示例Web应用程序，包含用户认证和CRUD功能。",
            "status": "active",
            "visibility": "public",
            "created_by": admin.id,
        },
        {
            "name": "API微服务项目",
            "description": "使用AI平台生成的REST API微服务，包含数据库集成和文档。",
            "status": "archived",
            "visibility": "private",
            "created_by": admin.id,
        },
    ]

    created_count = 0
    for project_data in projects_data:
        # 检查项目是否已存在
        existing_project = await session.execute(
            select(Project).where(Project.name == project_data["name"])
        )
        existing_project = existing_project.scalar_one_or_none()

        if existing_project:
            logger.info(f"项目已存在: {project_data['name']}")
            continue

        # 创建项目
        project = Project(
            name=project_data["name"],
            description=project_data["description"],
            status=project_data["status"],
            visibility=project_data["visibility"],
            created_by=project_data["created_by"],
            metadata={
                "seed_data": True,
                "seed_timestamp": datetime.utcnow().isoformat(),
            },
        )

        session.add(project)
        created_count += 1
        logger.info(f"创建项目: {project_data['name']}")

    await session.commit()
    logger.info(f"项目种子数据完成，创建了 {created_count} 个项目")

async def seed_requirements(session: AsyncSession):
    """创建初始需求"""
    logger.info("开始创建需求种子数据...")

    # 获取项目和用户
    project_result = await session.execute(
        select(Project).where(Project.name == "AI开发平台项目")
    )
    project = project_result.scalar_one_or_none()

    admin_result = await session.execute(
        select(User).where(User.username == "admin")
    )
    admin = admin_result.scalar_one_or_none()

    if not project or not admin:
        logger.warning("未找到项目或管理员用户，跳过需求创建")
        return

    requirements_data = [
        {
            "title": "需求分析功能",
            "description": "实现需求文档上传、分析和结构化功能。支持多种文档格式（PDF、Markdown、Word等）。",
            "priority": "high",
            "status": "analyzed",
            "analysis_result": {
                "core_objectives": [
                    "实现文档上传和存储",
                    "提取需求文本并分析",
                    "生成结构化需求规格",
                    "支持多种文档格式"
                ],
                "features": [
                    "文件上传接口",
                    "文档解析器",
                    "需求分析智能体",
                    "结果存储和检索"
                ],
                "technical_constraints": ["支持最大100MB文件", "处理时间小于30秒"],
                "assumptions": ["文档格式正确", "网络连接稳定"],
                "suggested_tech_stack": ["Python", "FastAPI", "ChromaDB", "OpenAI API"]
            },
        },
        {
            "title": "任务规划功能",
            "description": "将结构化需求分解为具体开发任务，分析任务依赖关系和优先级。",
            "priority": "medium",
            "status": "pending",
        },
        {
            "title": "代码生成功能",
            "description": "根据任务描述生成对应编程语言的代码，支持多种编程语言和框架。",
            "priority": "high",
            "status": "pending",
        },
    ]

    created_count = 0
    for req_data in requirements_data:
        # 检查需求是否已存在
        existing_req = await session.execute(
            select(Requirement).where(
                Requirement.title == req_data["title"],
                Requirement.project_id == project.id
            )
        )
        existing_req = existing_req.scalar_one_or_none()

        if existing_req:
            logger.info(f"需求已存在: {req_data['title']}")
            continue

        # 创建需求
        requirement = Requirement(
            project_id=project.id,
            title=req_data["title"],
            description=req_data["description"],
            priority=req_data["priority"],
            status=req_data["status"],
            created_by=admin.id,
            analysis_result=req_data.get("analysis_result"),
            metadata={
                "seed_data": True,
                "seed_timestamp": datetime.utcnow().isoformat(),
            },
        )

        session.add(requirement)
        created_count += 1
        logger.info(f"创建需求: {req_data['title']}")

    await session.commit()
    logger.info(f"需求种子数据完成，创建了 {created_count} 个需求")

async def seed_tasks(session: AsyncSession):
    """创建初始任务"""
    logger.info("开始创建任务种子数据...")

    # 获取项目、需求和用户
    project_result = await session.execute(
        select(Project).where(Project.name == "AI开发平台项目")
    )
    project = project_result.scalar_one_or_none()

    req_result = await session.execute(
        select(Requirement).where(Requirement.title == "需求分析功能")
    )
    requirement = req_result.scalar_one_or_none()

    dev_result = await session.execute(
        select(User).where(User.username == "developer")
    )
    developer = dev_result.scalar_one_or_none()

    if not project or not requirement or not developer:
        logger.warning("未找到项目、需求或开发人员，跳过任务创建")
        return

    tasks_data = [
        {
            "title": "实现文档上传API",
            "description": "创建支持多种文件格式的上传接口，包含文件验证和存储功能。",
            "task_type": "development",
            "priority": "high",
            "estimated_hours": 4.0,
            "assigned_to": developer.id,
        },
        {
            "title": "集成文档解析库",
            "description": "集成PyPDF2、python-docx等库，支持PDF、Word、Markdown文档解析。",
            "task_type": "development",
            "priority": "medium",
            "estimated_hours": 6.0,
            "assigned_to": developer.id,
        },
        {
            "title": "实现需求分析智能体",
            "description": "使用LLM API实现需求分析智能体，能够从文档中提取结构化需求。",
            "task_type": "development",
            "priority": "high",
            "estimated_hours": 8.0,
            "assigned_to": developer.id,
        },
    ]

    created_count = 0
    for task_data in tasks_data:
        # 检查任务是否已存在
        existing_task = await session.execute(
            select(Task).where(
                Task.title == task_data["title"],
                Task.project_id == project.id
            )
        )
        existing_task = existing_task.scalar_one_or_none()

        if existing_task:
            logger.info(f"任务已存在: {task_data['title']}")
            continue

        # 创建任务
        task = Task(
            project_id=project.id,
            requirement_id=requirement.id,
            title=task_data["title"],
            description=task_data["description"],
            task_type=task_data["task_type"],
            priority=task_data["priority"],
            estimated_hours=task_data["estimated_hours"],
            assigned_to=task_data["assigned_to"],
            status="pending",
            metadata={
                "seed_data": True,
                "seed_timestamp": datetime.utcnow().isoformat(),
            },
        )

        session.add(task)
        created_count += 1
        logger.info(f"创建任务: {task_data['title']}")

    await session.commit()
    logger.info(f"任务种子数据完成，创建了 {created_count} 个任务")

async def seed_knowledge_documents(session: AsyncSession):
    """创建初始知识库文档"""
    logger.info("开始创建知识库文档种子数据...")

    # 获取项目
    project_result = await session.execute(
        select(Project).where(Project.name == "AI开发平台项目")
    )
    project = project_result.scalar_one_or_none()

    if not project:
        logger.warning("未找到项目，跳过知识库文档创建")
        return

    documents_data = [
        {
            "filename": "需求分析指南.md",
            "document_type": "guideline",
            "content_hash": "sample_hash_1",
            "chunk_count": 0,
        },
        {
            "filename": "API设计规范.pdf",
            "document_type": "specification",
            "content_hash": "sample_hash_2",
            "chunk_count": 0,
        },
        {
            "filename": "代码评审标准.docx",
            "document_type": "standard",
            "content_hash": "sample_hash_3",
            "chunk_count": 0,
        },
    ]

    created_count = 0
    for doc_data in documents_data:
        # 检查文档是否已存在
        existing_doc = await session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.filename == doc_data["filename"],
                KnowledgeDocument.project_id == project.id
            )
        )
        existing_doc = existing_doc.scalar_one_or_none()

        if existing_doc:
            logger.info(f"知识库文档已存在: {doc_data['filename']}")
            continue

        # 创建文档
        document = KnowledgeDocument(
            project_id=project.id,
            filename=doc_data["filename"],
            document_type=doc_data["document_type"],
            content_hash=doc_data["content_hash"],
            chunk_count=doc_data["chunk_count"],
            metadata={
                "seed_data": True,
                "seed_timestamp": datetime.utcnow().isoformat(),
                "description": f"示例{doc_data['document_type']}文档",
            },
        )

        session.add(document)
        created_count += 1
        logger.info(f"创建知识库文档: {doc_data['filename']}")

    await session.commit()
    logger.info(f"知识库文档种子数据完成，创建了 {created_count} 个文档")

async def seed_all():
    """执行所有种子数据创建"""
    logger.info("开始数据库种子数据初始化...")

    try:
        session_factory = get_async_session()
        async with session_factory() as session:
            # 开始事务
            async with session.begin():
                await seed_users(session)
                await seed_projects(session)
                await seed_requirements(session)
                await seed_tasks(session)
                await seed_knowledge_documents(session)

        logger.info("数据库种子数据初始化完成")
        return True

    except Exception as e:
        logger.error(f"数据库种子数据初始化失败: {str(e)}")
        return False

async def clear_seed_data():
    """清除种子数据（仅用于开发和测试）"""
    logger.warning("开始清除种子数据...")

    try:
        session_factory = get_async_session()
        async with session_factory() as session:
            # 注意：这将删除所有标记为种子数据的记录
            # 在实际应用中可能需要更精确的删除逻辑

            # 删除知识库文档
            result = await session.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.metadata["seed_data"].as_boolean() == True
                )
            )
            docs = result.scalars().all()
            for doc in docs:
                await session.delete(doc)

            # 删除任务
            result = await session.execute(
                select(Task).where(
                    Task.metadata["seed_data"].as_boolean() == True
                )
            )
            tasks = result.scalars().all()
            for task in tasks:
                await session.delete(task)

            # 删除需求
            result = await session.execute(
                select(Requirement).where(
                    Requirement.metadata["seed_data"].as_boolean() == True
                )
            )
            requirements = result.scalars().all()
            for req in requirements:
                await session.delete(req)

            # 删除项目（谨慎操作）
            result = await session.execute(
                select(Project).where(
                    Project.metadata["seed_data"].as_boolean() == True
                )
            )
            projects = result.scalars().all()
            for project in projects:
                await session.delete(project)

            # 保留用户，因为他们可能被其他数据引用

            await session.commit()

        logger.warning("种子数据清除完成")
        return True

    except Exception as e:
        logger.error(f"清除种子数据失败: {str(e)}")
        return False

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库种子数据工具")
    parser.add_argument("--action", choices=["seed", "clear"], default="seed", help="执行的操作")

    args = parser.parse_args()

    if args.action == "seed":
        success = asyncio.run(seed_all())
    elif args.action == "clear":
        success = asyncio.run(clear_seed_data())

    if success:
        logger.info(f"操作 '{args.action}' 完成")
        sys.exit(0)
    else:
        logger.error(f"操作 '{args.action}' 失败")
        sys.exit(1)

if __name__ == "__main__":
    main()