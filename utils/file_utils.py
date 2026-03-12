"""文件操作工具"""

import os
import shutil
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
import aiofiles
import aiofiles.os

from config.settings import settings

async def save_uploaded_file(
    file_content: bytes,
    filename: str,
    directory: Optional[str] = None,
    overwrite: bool = False
) -> str:
    """
    保存上传的文件

    Args:
        file_content: 文件内容（字节）
        filename: 文件名
        directory: 保存目录（默认为上传目录）
        overwrite: 是否覆盖已存在的文件

    Returns:
        保存的文件路径
    """
    if directory is None:
        directory = settings.upload_dir

    # 确保目录存在
    os.makedirs(directory, exist_ok=True)

    # 清理文件名
    safe_filename = sanitize_filename(filename)

    # 生成完整路径
    filepath = os.path.join(directory, safe_filename)

    # 处理文件名冲突
    if not overwrite and os.path.exists(filepath):
        filepath = generate_unique_filename(filepath)

    # 保存文件
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(file_content)

    return filepath

async def read_file_safely(filepath: str, max_size: Optional[int] = None) -> bytes:
    """
    安全读取文件

    Args:
        filepath: 文件路径
        max_size: 最大文件大小（字节）

    Returns:
        文件内容（字节）
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # 检查文件大小
    file_size = os.path.getsize(filepath)
    if max_size is not None and file_size > max_size:
        raise ValueError(f"文件大小超过限制: {file_size} > {max_size}")

    # 读取文件
    async with aiofiles.open(filepath, "rb") as f:
        content = await f.read()

    return content

def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除危险字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    # 移除路径分隔符
    filename = os.path.basename(filename)

    # 定义危险字符
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')

    # 限制长度
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext

    return filename

def generate_unique_filename(filepath: str) -> str:
    """
    生成唯一的文件名

    Args:
        filepath: 原始文件路径

    Returns:
        唯一的文件路径
    """
    directory, filename = os.path.split(filepath)
    name, ext = os.path.splitext(filename)

    counter = 1
    while os.path.exists(filepath):
        new_filename = f"{name}_{counter}{ext}"
        filepath = os.path.join(directory, new_filename)
        counter += 1

    return filepath

def calculate_file_hash(filepath: str, algorithm: str = "sha256") -> str:
    """
    计算文件哈希值

    Args:
        filepath: 文件路径
        algorithm: 哈希算法（sha256, md5等）

    Returns:
        文件哈希值
    """
    hash_func = hashlib.new(algorithm)

    with open(filepath, "rb") as f:
        # 分块读取，避免大文件内存问题
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return hash_func.hexdigest()

async def calculate_file_hash_async(filepath: str, algorithm: str = "sha256") -> str:
    """
    异步计算文件哈希值

    Args:
        filepath: 文件路径
        algorithm: 哈希算法

    Returns:
        文件哈希值
    """
    hash_func = hashlib.new(algorithm)

    async with aiofiles.open(filepath, "rb") as f:
        # 分块读取
        chunk = await f.read(4096)
        while chunk:
            hash_func.update(chunk)
            chunk = await f.read(4096)

    return hash_func.hexdigest()

def get_file_info(filepath: str) -> dict:
    """
    获取文件信息

    Args:
        filepath: 文件路径

    Returns:
        文件信息字典
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    stat = os.stat(filepath)

    # 猜测MIME类型
    mime_type, encoding = mimetypes.guess_type(filepath)

    return {
        "filename": os.path.basename(filepath),
        "filepath": filepath,
        "size": stat.st_size,
        "created_at": stat.st_ctime,
        "modified_at": stat.st_mtime,
        "accessed_at": stat.st_atime,
        "mime_type": mime_type or "application/octet-stream",
        "encoding": encoding,
        "is_file": os.path.isfile(filepath),
        "is_dir": os.path.isdir(filepath),
    }

async def ensure_directory(directory: str) -> None:
    """
    确保目录存在（异步）

    Args:
        directory: 目录路径
    """
    await aiofiles.os.makedirs(directory, exist_ok=True)

def clean_directory(directory: str, pattern: str = "*", age_days: Optional[int] = None) -> int:
    """
    清理目录中的文件

    Args:
        directory: 目录路径
        pattern: 文件模式（glob格式）
        age_days: 删除多少天前的文件

    Returns:
        删除的文件数量
    """
    if not os.path.exists(directory):
        return 0

    deleted_count = 0
    import glob
    import time

    current_time = time.time()
    for filepath in glob.glob(os.path.join(directory, pattern)):
        if os.path.isfile(filepath):
            # 检查文件年龄
            if age_days is not None:
                file_age = current_time - os.path.getmtime(filepath)
                if file_age < age_days * 24 * 3600:
                    continue

            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"删除文件失败 {filepath}: {e}")

    return deleted_count

def split_file_by_size(filepath: str, max_chunk_size: int) -> list:
    """
    按大小分割文件

    Args:
        filepath: 文件路径
        max_chunk_size: 最大块大小（字节）

    Returns:
        块文件路径列表
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    file_size = os.path.getsize(filepath)
    if file_size <= max_chunk_size:
        return [filepath]

    chunks = []
    chunk_dir = os.path.join(os.path.dirname(filepath), "chunks")
    os.makedirs(chunk_dir, exist_ok=True)

    with open(filepath, "rb") as f:
        chunk_index = 0
        while True:
            chunk_data = f.read(max_chunk_size)
            if not chunk_data:
                break

            chunk_filename = f"{os.path.basename(filepath)}.chunk{chunk_index:03d}"
            chunk_filepath = os.path.join(chunk_dir, chunk_filename)

            with open(chunk_filepath, "wb") as chunk_file:
                chunk_file.write(chunk_data)

            chunks.append(chunk_filepath)
            chunk_index += 1

    return chunks

async def copy_file_async(src: str, dst: str, overwrite: bool = False) -> bool:
    """
    异步复制文件

    Args:
        src: 源文件路径
        dst: 目标文件路径
        overwrite: 是否覆盖已存在的文件

    Returns:
        是否成功
    """
    if not await aiofiles.os.path.exists(src):
        raise FileNotFoundError(f"源文件不存在: {src}")

    if not overwrite and await aiofiles.os.path.exists(dst):
        raise FileExistsError(f"目标文件已存在: {dst}")

    # 确保目标目录存在
    dst_dir = os.path.dirname(dst)
    await ensure_directory(dst_dir)

    # 复制文件
    async with aiofiles.open(src, "rb") as src_file:
        content = await src_file.read()

    async with aiofiles.open(dst, "wb") as dst_file:
        await dst_file.write(content)

    return True

__all__ = [
    "save_uploaded_file",
    "read_file_safely",
    "sanitize_filename",
    "generate_unique_filename",
    "calculate_file_hash",
    "calculate_file_hash_async",
    "get_file_info",
    "ensure_directory",
    "clean_directory",
    "split_file_by_size",
    "copy_file_async",
]