# M2 视觉感知与时空共现

M3 已新增 PyG GNN 推理与多跳查询接口，安装、输入约定和完整示例见 [M3 实现说明](../docs/m3-implementation.md)。

本轮交付本地媒体读取、Mock 轨迹、YOLOv8 + ByteTrack 适配器和共现强度计算。Mock 无需训练、GPU 或模型权重；OpenCV 负责解码本地文件。真实 YOLO 模式尚未在本机运行验证，跨镜头 ReID、算法评测和后端任务接入属于后续 M2 工作。

## 快速运行

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r ai_pipeline/requirements.txt
.\.venv\Scripts\python.exe -m ai_pipeline.run --source ai_pipeline/examples/frames --mode mock --fps 10 --window-seconds 1 --output data/m2-mock-demo.json
```

内置三个 PPM 图片仅用于可复现的解码验证，不含人员。Mock 对每个解码帧固定生成两个缓慢平移的合成轨迹，不分析画面；预期得到 3 帧、1 条窗口关系，共现时长 0.3 秒、归一化中心距离 0.2、强度约 0.42。输出的 `synthetic: true` 必须保留，不可将其用于准确率或真实关系结论。

本地短视频或有序图片文件夹使用同一个入口：

```powershell
.\.venv\Scripts\python.exe -m ai_pipeline.run --source 'D:\videos\short.mp4' --mode mock --max-frames 300 --window-seconds 10 --output data/video-mock.json
.\.venv\Scripts\python.exe -m ai_pipeline.run --source 'D:\images\sequence' --mode mock --fps 5 --output data/images-mock.json
```

图片按自然文件名顺序排列（frame2 在 frame10 之前）；`--fps` 决定图片序列的时间间隔。视频使用容器中的固定帧率，当前不支持变帧率精确时间戳。每次运行是一个独立序列，最多处理 300 帧，可用 `--max-frames` 调整。文件夹应来自同一连续场景；不能把互不相关的图片视作连续时间证据。

## 真实检测追踪入口

根据根目录 README 安装兼容版本的 PyTorch、Ultralytics 后，准备本地 YOLOv8 `.pt` 权重再运行：

```powershell
.\.venv\Scripts\python.exe -m ai_pipeline.run --source 'D:\videos\short.mp4' --mode yolo --weights 'D:\models\yolov8n.pt' --output data/video-yolo.json
```

适配器调用 Ultralytics `track`，固定 `classes=[0]`（人员）、`tracker='bytetrack.yaml'`、`persist=True`，输出归一化框及序列内跟踪 ID。未找到本地权重时直接报错；Mock 模式不会导入 Ultralytics。没有检测或跟踪 ID 的帧不会生成轨迹。Track ID 不等于跨镜头匿名人员身份；本轮不执行 ReID。

## 数据与计算约定

`media.py` 流式输出解码图像、相对秒时间戳及帧持续时间；`tracking.py` 输出 `track_id` 与归一化 `bbox=[x1,y1,x2,y2]`；`cooccurrence.py` 接收不重叠的时间区间和轨迹列表，输出窗口关系。

- 时间窗口从零开始，采用半开区间 `[start,end)`。跨窗口帧按时长拆分，缺失检测不补时长。
- 每帧同一 ID 只能出现一次；无效坐标、重复 ID、负时间、乱序或真实重叠均拒绝。纳秒级浮点舍入误差允许容差。
- 每对轨迹仅生成一个无向统计键，ID 排序以避免 A-B 与 B-A 重复，不生成自关系。
- `co_occurrence_count` 是窗口内共同被检测到的帧数，不是独立互动事件数；距离为框中心在归一化图像平面的欧氏距离，不能当作米制距离。
- `cooccurrence-v1` 强度公式：`0.6 × (共现时长 / 窗口时长) + 0.4 × max(0, 1 - 平均距离 / 0.5)`，值域为 `[0,1]`。平均距离按共现时长加权。该公式是可解释实验基线，尚未经数据标定，不代表关系概率。
- 输出记录 Mock 标志、序列范围、算法版本和证据统计。当前结果写入 JSON 文件，尚未自动入图或触发后端任务完成。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=backend/app --cov=ai_pipeline --cov-report=term-missing --cov-fail-under=80
```

测试包括手算共现结果、窗口边界、缺帧、浮点帧率、错误输入、图片自然排序、MJPG 短视频解码、Mock 命令行运行和真实适配器的模拟模型边界调用。真实 Neo4j 集成测试需显式配置，真实 YOLO 推理需本地权重另行验证。
