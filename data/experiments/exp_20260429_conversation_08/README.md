# exp_20260429_conversation_08

## 作用

本目录用于保存“会话持久化与前端交互功能测试”的实验材料。

该实验用于验证本次 FastAPI 前端改造是否可靠，包括：

- SQLite 会话持久化。
- 会话 CRUD API。
- `session_id` 聊天协议。
- 刷新/重启后的历史恢复。
- 前端三栏布局与静态资源缓存更新。

## 实验性质

该实验属于系统功能测试与回归测试，不属于 RAG 问答效果实验。因此不要与问答通过率、路由准确率等模型效果指标混合统计。

## 输入对象

| 模块 | 文件 |
|---|---|
| SQLite 存储 | `server/storage.py` |
| 会话 API | `server/api/conversations.py` |
| 聊天 API | `server/api/chat.py` |
| FastAPI 入口 | `server/main.py` |
| 前端页面 | `server/static/index.html` |
| 前端逻辑 | `server/static/app.js` |
| 前端样式 | `server/static/styles.css` |

## 数据库文件

生产运行时会话数据库为：

```text
data/conversations.sqlite3
```

自动 smoke test 使用临时 SQLite 文件，不写入生产数据库。

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 本实验说明。 |
| `conversation_test_metrics.csv` | 本实验需要验证的指标定义。 |
| `manual_test_checklist.csv` | 需要浏览器或服务重启参与的手工验证清单。 |
| `run_conversation_smoke.py` | 自动 API 级 smoke test，使用临时 SQLite 和 fake runtime。 |
| `conversation_smoke_report.json` | 自动 smoke test 运行结果。 |
| `conversation_smoke_results.csv` | 自动 smoke test 的逐项结果。 |
| `chart_prompt.md` | 功能测试图表生成 prompt。 |

## 自动测试命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260429_conversation_08\run_conversation_smoke.py
```

## 自动测试结果

运行时间：2026-04-29

| 指标 | 结果 |
|---|---:|
| 自动测试用例数 | 14 |
| 通过用例数 | 14 |
| 失败用例数 | 0 |
| 通过率 | 100.00% |
| 是否写入生产数据库 | 否 |

自动测试已验证：

- 会话列表初始状态。
- 新建会话。
- 读取空会话详情。
- 两轮聊天写入。
- 第二轮聊天由后端基于 `session_id` 自动读取上一轮历史。
- 聊天请求不再依赖前端传入 `history`。
- 消息顺序为 `user/assistant/user/assistant`。
- 首条用户消息自动生成标题。
- 会话重命名。
- 空消息校验。
- 无效 `session_id` 返回 404。
- 删除会话以及删除后不可读取。

详细结果见：

```text
conversation_smoke_report.json
conversation_smoke_results.csv
```

## 手工测试命令

启动服务：

```powershell
venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

浏览器访问：

```text
http://127.0.0.1:8000
```

## 论文写法建议

该实验可以写为“系统功能与持久化测试”。重点结论应围绕：

- 会话创建、加载、重命名、删除是否正确。
- 多轮聊天是否由后端基于 `session_id` 读取历史。
- 消息是否写入 SQLite。
- 刷新和重启后历史是否保留。
- 前端是否不再发送旧的 `history` 字段。
