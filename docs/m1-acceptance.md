# M1 核心后端验收记录

日期：2026-11-12。状态：按用户缩定范围完成并封存。

已交付：FastAPI 基础配置和路由、受控 Bearer Token 鉴权与任务所有权检查、SQLite 任务状态及审计、匿名标识和基础字段脱敏、内存图 CRUD、Neo4j 参数化图 CRUD 适配与模拟驱动测试。

验证命令：`.venv/Scripts/python.exe -m pytest --cov=backend/app --cov-report=term-missing --cov-fail-under=80`。

结果：16 passed、1 skipped，后端行覆盖率 95.30%。内存图查询接口含响应时间小于 1 秒断言。真实 Neo4j 测试因未配置数据库跳过，不能据此声称真实数据库性能或并发约束已通过。测试依赖有一条 Starlette 测试客户端弃用提示。

经用户同意延期：媒体授权及上传、完整用户管理与 JWT、分页筛选、其他完整接口契约、真实 Neo4j 约束/并发/性能验证。当前封存为本地实验后端基线，默认内存图数据不持久化，SQLite 审计不具备外部防篡改保证。
