"""数据库备份和恢复脚本

支持PostgreSQL数据库的备份和恢复操作。
"""

import asyncio
import sys
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import loguru

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
import loguru

logger = loguru.logger

class DatabaseBackup:
    """数据库备份管理器"""

    def __init__(self, backup_dir: str = "./backups"):
        """
        初始化备份管理器

        Args:
            backup_dir: 备份文件存储目录
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _parse_database_url(self, url: str) -> dict:
        """解析数据库URL"""
        # 移除协议前缀
        if url.startswith("postgresql://"):
            url = url[13:]

        # 解析各部分
        parts = url.split("@")
        if len(parts) != 2:
            raise ValueError(f"无效的数据库URL: {url}")

        credentials_part, server_part = parts

        # 解析凭据
        if ":" in credentials_part:
            user, password = credentials_part.split(":", 1)
        else:
            user, password = credentials_part, ""

        # 解析服务器和数据库
        server_parts = server_part.split("/")
        if len(server_parts) != 2:
            raise ValueError(f"无效的服务器/数据库格式: {server_part}")

        server, database = server_parts

        # 解析主机和端口
        if ":" in server:
            host, port = server.split(":", 1)
        else:
            host, port = server, "5432"

        return {
            "user": user,
            "password": password,
            "host": host,
            "port": port,
            "database": database
        }

    def create_backup(self, backup_name: str = None, compress: bool = True) -> Path:
        """
        创建数据库备份

        Args:
            backup_name: 备份文件名（可选，自动生成）
            compress: 是否压缩备份文件

        Returns:
            备份文件路径
        """
        try:
            # 解析数据库配置
            db_config = self._parse_database_url(str(settings.database_url))

            # 生成备份文件名
            if backup_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{db_config['database']}_{timestamp}"

            backup_path = self.backup_dir / backup_name

            # 构建pg_dump命令
            env = os.environ.copy()
            if db_config["password"]:
                env["PGPASSWORD"] = db_config["password"]

            pg_dump_cmd = [
                "pg_dump",
                "-h", db_config["host"],
                "-p", db_config["port"],
                "-U", db_config["user"],
                "-d", db_config["database"],
                "-F", "c",  # 自定义格式（压缩）
                "-f", str(backup_path.with_suffix(".dump")),
                "--verbose",
                "--no-owner",
                "--no-acl",  # 不保存权限
            ]

            # 添加SSL模式（如果需要）
            if "localhost" not in db_config["host"] and "127.0.0.1" not in db_config["host"]:
                pg_dump_cmd.extend(["--ssl-mode", "require"])

            logger.info(f"开始创建数据库备份: {db_config['database']}")
            logger.info(f"命令: {' '.join(pg_dump_cmd[:6])}...")

            # 执行备份
            result = subprocess.run(
                pg_dump_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(f"备份创建成功: {backup_path.with_suffix('.dump')}")

            # 如果需要压缩
            final_path = backup_path.with_suffix(".dump")
            if compress:
                logger.info("压缩备份文件...")
                import gzip

                compressed_path = backup_path.with_suffix(".dump.gz")
                with open(final_path, "rb") as f_in:
                    with gzip.open(compressed_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # 删除未压缩文件
                os.remove(final_path)
                final_path = compressed_path

            logger.info(f"数据库备份完成: {final_path}")
            return final_path

        except subprocess.CalledProcessError as e:
            logger.error(f"备份失败: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"备份过程出错: {str(e)}")
            raise

    def restore_backup(self, backup_file: Path, drop_existing: bool = False) -> bool:
        """
        从备份恢复数据库

        Args:
            backup_file: 备份文件路径
            drop_existing: 是否删除现有数据库

        Returns:
            是否成功
        """
        try:
            # 解析数据库配置
            db_config = self._parse_database_url(str(settings.database_url))

            # 检查备份文件
            if not backup_file.exists():
                raise FileNotFoundError(f"备份文件不存在: {backup_file}")

            # 解压（如果需要）
            temp_file = None
            if backup_file.suffix == ".gz":
                logger.info("解压备份文件...")
                import gzip
                temp_dir = tempfile.gettempdir()
                temp_file = Path(temp_dir) / backup_file.stem

                with gzip.open(backup_file, "rb") as f_in:
                    with open(temp_file, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)

                restore_file = temp_file
            else:
                restore_file = backup_file

            # 准备环境变量
            env = os.environ.copy()
            if db_config["password"]:
                env["PGPASSWORD"] = db_config["password"]

            # 如果需要，删除现有数据库
            if drop_existing:
                logger.warning(f"删除现有数据库: {db_config['database']}")

                drop_db_cmd = [
                    "dropdb",
                    "-h", db_config["host"],
                    "-p", db_config["port"],
                    "-U", db_config["user"],
                    db_config["database"]
                ]

                try:
                    subprocess.run(
                        drop_db_cmd,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    logger.info("数据库删除成功")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"删除数据库失败（可能不存在）: {e.stderr}")

            # 创建数据库（如果不存在）
            create_db_cmd = [
                "createdb",
                "-h", db_config["host"],
                "-p", db_config["port"],
                "-U", db_config["user"],
                db_config["database"]
            ]

            try:
                subprocess.run(
                    create_db_cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info("数据库创建成功")
            except subprocess.CalledProcessError as e:
                logger.info(f"数据库已存在或创建失败: {e.stderr}")

            # 恢复备份
            logger.info("开始恢复数据库...")
            pg_restore_cmd = [
                "pg_restore",
                "-h", db_config["host"],
                "-p", db_config["port"],
                "-U", db_config["user"],
                "-d", db_config["database"],
                "--verbose",
                "--no-owner",
                "--no-acl",
                "--clean",  # 删除现有对象
                "--if-exists",
                str(restore_file)
            ]

            logger.info(f"恢复命令: {' '.join(pg_restore_cmd[:6])}...")

            result = subprocess.run(
                pg_restore_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info("数据库恢复成功")

            # 清理临时文件
            if temp_file and temp_file.exists():
                os.remove(temp_file)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"恢复失败: {e.stderr}")
            if e.stdout:
                logger.error(f"输出: {e.stdout}")
            return False
        except Exception as e:
            logger.error(f"恢复过程出错: {str(e)}")
            return False

    def list_backups(self) -> list:
        """列出所有备份文件"""
        backups = []
        for file in self.backup_dir.glob("backup_*.dump*"):
            stats = file.stat()
            backups.append({
                "name": file.name,
                "path": str(file),
                "size": stats.st_size,
                "modified": datetime.fromtimestamp(stats.st_mtime),
                "compressed": file.suffix == ".gz"
            })

        # 按修改时间排序
        backups.sort(key=lambda x: x["modified"], reverse=True)
        return backups

    def cleanup_old_backups(self, keep_last: int = 10, max_age_days: int = 30) -> int:
        """
        清理旧备份文件

        Args:
            keep_last: 保留最近多少个备份
            max_age_days: 最大保留天数

        Returns:
            删除的文件数量
        """
        backups = self.list_backups()
        if len(backups) <= keep_last:
            return 0

        deleted_count = 0
        cutoff_date = datetime.now().timestamp() - (max_age_days * 24 * 3600)

        for i, backup in enumerate(backups):
            should_delete = False

            # 保留最近的几个备份
            if i >= keep_last:
                should_delete = True

            # 删除超过最大天数的备份
            if backup["modified"].timestamp() < cutoff_date:
                should_delete = True

            if should_delete:
                try:
                    Path(backup["path"]).unlink()
                    logger.info(f"删除旧备份: {backup['name']}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"删除备份失败 {backup['name']}: {str(e)}")

        return deleted_count

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库备份和恢复工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # 备份命令
    backup_parser = subparsers.add_parser("backup", help="创建数据库备份")
    backup_parser.add_argument("--name", help="备份名称（可选）")
    backup_parser.add_argument("--no-compress", action="store_true", help="不压缩备份文件")
    backup_parser.add_argument("--backup-dir", default="./backups", help="备份目录")

    # 恢复命令
    restore_parser = subparsers.add_parser("restore", help="从备份恢复数据库")
    restore_parser.add_argument("backup_file", help="备份文件路径")
    restore_parser.add_argument("--drop-existing", action="store_true", help="删除现有数据库")
    restore_parser.add_argument("--backup-dir", default="./backups", help="备份目录")

    # 列表命令
    list_parser = subparsers.add_parser("list", help="列出所有备份")
    list_parser.add_argument("--backup-dir", default="./backups", help="备份目录")

    # 清理命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理旧备份")
    cleanup_parser.add_argument("--keep-last", type=int, default=10, help="保留最近多少个备份")
    cleanup_parser.add_argument("--max-age-days", type=int, default=30, help="最大保留天数")
    cleanup_parser.add_argument("--backup-dir", default="./backups", help="备份目录")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    backup_manager = DatabaseBackup(backup_dir=args.backup_dir)

    try:
        if args.command == "backup":
            backup_path = backup_manager.create_backup(
                backup_name=args.name,
                compress=not args.no_compress
            )
            logger.info(f"备份创建成功: {backup_path}")

        elif args.command == "restore":
            backup_file = Path(args.backup_file)
            if not backup_file.is_absolute():
                backup_file = Path(args.backup_dir) / args.backup_file

            success = backup_manager.restore_backup(
                backup_file=backup_file,
                drop_existing=args.drop_existing
            )

            if success:
                logger.info("数据库恢复成功")
            else:
                logger.error("数据库恢复失败")
                sys.exit(1)

        elif args.command == "list":
            backups = backup_manager.list_backups()
            if not backups:
                logger.info("没有找到备份文件")
            else:
                logger.info(f"找到 {len(backups)} 个备份文件:")
                for i, backup in enumerate(backups):
                    size_mb = backup["size"] / (1024 * 1024)
                    logger.info(f"  {i+1}. {backup['name']}")
                    logger.info(f"     大小: {size_mb:.2f} MB, 修改时间: {backup['modified']}")

        elif args.command == "cleanup":
            deleted = backup_manager.cleanup_old_backups(
                keep_last=args.keep_last,
                max_age_days=args.max_age_days
            )
            logger.info(f"清理完成，删除了 {deleted} 个旧备份")

    except Exception as e:
        logger.error(f"命令执行失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()