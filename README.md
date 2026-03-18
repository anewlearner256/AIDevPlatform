# AI自动开发平台

一个基于多智能体工作流的AI自动开发平台，能够从需求输入自动生成可运行的代码。

## 系统架构

平台采用模块化架构，主要包含以下核心组件：

1. **RAG知识库系统** - 基于ChromaDB的文档检索和知识管理
2. **智能体系统** - 需求、任务规划、开发、评审、测试智能体
3. **LangGraph工作流编排** - 多智能体协作流程控制
4. **OpenClaw执行引擎** - Docker沙箱环境中的安全代码执行
5. **技能系统** - 构建、部署、调试等扩展技能

## 技术栈

- **后端框架**: FastAPI (Python 3.11+)
- **智能体编排**: LangGraph + LangChain
- **LLM集成**: Anthropic Claude API / OpenAI API
- **向量数据库**: ChromaDB
- **主数据库**: PostgreSQL
- **缓存/队列**: Redis + Celery
- **执行环境**: Docker
- **前端**: React + TypeScript + Ant Design (可选)

## 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (可通过Docker运行)
- Redis (可通过Docker运行)

### 本地开发设置

1. 克隆项目并进入目录
2. 安装依赖:
   ```bash
   pip install poetry
   poetry install
   ```
3. 复制环境变量文件:
   ```bash
   cp .env.example .env
   # 编辑.env文件配置API密钥和数据库连接
   ```
4. 启动依赖服务:
   ```bash
   docker-compose up -d postgres redis
   ```
5. 初始化数据库:
   ```bash
   poetry run python scripts/migrate.py
   ```
6. 启动开发服务器:
   ```bash
   poetry run uvicorn api.main:app --reload
   ```

### Docker部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## API文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目结构

```
aid-dev-platform/
├── api/              # FastAPI应用层
├── core/             # 核心业务逻辑
├── models/           # 数据模型层
├── services/         # 服务层
├── utils/            # 工具函数
├── config/           # 配置文件
├── tests/            # 测试目录
├── docker/           # Docker配置
├── docs/             # 文档
└── scripts/          # 脚本文件
```

## 功能特性

### 已实现
- [x] 项目管理API（项目/需求/任务/执行的核心路由与服务层已完成）
- [x] 需求智能体（需求分析与结构化的Agent实现已完成）
- [x] 任务规划智能体（任务分解与依赖分析的Agent实现已完成）
- [x] 开发/评审/测试智能体（多智能体基础实现与编排已完成）
- [x] LangGraph工作流编排（开发、评审、测试与全流程工作流图已实现）
- [x] OpenClaw执行引擎（多语言代码执行与依赖安装基础能力已实现）
- [x] 任务队列系统（Redis + Celery任务队列与后台任务框架已实现）
- [x] RAG知识库基础链路（KnowledgeManager/VectorStore/检索结构已接入）
- [x] 智能体服务层（AgentService + 依赖注入路径已补齐）

> 注：系统主干能力已可联调，技能系统与部分生产级增强（可观测性、稳定性、更多语言生态）持续完善中。

### 规划中
- [ ] 前端监控仪表板
- [ ] 多租户支持
- [ ] 插件系统
- [ ] 更多编程语言支持

## 开发指南

### 代码风格

- 使用Black进行代码格式化
- 使用isort进行导入排序
- 使用mypy进行类型检查
- 使用pytest进行测试

### 提交规范

使用Conventional Commits规范:
- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具变动

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request。请确保代码符合项目代码规范并通过所有测试。
