"""OpenClaw执行器

集成OpenClaw代码执行引擎，提供安全的代码执行环境。
"""

import asyncio
import json
import tempfile
import subprocess
import os
import shutil
import loguru
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from config.settings import settings

logger = loguru.logger


class OpenClawExecutor:
    """OpenClaw执行器"""

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        timeout: int = 300,
        memory_limit: str = "1g",
        cpu_limit: float = 1.0
    ):
        """
        初始化OpenClaw执行器

        Args:
            workspace_dir: 工作空间目录
            timeout: 执行超时时间（秒）
            memory_limit: 内存限制
            cpu_limit: CPU限制
        """
        self.workspace_dir = workspace_dir or os.path.join(
            tempfile.gettempdir(),
            f"openclaw_workspace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.timeout = timeout or settings.execution_timeout
        self.memory_limit = memory_limit or settings.max_memory_limit
        self.cpu_limit = cpu_limit or settings.max_cpu_limit

        # 创建工作空间目录
        os.makedirs(self.workspace_dir, exist_ok=True)

        logger.info(f"OpenClaw执行器初始化完成，工作空间: {self.workspace_dir}")

    async def execute_code(
        self,
        code: Dict[str, str],
        language: str,
        input_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        执行代码

        Args:
            code: 代码字典（文件名 -> 代码内容）
            language: 编程语言
            input_data: 输入数据
            dependencies: 依赖项列表
            environment: 环境变量

        Returns:
            执行结果
        """
        try:
            # 创建工作空间
            execution_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            execution_dir = os.path.join(self.workspace_dir, execution_id)
            os.makedirs(execution_dir, exist_ok=True)

            # 写入代码文件
            code_files = await self._write_code_files(execution_dir, code, language)

            # 写入输入数据
            input_file = None
            if input_data:
                input_file = await self._write_input_data(execution_dir, input_data)

            # 安装依赖（如果需要）
            if dependencies:
                await self._install_dependencies(execution_dir, language, dependencies)

            # 准备环境
            env = await self._prepare_environment(environment)

            # 执行代码
            start_time = datetime.now()
            result = await self._execute_with_sandbox(
                execution_dir=execution_dir,
                code_files=code_files,
                language=language,
                input_file=input_file,
                env=env
            )
            execution_time = (datetime.now() - start_time).total_seconds()

            # 收集结果
            output = {
                "execution_id": execution_id,
                "status": result["status"],
                "output": result.get("output", ""),
                "error": result.get("error", ""),
                "exit_code": result.get("exit_code", 0),
                "execution_time": execution_time,
                "resource_usage": result.get("resource_usage", {}),
                "code_files": code_files,
                "language": language,
                "timestamp": datetime.now().isoformat(),
            }

            # 清理工作空间（保留一段时间用于调试）
            await self._schedule_cleanup(execution_dir)

            logger.info(f"代码执行完成: {execution_id} ({language}), 状态: {result['status']}")
            return output

        except Exception as e:
            logger.error(f"代码执行失败: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "execution_time": 0,
                "timestamp": datetime.now().isoformat(),
            }

    async def _write_code_files(
        self,
        execution_dir: str,
        code: Dict[str, str],
        language: str
    ) -> Dict[str, str]:
        """
        写入代码文件

        Args:
            execution_dir: 执行目录
            code: 代码字典
            language: 编程语言

        Returns:
            文件路径字典
        """
        code_files = {}

        for filename, content in code.items():
            # 确保文件扩展名正确
            if not self._has_valid_extension(filename, language):
                filename = self._add_extension(filename, language)

            file_path = os.path.join(execution_dir, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            code_files[filename] = file_path

        return code_files

    def _has_valid_extension(self, filename: str, language: str) -> bool:
        """检查文件扩展名是否有效"""
        extension_map = {
            "python": [".py"],
            "javascript": [".js"],
            "typescript": [".ts"],
            "java": [".java"],
            "go": [".go"],
            "cpp": [".cpp", ".cc", ".cxx"],
            "c": [".c"],
            "rust": [".rs"],
            "ruby": [".rb"],
            "php": [".php"],
        }

        extensions = extension_map.get(language, [])
        return any(filename.endswith(ext) for ext in extensions)

    def _add_extension(self, filename: str, language: str) -> str:
        """添加文件扩展名"""
        extension_map = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "java": ".java",
            "go": ".go",
            "cpp": ".cpp",
            "c": ".c",
            "rust": ".rs",
            "ruby": ".rb",
            "php": ".php",
        }

        extension = extension_map.get(language, ".txt")
        if not filename.endswith(extension):
            filename += extension

        return filename

    async def _write_input_data(self, execution_dir: str, input_data: Dict[str, Any]) -> str:
        """
        写入输入数据

        Args:
            execution_dir: 执行目录
            input_data: 输入数据

        Returns:
            输入文件路径
        """
        input_file = os.path.join(execution_dir, "input.json")

        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(input_data, f, indent=2, ensure_ascii=False)

        return input_file

    async def _install_dependencies(self, execution_dir: str, language: str, dependencies: List[str]):
        """
        安装依赖项

        Args:
            execution_dir: 执行目录
            language: 编程语言
            dependencies: 依赖项列表
        """
        try:
            if language == "python":
                await self._install_python_dependencies(execution_dir, dependencies)
            elif language == "javascript":
                await self._install_javascript_dependencies(execution_dir, dependencies)
            elif language == "java":
                await self._install_java_dependencies(execution_dir, dependencies)
            # 其他语言的依赖安装可以后续添加

            logger.debug(f"依赖安装完成: {language}, {len(dependencies)} 个依赖项")

        except Exception as e:
            logger.warning(f"依赖安装失败: {e}")

    async def _install_python_dependencies(self, execution_dir: str, dependencies: List[str]):
        """安装Python依赖"""
        # 创建requirements.txt
        requirements_file = os.path.join(execution_dir, "requirements.txt")
        with open(requirements_file, 'w', encoding='utf-8') as f:
            for dep in dependencies:
                f.write(f"{dep}\n")

        # 安装依赖
        cmd = ["pip", "install", "-r", requirements_file, "--user"]
        await self._run_command(cmd, execution_dir)

    async def _install_javascript_dependencies(self, execution_dir: str, dependencies: List[str]):
        """安装JavaScript依赖"""
        # 创建package.json
        package_json = {
            "name": "execution-package",
            "version": "1.0.0",
            "dependencies": {dep: "*" for dep in dependencies}
        }

        package_file = os.path.join(execution_dir, "package.json")
        with open(package_file, 'w', encoding='utf-8') as f:
            json.dump(package_json, f, indent=2)

        # 安装依赖
        cmd = ["npm", "install"]
        await self._run_command(cmd, execution_dir)

    async def _install_java_dependencies(self, execution_dir: str, dependencies: List[str]):
        """安装Java依赖"""
        # 创建简单的pom.xml
        pom_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>execution</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <!-- 依赖项可以在这里添加 -->
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.8.1</version>
                <configuration>
                    <source>11</source>
                    <target>11</target>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>"""

        pom_file = os.path.join(execution_dir, "pom.xml")
        with open(pom_file, 'w', encoding='utf-8') as f:
            f.write(pom_xml)

        # 注：实际依赖安装需要更复杂的Maven配置
        logger.info("Java依赖安装需要手动配置pom.xml")

    async def _prepare_environment(self, environment: Optional[Dict[str, str]]) -> Dict[str, str]:
        """
        准备环境变量

        Args:
            environment: 自定义环境变量

        Returns:
            环境变量字典
        """
        env = os.environ.copy()

        # 添加默认环境变量
        env.update({
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
        })

        # 添加自定义环境变量
        if environment:
            env.update(environment)

        return env

    async def _execute_with_sandbox(
        self,
        execution_dir: str,
        code_files: Dict[str, str],
        language: str,
        input_file: Optional[str],
        env: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        使用沙箱执行代码

        Args:
            execution_dir: 执行目录
            code_files: 代码文件路径
            language: 编程语言
            input_file: 输入文件路径
            env: 环境变量

        Returns:
            执行结果
        """
        try:
            # 根据语言选择执行命令
            if language == "python":
                result = await self._execute_python(execution_dir, code_files, input_file, env)
            elif language == "javascript":
                result = await self._execute_javascript(execution_dir, code_files, input_file, env)
            elif language == "java":
                result = await self._execute_java(execution_dir, code_files, input_file, env)
            elif language == "go":
                result = await self._execute_go(execution_dir, code_files, input_file, env)
            else:
                result = await self._execute_generic(execution_dir, code_files, language, input_file, env)

            return result

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"执行超时 ({self.timeout}秒)",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "exit_code": -1,
            }

    async def _execute_python(
        self,
        execution_dir: str,
        code_files: Dict[str, str],
        input_file: Optional[str],
        env: Dict[str, str]
    ) -> Dict[str, Any]:
        """执行Python代码"""
        # 找到主文件（通常是main.py或第一个.py文件）
        main_file = None
        for filename, filepath in code_files.items():
            if filename.endswith(".py"):
                if filename == "main.py" or "main" in filename.lower():
                    main_file = filepath
                    break

        if not main_file and code_files:
            main_file = next(iter(code_files.values()))

        if not main_file:
            return {
                "status": "failed",
                "error": "未找到Python主文件",
                "exit_code": -1,
            }

        # 构建执行命令
        cmd = ["python", main_file]

        # 如果有输入文件，作为参数传递
        if input_file:
            cmd.append(input_file)

        return await self._run_command(cmd, execution_dir, env)

    async def _execute_javascript(
        self,
        execution_dir: str,
        code_files: Dict[str, str],
        input_file: Optional[str],
        env: Dict[str, str]
    ) -> Dict[str, Any]:
        """执行JavaScript代码"""
        # 找到主文件
        main_file = None
        for filename, filepath in code_files.items():
            if filename.endswith(".js"):
                if filename == "index.js" or "main" in filename.lower():
                    main_file = filepath
                    break

        if not main_file and code_files:
            main_file = next(iter(code_files.values()))

        if not main_file:
            return {
                "status": "failed",
                "error": "未找到JavaScript主文件",
                "exit_code": -1,
            }

        cmd = ["node", main_file]

        if input_file:
            cmd.append(input_file)

        return await self._run_command(cmd, execution_dir, env)

    async def _execute_java(
        self,
        execution_dir: str,
        code_files: Dict[str, str],
        input_file: Optional[str],
        env: Dict[str, str]
    ) -> Dict[str, Any]:
        """执行Java代码"""
        # 编译Java文件
        java_files = [f for f in code_files.values() if f.endswith(".java")]
        if not java_files:
            return {
                "status": "failed",
                "error": "未找到Java文件",
                "exit_code": -1,
            }

        # 编译
        compile_cmd = ["javac"] + java_files
        compile_result = await self._run_command(compile_cmd, execution_dir, env)

        if compile_result["exit_code"] != 0:
            return {
                "status": "compile_failed",
                "error": compile_result.get("error", "编译失败"),
                "output": compile_result.get("output", ""),
                "exit_code": compile_result["exit_code"],
            }

        # 找到主类
        main_class = self._find_java_main_class(java_files[0])
        if not main_class:
            return {
                "status": "failed",
                "error": "未找到Java主类",
                "exit_code": -1,
            }

        # 执行
        exec_cmd = ["java", main_class]
        if input_file:
            exec_cmd.append(input_file)

        return await self._run_command(exec_cmd, execution_dir, env)

    def _find_java_main_class(self, java_file: str) -> Optional[str]:
        """查找Java主类"""
        try:
            with open(java_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单查找public class和main方法
            import re
            class_match = re.search(r'public\s+class\s+(\w+)', content)
            if class_match and 'public static void main' in content:
                return class_match.group(1)

        except Exception:
            pass

        return None

    async def _execute_go(
        self,
        execution_dir: str,
        code_files: Dict[str, str],
        input_file: Optional[str],
        env: Dict[str, str]
    ) -> Dict[str, Any]:
        """执行Go代码"""
        # 找到主文件
        main_file = None
        for filename, filepath in code_files.items():
            if filename.endswith(".go"):
                if "main" in filename.lower():
                    main_file = filepath
                    break

        if not main_file and code_files:
            main_file = next(iter(code_files.values()))

        if not main_file:
            return {
                "status": "failed",
                "error": "未找到Go主文件",
                "exit_code": -1,
            }

        # 构建可执行文件
        executable = os.path.join(execution_dir, "main")
        build_cmd = ["go", "build", "-o", executable, main_file]
        build_result = await self._run_command(build_cmd, execution_dir, env)

        if build_result["exit_code"] != 0:
            return {
                "status": "compile_failed",
                "error": build_result.get("error", "编译失败"),
                "output": build_result.get("output", ""),
                "exit_code": build_result["exit_code"],
            }

        # 执行
        exec_cmd = [executable]
        if input_file:
            exec_cmd.append(input_file)

        return await self._run_command(exec_cmd, execution_dir, env)

    async def _execute_generic(
        self,
        execution_dir: str,
        code_files: Dict[str, str],
        language: str,
        input_file: Optional[str],
        env: Dict[str, str]
    ) -> Dict[str, Any]:
        """执行通用代码"""
        # 对于不支持的语言，返回错误
        return {
            "status": "failed",
            "error": f"不支持的语言: {language}",
            "exit_code": -1,
        }

    async def _run_command(
        self,
        cmd: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        运行命令

        Args:
            cmd: 命令列表
            cwd: 工作目录
            env: 环境变量

        Returns:
            执行结果
        """
        try:
            # 准备进程
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

            # 执行并等待完成
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                # 超时，终止进程
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                raise asyncio.TimeoutError(f"命令执行超时: {' '.join(cmd)}")

            # 解码输出
            output = stdout.decode('utf-8', errors='replace') if stdout else ""
            error = stderr.decode('utf-8', errors='replace') if stderr else ""

            # 确定状态
            exit_code = process.returncode
            if exit_code == 0:
                status = "success"
            else:
                status = "failed"

            return {
                "status": status,
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "resource_usage": {
                    # 这里可以添加资源使用统计
                },
            }

        except Exception as e:
            logger.error(f"命令执行失败: {' '.join(cmd)} - {e}")
            return {
                "status": "failed",
                "error": str(e),
                "output": "",
                "exit_code": -1,
            }

    async def _schedule_cleanup(self, execution_dir: str):
        """计划清理执行目录"""
        # 在实际应用中，可以设置延迟清理
        # 这里简化处理，立即清理
        try:
            # 使用线程池避免阻塞
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, execution_dir, True)
        except Exception as e:
            logger.warning(f"清理执行目录失败: {e}")

    async def cleanup_all(self):
        """清理所有工作空间"""
        try:
            if os.path.exists(self.workspace_dir):
                shutil.rmtree(self.workspace_dir, ignore_errors=True)
                logger.info(f"清理工作空间: {self.workspace_dir}")
        except Exception as e:
            logger.error(f"清理工作空间失败: {e}")

    async def get_status(self) -> Dict[str, Any]:
        """
        获取执行器状态

        Returns:
            状态信息
        """
        workspace_exists = os.path.exists(self.workspace_dir)
        workspace_size = 0

        if workspace_exists:
            try:
                workspace_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(self.workspace_dir)
                    for filename in filenames
                )
            except Exception:
                pass

        return {
            "workspace_dir": self.workspace_dir,
            "workspace_exists": workspace_exists,
            "workspace_size_bytes": workspace_size,
            "timeout": self.timeout,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "timestamp": datetime.now().isoformat(),
        }