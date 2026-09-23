# 字幕时间漂移校正工具（Subtitle Time Drift Fixer）

用 **Python + FastAPI + 原生 HTML/JS** 实现的小型 Web 工具：粘贴 SRT 字幕，给出若干组人工确认的
**「原时间 → 正确时间」锚点**，即可校正整份字幕的时间轴（支持整体平移与变速漂移），
在页面上预览校正结果并下载新的 SRT 文件。

## 校正规则

- **分段线性映射**：相邻两个锚点之间做线性插值。
- **锚点外沿用最近区段斜率外推**：
  - 第一个锚点之前：使用第 1、2 个锚点确定的直线（只有 1 个锚点时斜率为 1，即整体平移）；
  - 最后一个锚点之后：使用最后两个锚点确定的直线。
- **严格递增校验（不满足则拒绝生成并返回原因）**：
  - 所有锚点的**原时间**必须互不相同（按数值严格递增）；
  - 按原时间排序后，**正确时间**也必须严格递增（不能相等或倒退）。
- **只改时间，不动内容**：字幕序号与文本（含多行文本）原样保留。
- 锚点无需按顺序填写，后端按原时间自动排序；时间格式为 `HH:MM:SS,mmm`
  （也兼容 `HH:MM:SS.mmm`）。

## 单条启动命令（Docker Compose，推荐）

```bash
docker compose up -d --build
```

启动后访问：

- 地址： **http://localhost:8000**
- 端口：容器内固定 **8000**；宿主机默认映射 **8000**

修改宿主机端口（例如改用 8080）：

```bash
PORT=8080 docker compose up -d --build      # 然后访问 http://localhost:8080
```

或直接修改 `docker-compose.yml` 中 `"${PORT:-8000}:8000"` 左侧的端口。

停止服务：

```bash
docker compose down
```

## 不用 Docker 的本地启动方式

需要 Python 3.11+。

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 或：python -m app.main
```

同样访问 http://localhost:8000 。

## 必要配置（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 直接以 `python -m app.main` 运行时的监听端口；Compose 中容器内端口固定为 8000，宿主机端口用同名变量映射 |
| `HOST` | `0.0.0.0` | 监听地址，一般无需修改 |

除上述变量外无其他配置：不依赖数据库，不写磁盘，不需要任何密钥。

## 使用步骤

1. 打开 http://localhost:8000；
2. 将完整 SRT 粘贴到第一个文本框（可点「填入示例」快速体验）；
3. 在锚点表格中填写至少 1 组「原时间 → 正确时间」，需要时点「+ 添加锚点」；
   - 1 组锚点：整体平移；
   - 2 组及以上：分段线性校正，可处理前段快、后段慢之类的变速漂移；
4. 点「校正字幕」：
   - 通过校验时，页面下方按条目展示 `原时间 → 校正后时间`、偏移量与文本，
     并显示生效锚点和各区段斜率，点「下载校正后的 SRT」即可下载；
   - 校验失败时（如正确时间倒退、SRT 格式错误、结果早于 00:00:00,000），
     页面顶部红框会给出具体原因（包括是第几组锚点）。

## HTTP 接口

- `GET /`：网页界面
- `POST /api/correct`：执行校正

  ```json
  {
    "srt": "1\n00:00:01,000 --> 00:00:03,000\n你好\n",
    "anchors": [
      {"old_time": "00:00:10,000", "new_time": "00:00:12,000"},
      {"old_time": "00:01:00,000", "new_time": "00:01:05,000"}
    ]
  }
  ```

  成功返回 `ok: true`、逐条校正结果与可直接保存的 SRT 文本（`srt` 字段）；
  校验失败返回 HTTP 400：`{"ok": false, "error": "原因说明"}`。

- `GET /api/health`：健康检查（Docker HEALTHCHECK 使用）

## 运行测试

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## 项目结构

```
.
├── app/
│   ├── main.py          # FastAPI 路由与接口
│   ├── srt.py           # SRT 解析 / 序列化（保留序号与文本）
│   ├── alignment.py     # 锚点校验 + 分段线性映射（含外侧斜率外推）
│   └── corrector.py     # 校正流程编排
├── static/
│   └── index.html       # 轻量网页界面（原生 JS，无构建步骤）
├── tests/               # pytest 单元与接口测试
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```
