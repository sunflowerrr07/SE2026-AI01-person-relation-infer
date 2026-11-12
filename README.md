# SE2026-AI01-person-relation-infer
基于图像数据的人员关系推断与判别系统，使用YOLOv8、ByteTrack、PyTorch Geometric、Neo4j、FastAPI、Vue3实现。

项目规范见 [AGENTS.md](AGENTS.md)，分阶段计划见 [开发计划](docs/superpowers/plans/2026-11-12-development-plan.md)。

## 本地 Python 环境

项目使用 Python 3.12。Windows PowerShell 中：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

`.venv` 不提交仓库；重建时用可用 Python 3.12 执行 `python -m venv .venv`。虚拟环境依赖创建它的 Python，本机使用 Codex 自带运行时，升级或移动后须重建。

当前后端为开发中版本，可通过环境变量配置单个开发用户并启动：

```powershell
$env:API_USER = 'developer'
$env:API_TOKEN = '<自行生成的强随机令牌>'
$env:GRAPH_REPOSITORY = 'memory'
python -m uvicorn backend.app.config:create_from_environment --factory
```

SQLite 任务和审计记录默认位于 `data/`，可用 `APP_DATA_DIR` 调整。此开发配置尚不具备完整用户管理、媒体授权和生产安全控制，不可用于真实敏感数据。内存图谱在进程重启后丢失。

## Neo4j 配置

M1 将支持内存仓储和真实 Neo4j 仓储。内存模式仅供本地开发和单元测试，数据不持久化，也不验证 Neo4j 的 Cypher、约束或连接行为；上线或集成验证必须使用真实数据库，禁止故障时静默回退。

1. 本地：安装 [Neo4j Desktop](https://neo4j.com/download/)，创建并启动数据库，设置凭据。使用 `bolt://localhost:7687`，确认 Bolt 端口可达。
2. 云端：在 [Neo4j Aura](https://neo4j.com/cloud/aura/) 创建可用免费实例，保存控制台提供的连接 URI、用户名和密码；使用加密 `neo4j+s://` URI。
3. M1 实现时通过环境变量 `GRAPH_REPOSITORY=neo4j`、`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`、`NEO4J_DATABASE` 注入配置；内存模式显式设置 `GRAPH_REPOSITORY=memory`。不要提交凭据。启动后先验证连接，再运行真实数据库集成测试。这些变量是计划契约，当前尚无服务读取。

## M2 时安装 AI 依赖

当前不安装大型 AI 依赖。以下为 Windows、Python 3.12、CUDA 12.6 候选命令；安装前在 [PyTorch](https://pytorch.org/get-started/previous-versions/) 和 [PyG](https://pytorch-geometric.readthedocs.io/en/latest/install/installation.html) 核对版本与 wheel 兼容性。驱动支持 CUDA 12.6 不代表已安装 CUDA Toolkit，实际可用性以 PyTorch 检查为准。

```powershell
python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu126
python -m pip install torch-geometric ultralytics
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

PyG 可选原生扩展应根据最终 PyTorch/CUDA 组合从对应 wheel 页面单独安装，不要混用版本。GPU 不可用时先检查驱动和 wheel。
