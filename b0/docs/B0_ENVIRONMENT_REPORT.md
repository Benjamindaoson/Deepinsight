# B0 环境报告

核验日期：2026-10-17（Asia/Shanghai）。工作根目录：`D:\deepinsight-lite`。本轮开始时根目录为空。未访问 A 路线项目，未创建 B1 业务代码。

## 已观测环境

| 项目 | 实际版本 / 状态 | 证据 |
|---|---|---|
| Windows | Windows 11 家庭中文版，OS 10.0.26300 / build 26300；WMI 的 WindowsProductName 仍显示旧名称，保留原始差异 | `evidence/versions/windows.json` |
| WSL | Ubuntu，WSL2；Linux 6.6.114.1-microsoft-standard-WSL2 x86_64 | 同上 |
| WSL 默认 Python | 3.14.4；没有用于选定 Runtime | 同上 |
| WSL 验证环境 | CPython 3.12.14，`b0/.venv` | 安装实测；保留环境 |
| 最终 Runtime 环境 | Windows CPython 3.12.10，`b0/.venv-win` | `versions/requirements-win.lock.txt` |
| WSL Node | 24.18.0，复用 `/home/benjamin/.nvm/versions/node/v24.18.0/bin` | `logs/ui-install.log` |
| npm | UI 实际使用 11.16.0；最初 PATH 中还存在 Windows npm | 同上、environment.log |
| pnpm | 最终 10.34.5；WSL 原默认 11.15.1 不适用该锁文件配置 | 同上 |
| Git | WSL 2.53.0 | environment.log |
| uv | 已存在 `/home/benjamin/.local/bin/uv`，Windows uv 也可用；精确版本补充于 `versions/toolchain-final.json` | 版本凭据 |
| Docker / Compose | 29.8.1 / v5.5.1；本方案无需容器 | environment.log |
| 数据库 | 原生 SqliteDb；本地 `b0/runtime-demo/native.db` | T03、T07、T08 |

未发现已安装 Node 22；使用已有且实际跑通 Next.js 15.5.18 的 Node 24.18.0，没有覆盖系统版本。Agno 2.9.0 的声明 Python 范围是 `>=3.9,<4`，3.12 在支持范围内。

## 端口与隔离

初始 WSL 监听记录中存在其他服务，未停止这些服务。B0 仅使用前端 3100、Runtime 7777。启动脚本遇到占用会拒绝启动；停止脚本核对本项目目录、记录的 launcher 与进程关系。Runtime 绑定 Windows loopback；UI 使用官方 Next 开发服务器，属于本地开发验收，未实施生产网络隔离。模型密钥只在后端读取。

## 安装与环境问题

1. 完整 `git clone` Agno 下载中发生 `GnuTLS recv error (-9)` / `early EOF`。改为同一官方来源 `git clone --depth 1 --branch v2.9.0 ...`，成功取得明确标签。没有用自建实现替代。
2. WSL 默认 pnpm 11 忽略 `package.json` 的 `pnpm.overrides`，`--frozen-lockfile` 报 `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`。改用 `npm exec --package=pnpm@10.34.5` 后冻结安装成功。没有修改包清单或锁文件。安装日志保留 sharp 构建脚本未批准的提示；文本聊天不依赖该脚本，未以此跳过检查。
3. WSL 挂载盘首次 Python 导入持续超过 5 分钟，进程处于 `p9_client_rpc` I/O 等待。依据任务允许的环境例外，最终后端使用同项目内 Windows 独立 `.venv-win`；同一 Agno 2.9.0，没有第二套 Agent 框架。Windows 首次 `AgentOS` 导入实测约 12.53 秒。
4. 原 `sqlalchemy==2.1.5` 导入 asyncio 模块要求 greenlet。安装 `sqlalchemy[asyncio]==2.1.5`，取得 greenlet 3.5.6 后服务启动。
5. 原版 `pnpm dev --port 3100` 的 Webpack 首页编译停滞，并输出字体请求超时。使用官方支持的 `--turbopack` 参数后首页编译 29.4 秒、HTTP 200；无源码/Next 配置调整。
6. 默认 Runtime CORS 不允许来源 `http://localhost:3100`，预检 HTTP 400。在 **b0 运行副本** 使用官方 `cors_allowed_origins` 配置显式加入本地 3100 后 HTTP 200。见 `cors-before.json` / `cors-after.json`。

## 实际环境命令

在 Windows 根目录执行：

```powershell
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/environment.sh
uv venv --python 3.12 D:/deepinsight-lite/b0/.venv-win
uv pip install --python D:/deepinsight-lite/b0/.venv-win/Scripts/python.exe "agno[os]==2.9.0" openai "sqlalchemy[asyncio]==2.1.5"
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/setup-ui.sh
& D:/deepinsight-lite/b0/scripts/start-runtime.ps1 -NativeTests
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/start-ui.sh
```

首次安装后已冻结完整依赖，重建优先用锁定清单，详见 RUNBOOK。运行日志、凭据、虚拟环境均未提交到官方仓库。

## 资源与耗时

恢复开发服务后的 Runtime 工作集快照为144,695,296 bytes（约138 MiB）；UI开发服务器在首次编译后 RSS 约1,054,776 KiB（约1.01 GiB）。这是本次本机进程快照，不是生产模式内存测量，不能据“Lite”名称宣称低内存。`ps %CPU` 是进程累计平均，不解释成瞬时空闲CPU。

后端 restart-to-health 实测 **7.884 秒**；此值包含启动脚本与轮询开销，不是冷启动基准。UI Turbopack `Ready` **20.4 秒**，首次首页请求 **32.489 秒**；后续已观测请求 847ms。它们是一次本机测量，不代表 SLA。空闲内存与每类请求/Token 见 `versions/runtime-resources.json`、`versions/ui-resources.log`、`api-results/performance-summary.json`。未测量项在机器凭据中标为 `NOT MEASURED`。必要应用服务为 UI + AgentOS 两项；SQLite 无独立服务，不需要 PostgreSQL、Redis 或额外调度框架。
