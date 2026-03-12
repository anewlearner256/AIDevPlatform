"""任务规划智能体

将需求分解为具体的开发任务，分析任务依赖关系和优先级。
"""

from typing import Dict, Any, List, Optional
import json
import re
import loguru

from .base_agent import BaseAgent
from config.agents_config import TaskPlannerConfig
from utils.llm_client import LLMClient

logger = loguru.logger

class TaskPlannerAgent(BaseAgent):
    """任务规划智能体"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """初始化任务规划智能体"""
        config = TaskPlannerConfig()
        super().__init__(
            name="task_planner_agent",
            config=config,
            llm_client=llm_client
        )

        self.prompt_template = config.decomposition_prompt_template
        self.max_tasks = config.max_tasks_per_requirement
        self.min_hours = config.min_task_hours
        self.max_hours = config.max_task_hours

        logger.info("任务规划智能体初始化完成")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理任务规划

        Args:
            input_data: 输入数据，包含需求规格和分析上下文

        Returns:
            任务分解结果
        """
        try:
            # 验证输入
            if not await self.validate_input(input_data):
                raise ValueError("输入数据验证失败")

            # 准备提示
            prompt = self._prepare_prompt(input_data)

            # 调用LLM进行任务规划
            planning_result = await self._plan_with_llm(prompt)

            # 后处理：验证和优化任务分解
            processed_result = await self._post_process_tasks(planning_result)

            # 验证输出
            if not await self.validate_output(processed_result):
                raise ValueError("任务规划结果验证失败")

            # 添加元数据
            processed_result["metadata"] = {
                "agent": self.name,
                "planning_timestamp": self._get_current_timestamp(),
                "input_summary": self._summarize_input(input_data),
                "total_tasks": len(processed_result.get("tasks", [])),
            }

            logger.info(f"任务规划完成，生成 {len(processed_result.get('tasks', []))} 个任务")
            return processed_result

        except Exception as e:
            logger.error(f"任务规划失败: {str(e)}")
            raise

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not await super().validate_input(input_data):
            return False

        # 检查必要字段
        required_fields = ["requirement_spec"]
        for field in required_fields:
            if field not in input_data:
                logger.warning(f"输入数据缺少必要字段: {field}")
                return False

        # 检查需求规格格式
        req_spec = input_data.get("requirement_spec", {})
        if not isinstance(req_spec, dict):
            logger.warning("需求规格必须是字典")
            return False

        # 检查核心字段
        if not req_spec.get("title") and not req_spec.get("core_objectives"):
            logger.warning("需求规格缺少标题或核心目标")
            return False

        return True

    async def validate_output(self, output_data: Dict[str, Any]) -> bool:
        """验证输出数据"""
        if not await super().validate_output(output_data):
            return False

        # 检查必要字段
        required_fields = ["tasks", "summary"]
        for field in required_fields:
            if field not in output_data:
                logger.warning(f"输出数据缺少必要字段: {field}")
                return False

        # 验证任务列表
        tasks = output_data.get("tasks", [])
        if not isinstance(tasks, list):
            logger.warning("tasks 必须是列表")
            return False

        if len(tasks) == 0:
            logger.warning("任务列表不能为空")
            return False

        if len(tasks) > self.max_tasks:
            logger.warning(f"任务数量超过限制: {len(tasks)} > {self.max_tasks}")
            # 不返回False，只是警告

        # 验证每个任务
        for i, task in enumerate(tasks):
            if not self._validate_task(task, i):
                return False

        return True

    def _validate_task(self, task: Dict[str, Any], index: int) -> bool:
        """验证单个任务"""
        required_fields = ["task_id", "title", "description", "priority", "estimated_hours"]
        for field in required_fields:
            if field not in task:
                logger.warning(f"任务 {index} 缺少字段: {field}")
                return False

        # 验证优先级
        valid_priorities = ["high", "medium", "low"]
        if task.get("priority") not in valid_priorities:
            logger.warning(f"任务 {index} 优先级无效: {task.get('priority')}")
            return False

        # 验证预估工时
        estimated_hours = task.get("estimated_hours", 0)
        if not isinstance(estimated_hours, (int, float)):
            logger.warning(f"任务 {index} 预估工时必须是数字")
            return False

        if estimated_hours < self.min_hours or estimated_hours > self.max_hours:
            logger.warning(f"任务 {index} 预估工时超出范围: {estimated_hours}")
            # 不返回False，只是调整

        return True

    def _prepare_prompt(self, input_data: Dict[str, Any]) -> str:
        """准备提示"""
        # 提取需求规格
        requirement_spec = input_data.get("requirement_spec", {})

        # 格式化需求规格
        formatted_spec = self._format_requirement_spec(requirement_spec)

        # 构建上下文
        context = {
            "requirement_spec": formatted_spec,
            "max_tasks": self.max_tasks,
            "min_hours": self.min_hours,
            "max_hours": self.max_hours,
            "additional_context": input_data.get("additional_context", ""),
        }

        # 格式化提示
        prompt = self.prompt_template.format(**context)

        # 添加输出格式要求
        output_schema = {
            "summary": {
                "total_tasks": "总任务数",
                "total_estimated_hours": "总预估工时",
                "high_priority_tasks": "高优先级任务数",
                "dependencies_analyzed": "是否分析了依赖关系",
            },
            "tasks": [
                {
                    "task_id": "任务ID（如T001）",
                    "title": "任务标题",
                    "description": "任务描述",
                    "priority": "优先级（high/medium/low）",
                    "estimated_hours": "预估工时（小时）",
                    "dependencies": ["依赖的任务ID列表"],
                    "required_skills": ["所需技能列表"],
                    "task_type": "任务类型（如development/testing/documentation）",
                }
            ]
        }

        prompt += f"\n\n请严格按照以下JSON格式返回结果:\n{json.dumps(output_schema, indent=2, ensure_ascii=False)}"

        return prompt

    def _format_requirement_spec(self, requirement_spec: Dict[str, Any]) -> str:
        """格式化需求规格"""
        formatted = []

        # 标题
        if title := requirement_spec.get("title"):
            formatted.append(f"需求标题: {title}")

        # 描述
        if description := requirement_spec.get("description"):
            formatted.append(f"\n需求描述: {description}")

        # 核心目标
        if objectives := requirement_spec.get("core_objectives"):
            formatted.append("\n核心目标:")
            for i, obj in enumerate(objectives, 1):
                formatted.append(f"  {i}. {obj}")

        # 功能列表
        if features := requirement_spec.get("features"):
            formatted.append("\n主要功能:")
            for i, feature in enumerate(features, 1):
                formatted.append(f"  {i}. {feature}")

        # 技术约束
        if constraints := requirement_spec.get("technical_constraints"):
            formatted.append("\n技术约束:")
            for i, constraint in enumerate(constraints, 1):
                formatted.append(f"  {i}. {constraint}")

        # 建议技术栈
        if tech_stack := requirement_spec.get("suggested_tech_stack"):
            formatted.append(f"\n建议技术栈: {', '.join(tech_stack)}")

        return "\n".join(formatted)

    async def _plan_with_llm(self, prompt: str) -> Dict[str, Any]:
        """使用LLM进行任务规划"""
        try:
            # 调用LLM
            response = await self.call_llm(
                prompt=prompt,
                system_prompt="你是一个资深项目规划师，擅长将复杂需求分解为可执行的任务。"
            )

            # 解析响应
            planning_result = self._parse_llm_response(response)

            return planning_result

        except Exception as e:
            logger.error(f"LLM任务规划失败: {str(e)}")
            # 回退到默认规划
            return self._fallback_planning(prompt)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            # 解析JSON
            result = json.loads(json_str)

            # 验证和标准化结果
            return self._standardize_planning_result(result)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败，尝试提取关键信息: {str(e)}")
            return self._extract_task_information(response)

    def _standardize_planning_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """标准化规划结果"""
        standardized = {
            "summary": result.get("summary", {}),
            "tasks": [],
        }

        # 处理任务列表
        tasks = result.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        for i, task in enumerate(tasks, 1):
            standardized_task = self._standardize_task(task, i)
            if standardized_task:
                standardized["tasks"].append(standardized_task)

        # 确保摘要包含必要信息
        if not standardized["summary"].get("total_tasks"):
            standardized["summary"]["total_tasks"] = len(standardized["tasks"])

        if not standardized["summary"].get("total_estimated_hours"):
            total_hours = sum(t.get("estimated_hours", 0) for t in standardized["tasks"])
            standardized["summary"]["total_estimated_hours"] = total_hours

        return standardized

    def _standardize_task(self, task: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        """标准化单个任务"""
        try:
            # 确保任务ID
            task_id = task.get("task_id") or f"T{index:03d}"

            # 确保标题
            title = task.get("title") or f"任务 {index}"

            # 确保描述
            description = task.get("description") or title

            # 标准化优先级
            priority = task.get("priority", "medium").lower()
            if priority not in ["high", "medium", "low"]:
                priority = "medium"

            # 标准化预估工时
            estimated_hours = task.get("estimated_hours", 8)
            if not isinstance(estimated_hours, (int, float)):
                estimated_hours = 8
            estimated_hours = max(self.min_hours, min(self.max_hours, estimated_hours))

            # 标准化依赖关系
            dependencies = task.get("dependencies", [])
            if not isinstance(dependencies, list):
                dependencies = []

            # 标准化所需技能
            required_skills = task.get("required_skills", [])
            if not isinstance(required_skills, list):
                required_skills = []

            # 标准化任务类型
            task_type = task.get("task_type", "development")
            valid_types = ["development", "testing", "documentation", "design", "deployment", "other"]
            if task_type not in valid_types:
                task_type = "development"

            standardized = {
                "task_id": task_id,
                "title": title,
                "description": description,
                "priority": priority,
                "estimated_hours": estimated_hours,
                "dependencies": dependencies,
                "required_skills": required_skills,
                "task_type": task_type,
            }

            return standardized

        except Exception as e:
            logger.warning(f"标准化任务失败（索引 {index}）: {str(e)}")
            return None

    async def _post_process_tasks(self, planning_result: Dict[str, Any]) -> Dict[str, Any]:
        """后处理任务分解"""
        try:
            tasks = planning_result.get("tasks", [])
            if not tasks:
                return planning_result

            # 1. 分析依赖关系
            tasks = self._analyze_dependencies(tasks)

            # 2. 优化任务顺序
            tasks = self._optimize_task_order(tasks)

            # 3. 验证和修复任务ID
            tasks = self._validate_and_fix_task_ids(tasks)

            # 4. 计算关键路径
            critical_path = self._calculate_critical_path(tasks)

            # 更新结果
            updated_result = planning_result.copy()
            updated_result["tasks"] = tasks

            # 更新摘要
            if "summary" not in updated_result:
                updated_result["summary"] = {}

            updated_result["summary"]["critical_path"] = critical_path
            updated_result["summary"]["optimized"] = True

            return updated_result

        except Exception as e:
            logger.error(f"任务后处理失败: {str(e)}")
            return planning_result

    def _analyze_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析任务依赖关系"""
        # 构建任务ID映射
        task_id_map = {task["task_id"]: i for i, task in enumerate(tasks)}

        # 分析依赖关系
        for task in tasks:
            dependencies = task.get("dependencies", [])
            valid_dependencies = []

            for dep_id in dependencies:
                if dep_id in task_id_map:
                    valid_dependencies.append(dep_id)
                else:
                    logger.warning(f"依赖的任务不存在: {dep_id}")

            task["dependencies"] = valid_dependencies

        # 检查循环依赖
        for i, task in enumerate(tasks):
            if self._has_dependency_cycle(tasks, task["task_id"], set()):
                logger.warning(f"检测到循环依赖: {task['task_id']}")
                task["dependencies"] = []

        return tasks

    def _has_dependency_cycle(
        self,
        tasks: List[Dict[str, Any]],
        task_id: str,
        visited: set
    ) -> bool:
        """检查循环依赖"""
        if task_id in visited:
            return True

        visited.add(task_id)

        # 查找任务
        task = next((t for t in tasks if t["task_id"] == task_id), None)
        if not task:
            return False

        # 检查所有依赖
        for dep_id in task.get("dependencies", []):
            if self._has_dependency_cycle(tasks, dep_id, visited.copy()):
                return True

        return False

    def _optimize_task_order(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """优化任务顺序"""
        # 基于依赖关系拓扑排序
        sorted_tasks = []
        visited = set()

        # 构建邻接表
        adjacency = {task["task_id"]: set(task.get("dependencies", [])) for task in tasks}

        def visit(task_id):
            if task_id in visited:
                return
            visited.add(task_id)

            # 先访问依赖
            for dep_id in adjacency.get(task_id, set()):
                visit(dep_id)

            # 添加任务
            task = next((t for t in tasks if t["task_id"] == task_id), None)
            if task:
                sorted_tasks.append(task)

        # 访问所有任务
        for task in tasks:
            visit(task["task_id"])

        return sorted_tasks

    def _validate_and_fix_task_ids(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证和修复任务ID"""
        seen_ids = set()
        for i, task in enumerate(tasks):
            task_id = task.get("task_id")

            # 如果ID不存在或重复，生成新ID
            if not task_id or task_id in seen_ids:
                task_id = f"T{i+1:03d}"
                task["task_id"] = task_id

            seen_ids.add(task_id)

        # 更新依赖关系中的任务ID
        task_id_map = {task["task_id"]: task for task in tasks}

        for task in tasks:
            dependencies = task.get("dependencies", [])
            updated_dependencies = []

            for dep_id in dependencies:
                if dep_id in task_id_map:
                    updated_dependencies.append(dep_id)
                else:
                    # 尝试查找旧ID
                    for t in tasks:
                        if t.get("old_task_id") == dep_id or t.get("original_id") == dep_id:
                            updated_dependencies.append(t["task_id"])
                            break

            task["dependencies"] = updated_dependencies

        return tasks

    def _calculate_critical_path(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """计算关键路径"""
        if not tasks:
            return []

        # 简化实现：返回高优先级任务
        high_priority_tasks = [t["task_id"] for t in tasks if t.get("priority") == "high"]

        if high_priority_tasks:
            return high_priority_tasks[:5]  # 限制长度

        # 返回前几个任务
        return [t["task_id"] for t in tasks[:3]]

    def _extract_task_information(self, text: str) -> Dict[str, Any]:
        """从文本中提取任务信息（回退方法）"""
        logger.info("使用回退方法提取任务信息")

        # 初始化结果
        result = {
            "summary": {
                "total_tasks": 0,
                "total_estimated_hours": 0,
                "high_priority_tasks": 0,
                "dependencies_analyzed": False,
            },
            "tasks": [],
        }

        # 简单提取任务
        lines = text.split('\n')
        current_task = None

        for line in lines:
            line = line.strip()

            # 检测任务开始
            if line.startswith(("#", "##", "任务", "Task", "TASK")) and ":" in line:
                if current_task:
                    result["tasks"].append(current_task)

                # 解析任务标题
                parts = line.split(":", 1)
                title = parts[1].strip() if len(parts) > 1 else line

                current_task = {
                    "task_id": f"T{len(result['tasks']) + 1:03d}",
                    "title": title,
                    "description": title,
                    "priority": "medium",
                    "estimated_hours": 8,
                    "dependencies": [],
                    "required_skills": [],
                    "task_type": "development",
                }

            # 检测任务属性
            elif current_task and ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if "priority" in key:
                    current_task["priority"] = "high" if "高" in value or "high" in value.lower() else "medium"
                elif "hour" in key or "time" in key or "工时" in key:
                    try:
                        hours = float(value.split()[0])
                        current_task["estimated_hours"] = hours
                    except:
                        pass
                elif "depend" in key or "依赖" in key:
                    # 简单解析依赖
                    deps = [d.strip() for d in value.split(",") if d.strip()]
                    current_task["dependencies"] = deps

        # 添加最后一个任务
        if current_task:
            result["tasks"].append(current_task)

        # 更新摘要
        result["summary"]["total_tasks"] = len(result["tasks"])
        result["summary"]["total_estimated_hours"] = sum(t.get("estimated_hours", 0) for t in result["tasks"])
        result["summary"]["high_priority_tasks"] = sum(1 for t in result["tasks"] if t.get("priority") == "high")

        return result

    def _fallback_planning(self, prompt: str) -> Dict[str, Any]:
        """回退规划（当LLM失败时）"""
        logger.warning("使用回退规划")

        # 简单任务分解
        result = {
            "summary": {
                "total_tasks": 3,
                "total_estimated_hours": 24,
                "high_priority_tasks": 1,
                "dependencies_analyzed": True,
            },
            "tasks": [
                {
                    "task_id": "T001",
                    "title": "需求分析和设计",
                    "description": "详细分析需求，设计系统架构和数据库",
                    "priority": "high",
                    "estimated_hours": 8,
                    "dependencies": [],
                    "required_skills": ["需求分析", "系统设计"],
                    "task_type": "development",
                },
                {
                    "task_id": "T002",
                    "title": "核心功能开发",
                    "description": "实现系统核心功能模块",
                    "priority": "medium",
                    "estimated_hours": 12,
                    "dependencies": ["T001"],
                    "required_skills": ["编程", "API开发"],
                    "task_type": "development",
                },
                {
                    "task_id": "T003",
                    "title": "测试和部署",
                    "description": "编写测试用例，部署系统",
                    "priority": "medium",
                    "estimated_hours": 4,
                    "dependencies": ["T002"],
                    "required_skills": ["测试", "部署"],
                    "task_type": "testing",
                },
            ]
        }

        return result

    def _summarize_input(self, input_data: Dict[str, Any]) -> str:
        """摘要输入数据"""
        summary = []

        if req_spec := input_data.get("requirement_spec"):
            if title := req_spec.get("title"):
                summary.append(f"需求: {title[:50]}...")

            if objectives := req_spec.get("core_objectives"):
                summary.append(f"目标数: {len(objectives)}")

            if features := req_spec.get("features"):
                summary.append(f"功能数: {len(features)}")

        return "; ".join(summary)

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    async def get_planning_template(self) -> Dict[str, Any]:
        """获取规划模板"""
        return {
            "prompt_template": self.prompt_template,
            "config": {
                "max_tasks": self.max_tasks,
                "min_hours": self.min_hours,
                "max_hours": self.max_hours,
                "max_retries": self.config.max_retries,
                "timeout": self.config.timeout,
            }
        }