-- PostgreSQL初始化脚本
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- 用于文本相似性搜索
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- 用于GIN索引优化

-- 设置时区
SET timezone = 'UTC';

-- 创建额外用户（可选）
-- CREATE USER readonly WITH PASSWORD 'readonly_password';
-- GRANT CONNECT ON DATABASE aidevplatform TO readonly;
-- GRANT USAGE ON SCHEMA public TO readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;