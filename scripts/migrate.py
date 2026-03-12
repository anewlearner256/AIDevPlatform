"""数据库迁移脚本

创建数据库表结构。
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from models.database import Base, get_sync_engine, get_sync_session
from config.settings import settings
import loguru

logger = loguru.logger

def create_tables():
    """创建数据库表"""
    try:
        engine = get_sync_engine()

        logger.info("开始创建数据库表...")

        # 创建所有表
        Base.metadata.create_all(bind=engine)

        logger.info("数据库表创建成功")

        # 验证表创建
        with engine.connect() as conn:
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = [row[0] for row in result]
            logger.info(f"已创建的表: {tables}")

        return True

    except Exception as e:
        logger.error(f"创建数据库表失败: {str(e)}")
        return False

def drop_tables():
    """删除数据库表（仅用于开发和测试）"""
    try:
        engine = get_sync_engine()

        logger.warning("开始删除数据库表...")

        # 删除所有表
        Base.metadata.drop_all(bind=engine)

        logger.warning("数据库表删除成功")
        return True

    except Exception as e:
        logger.error(f"删除数据库表失败: {str(e)}")
        return False

def reset_database():
    """重置数据库（删除并重新创建表）"""
    logger.warning("重置数据库...")

    if drop_tables():
        return create_tables()
    else:
        return False

def check_database_connection():
    """检查数据库连接"""
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"数据库连接成功: {version}")
            return True
    except Exception as e:
        logger.error(f"数据库连接失败: {str(e)}")
        return False

async def async_create_tables():
    """异步创建数据库表"""
    from sqlalchemy.ext.asyncio import create_async_engine

    try:
        # 创建异步引擎
        db_url = str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(db_url)

        async with engine.begin() as conn:
            logger.info("开始异步创建数据库表...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表异步创建成功")

        await engine.dispose()
        return True

    except Exception as e:
        logger.error(f"异步创建数据库表失败: {str(e)}")
        return False

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库迁移工具")
    parser.add_argument("--action", choices=["create", "drop", "reset", "check"],
                       default="create", help="执行的操作")
    parser.add_argument("--async", dest="use_async", action="store_true",
                       help="使用异步模式（仅适用于create操作）")

    args = parser.parse_args()

    # 检查数据库连接
    if not check_database_connection():
        logger.error("无法连接到数据库，请检查配置")
        sys.exit(1)

    success = False

    if args.action == "create":
        if args.use_async:
            success = asyncio.run(async_create_tables())
        else:
            success = create_tables()

    elif args.action == "drop":
        success = drop_tables()

    elif args.action == "reset":
        success = reset_database()

    elif args.action == "check":
        success = check_database_connection()

    if success:
        logger.info(f"操作 '{args.action}' 完成")
        sys.exit(0)
    else:
        logger.error(f"操作 '{args.action}' 失败")
        sys.exit(1)

if __name__ == "__main__":
    main()