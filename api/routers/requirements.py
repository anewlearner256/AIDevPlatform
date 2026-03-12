"""需求管理API

处理需求文档上传、分析和需求智能体交互。
"""

from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import loguru

from config.settings import settings
from services.requirement_service import RequirementService
from models.schemas import (
    RequirementCreate,
    RequirementResponse,
    RequirementAnalysisResponse,
    DocumentUploadResponse
)

logger = loguru.logger
router = APIRouter()

# 初始化服务
requirement_service = RequirementService()

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    document_type: str = Form("requirement")
):
    """
    上传需求文档

    支持PDF、Markdown、Word、文本等格式。
    文档将存储在知识库中并建立索引。
    """
    try:
        # 验证文件类型
        allowed_types = [".pdf", ".md", ".txt", ".docx", ".json", ".yaml", ".yml"]
        file_extension = file.filename.lower().split(".")[-1] if "." in file.filename else ""

        if f".{file_extension}" not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型。支持的类型: {', '.join(allowed_types)}"
            )

        # 验证文件大小
        content = await file.read()
        if len(content) > settings.max_upload_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制 ({settings.max_upload_size}字节)"
            )

        # 处理文档
        result = await requirement_service.process_document(
            content=content,
            filename=file.filename,
            project_id=project_id,
            document_type=document_type
        )

        return DocumentUploadResponse(
            document_id=result.document_id,
            filename=file.filename,
            message="文档上传成功",
            chunk_count=result.chunk_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail="文档上传失败")


@router.post("/analyze", response_model=RequirementAnalysisResponse)
async def analyze_requirement(
    requirement: RequirementCreate,
    background_tasks: BackgroundTasks
):
    """
    分析需求文档

    启动需求智能体分析文档，生成结构化需求规格。
    """
    try:
        # 启动异步分析任务
        task_id = await requirement_service.start_analysis(
            requirement=requirement,
            background_tasks=background_tasks
        )

        return RequirementAnalysisResponse(
            task_id=task_id,
            message="需求分析任务已启动",
            status="processing"
        )

    except Exception as e:
        logger.error(f"需求分析启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail="需求分析启动失败")


@router.get("/{requirement_id}", response_model=RequirementResponse)
async def get_requirement(requirement_id: str):
    """
    获取需求详情
    """
    try:
        requirement = await requirement_service.get_requirement(requirement_id)
        if not requirement:
            raise HTTPException(status_code=404, detail="需求不存在")

        return requirement
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取需求失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取需求失败")


@router.get("/{requirement_id}/analysis")
async def get_analysis_result(requirement_id: str):
    """
    获取需求分析结果
    """
    try:
        result = await requirement_service.get_analysis_result(requirement_id)
        if not result:
            raise HTTPException(status_code=404, detail="分析结果不存在")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取分析结果失败")


@router.get("/project/{project_id}", response_model=List[RequirementResponse])
async def get_project_requirements(project_id: str, skip: int = 0, limit: int = 100):
    """
    获取项目的所有需求
    """
    try:
        requirements = await requirement_service.get_project_requirements(
            project_id=project_id,
            skip=skip,
            limit=limit
        )
        return requirements
    except Exception as e:
        logger.error(f"获取项目需求失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取项目需求失败")


@router.delete("/{requirement_id}")
async def delete_requirement(requirement_id: str):
    """
    删除需求
    """
    try:
        success = await requirement_service.delete_requirement(requirement_id)
        if not success:
            raise HTTPException(status_code=404, detail="需求不存在")

        return {"message": "需求删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除需求失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除需求失败")