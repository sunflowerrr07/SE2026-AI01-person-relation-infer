# M3 图关系推理与查询优化

本轮实现 PyTorch Geometric 推理模块、M2 窗口数据转换、模型权重保存恢复，以及任务隔离的多跳图查询。训练数据和真实 Neo4j 服务未提供，因此不宣称达到关系准确率 0.80，也不宣称真实数据库响应已验证小于 1 秒。

本轮验证结果：73 项通过、1 项真实 Neo4j 集成测试跳过；后端与算法代码合计行覆盖率 92.17%，`pip check` 通过。沿用环境有一条 Starlette 测试客户端弃用提示，不影响测试通过。

## GNN 输入与输出

`ai_pipeline.gnn.build_graph(cooccurrence, entity_features)` 接收对称、零对角线、取值 `[0,1]` 的 `N×N` 共现强度矩阵，以及与节点顺序一致的有限值 `N×F` 特征。生成真实 PyG `Data`，每条非零共现边转换成两个带权方向。

`RelationGNN(input_dim, hidden_dim=16)` 使用两层 `GCNConv`；将节点嵌入逐元素乘积与该对共现权重拼接，交给 MLP 输出 logit。对称解码确保 A-B 与 B-A 相同。`predict_relations(...)` 使用 sigmoid 输出二分类关联概率，默认预测已有共现的无向节点对，也可传入显式候选索引对，支持孤立节点和空边图。

每条结果包括 `source`、`target`、`probability`、`uncertain`、`model_version` 和 `model_status`。无训练权重时状态为 `untrained`，所有结果标记不确定；训练标志仅为检查点元数据，并非精度证明。当前输出尚未做概率校准，不表示朋友、亲属或同事等现实关系。

模型使用 `save_checkpoint` 和 `load_checkpoint` 保存/恢复结构参数、权重和版本；加载使用 `weights_only=True`，默认映射到 CPU。实际部署还需配套固定特征归一化、训练数据划分、标签、模型评测与阈值校准。

## 本机可复现运行

本机已安装 `torch 2.6.0+cpu` 和 `torch-geometric 2.6.1`，未安装 CUDA 版。新环境：

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r ai_pipeline/requirements-gnn.txt
.\.venv\Scripts\python.exe -m ai_pipeline.run --source ai_pipeline/examples/frames --mode mock --fps 10 --window-seconds 1 --output data/m2-mock-demo.json
.\.venv\Scripts\python.exe -m ai_pipeline.gnn_run --input data/m2-mock-demo.json --features ai_pipeline/examples/entity_features.json --output data/m3-gnn-demo.json
```

示例实体特征也是手工合成值，只用于验证数据流。每个 M2 时间窗口单独构图，不混合窗口；缺失实体特征、重复无向边、非法权重及无效时间范围会报错。输出保留 `synthetic_input` 和 `probability_calibrated: false`。没有 `--checkpoint` 时使用固定种子初始化实验模型；有训练权重后可加 `--checkpoint data/model.pt`。

## 多跳查询

入口：`GET /api/v1/graph/persons/{person_id}/neighbors?task_id=...&max_hops=2&limit=100`，沿关联边双向搜索，返回人员及最小跳数，不包含起点。最多 4 跳、最多 1,000 个结果；默认按跳数及人员标识排序。复用已有令牌鉴权、任务所有权检查及持久化审计。

- 内存仓储：写入时维护任务内邻接索引，查询用 BFS，避免每跳扫描所有关系；删除边/节点时维护索引。
- Neo4j：启动时创建 `(task_id, person_id)` 组合唯一约束和推断关系任务索引。查询从索引支持的起点展开，检查路径中所有节点及关系的任务范围，限制深度和返回数量。
- Neo4j 查询使用 0.8 秒数据库执行超时及自动提交会话，避免托管事务自动重试延长查询；数据库报告事务超时时 API 返回 504，而非伪造空结果。
- 数据库执行超时不等于端到端耗时保证：网络、连接获取、服务负载和路径规模仍会影响响应。真实部署须运行集成测试及性能评测，再确认小于 1 秒的验收目标。

## 本机性能记录

Windows、Python 3.12.14；内存链式图 5,000 节点、4,999 边；中间节点查询 4 跳，100 次串行查询，每次返回 8 个节点。仅统计仓储查询，不含建图、HTTP 或网络。

| 指标 | 本次实测 |
| --- | --- |
| P50 | 0.0035 毫秒 |
| P95 | 0.0041 毫秒 |
| 最大 | 0.0224 毫秒 |

单元测试另有内存多跳 API 的小于 1 秒断言。真实 Neo4j 集成测试在配置 `TEST_NEO4J_*` 后验证 CRUD、多跳结果和小于 1 秒断言；未配置时明确跳过。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=backend/app --cov=ai_pipeline --cov-report=term-missing --cov-fail-under=80
.\.venv\Scripts\python.exe -m pip check
```

覆盖真实 GCN 前向和梯度、已知 logit 对应概率、对称性、非法图、空图候选、检查点恢复、M2 桥接与命令行、任务隔离、邻接索引删除一致性、循环图最短跳数、参数边界、数据库超时处理及本机耗时。训练准确率和真实 Neo4j 服务延迟保留为后续实测项。
