# B0 可复现运行手册

本手册针对本机已经验证的 Windows Runtime + WSL UI 环境。工作根目录始终为 `D:\deepinsight-lite`。三个 upstream 仓库保留官方来源；不对它们执行 reset/clean，不升级 latest。所有命令由本轮实际安装/运行路径导出；后续重跑模型测试会使用现有账户额度。

## 1. 环境与精确版本

PowerShell：

```powershell
Set-Location D:/deepinsight-lite
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/environment.sh
git -C upstream/agent-ui rev-parse HEAD
git -C upstream/agno rev-parse HEAD
git -C upstream/agentos-docker rev-parse HEAD
```

应与 `b0/evidence/versions/repositories.json` 一致。Agno 为 v2.9.0、UI SHA 为 6dad9593fca6756e1813e4f4b3b2620be6377691。不要将 Docker 模板 main 的 v3.0.4 依赖安装进 v2 环境。

## 2. 依赖安装/重建

当前环境已安装；无需每次启动重新安装。仅重建时执行：

```powershell
Set-Location D:/deepinsight-lite
uv venv --python 3.12 b0/.venv-win
uv pip install --python b0/.venv-win/Scripts/python.exe -r b0/evidence/versions/requirements-win.lock.txt
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/setup-ui.sh
```

UI 安装脚本复用已安装 Linux Node 24.18.0，以固定 pnpm 10.34.5 执行 `install --frozen-lockfile`。没有改锁文件。若换电脑，先按其实际 Node 安装路径调整 **b0 脚本的环境 PATH** 并重新记录版本，不改官方业务源码。`b0/.venv` 是保留的 WSL 尝试环境，最终启动命令不使用它。

## 3. 模型配置

实际运行读取 `D:\deepinsight-lite\secrets\model.json`，未提交。字段：

```json
{
  "api_key": "YOUR_AUTHORIZED_API_KEY",
  "base_url": "https://YOUR_AUTHORIZED_OPENAI_COMPATIBLE_ENDPOINT/v1",
  "model": "EXACT_ID_RETURNED_BY_PROVIDER_MODELS_API",
  "provider": "YOUR_PROVIDER_DESCRIPTION"
}
```

模板占位符不能直接运行。现有配置已从授权环境安全写入；不要在前端填模型 API Key，不要输出该文件内容或将其加入 Git。当前 relay 实际返回 ID 为 `claude-sonnet-4-6`；底层身份未独立验证。直连 DeepSeek 的原配置已因余额不可用与模型 ID 不匹配停止使用，不能直接拿旧环境变量当已通过配置。

`b0/scripts/model_probe.py` 可执行一次短真实调用并保存响应（会使用额度）。`model_preflight.py` 做 models/balance 读取；balance 路径是供应商相关的，不存在时不能推定余额为零。

## 4. 启动官方最小示例

```powershell
Set-Location D:/deepinsight-lite
& ./b0/scripts/start-runtime.ps1
```

这启动 `b0/runtime-demo/agno_assist.py`，基于官方 Quickstart 的环境调整副本。只注册 Agno Assist，端口 7777。首次导入完成前健康接口可能暂不可连接，必须等待日志中的 `Application startup complete`。

```powershell
./b0/.venv-win/Scripts/python.exe b0/scripts/check-api.py
```

最小示例已实测；要执行 T01–T08，正常停止它并启动原生能力验证配置。

## 5. 启动完整 B0 验证配置

```powershell
Set-Location D:/deepinsight-lite
& ./b0/scripts/stop-runtime.ps1
& ./b0/scripts/start-runtime.ps1 -NativeTests
./b0/.venv-win/Scripts/python.exe b0/scripts/check-api.py
```

运行的是 Agno 原生 AgentOS，并非自建 FastAPI 替身。注册 `b0-agent`、`b0-skills`、`b0-team`、`b0-workflow`；SQLite 位于 `b0/runtime-demo/native.db`。打开 [API 文档](http://localhost:7777/docs)。`/info.agno_version` 应为 2.9.0。

## 6. 启动原版 UI

另一个 PowerShell 终端：

```powershell
Set-Location D:/deepinsight-lite
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/start-ui.sh
```

该脚本运行原版 `pnpm dev --turbopack --port 3100`。打开 [Agent UI](http://localhost:3100)，endpoint 设为 `http://localhost:7777`，选择 B0 Agent 或 Team。当前本地配置不要求 Auth Token。CORS 仅在 b0 运行副本中显式允许 localhost/127.0.0.1 的 3100。

第一次首页要等待编译与 hydration；页面刚返回 HTML 时侧栏可能尚在加载。以实体列表出现且能发起消息为准。

## 7. 执行真实测试

在根目录 PowerShell：

```powershell
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/run_native_tests.py agent
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/run_native_tests.py tools
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/run_native_tests.py sessions
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/run_native_tests.py workflow
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/run_native_tests.py team
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/run_native_tests.py skills
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/test_scheduler.py
./b0/.venv-win/Scripts/python.exe b0/smoke-tests/test_scheduler_failure.py
./b0/.venv-win/Scripts/python.exe b0/scripts/check-history.py before
& ./b0/scripts/stop-runtime.ps1
& ./b0/scripts/start-runtime.ps1 -NativeTests
```

等待服务就绪，然后：

```powershell
./b0/.venv-win/Scripts/python.exe b0/scripts/check-history.py after
./b0/.venv-win/Scripts/python.exe b0/scripts/verify-evidence.py
./b0/.venv-win/Scripts/python.exe b0/scripts/performance-summary.py
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/check-ui.sh
```

每个 PowerShell 命令都应检查 `$LASTEXITCODE`；不能在前一步失败后拿旧证据宣称本轮通过。Scheduler 自然触发脚本最长观测 160 秒、2 秒一次查询；这不是立即触发。首次观察到运行行后立即 disable，完成后再次核对，正常/失败路径均保存凭据。若关闭 API 导致停用失败，脚本必须失败；先恢复该 Runtime，再按已保存 Schedule ID 调用 `POST /schedules/{id}/disable`，确认 `enabled=false`。不要反复创建每分钟付费任务。

失败状态脚本针对不存在的 Agent，预期得到 404/failed，且不发起模型调用。它与自然成功测试分开记录。

浏览器验收必须另做：两个指定问题、显式工具请求、打开 Session、刷新、重启服务再打开、切换 Team 并执行。API 语义检查脚本不是浏览器验收替代品。原版 UI 无 Workflow 管理入口，后端测试走原生 API。

## 8. 日志与证据

- Runtime stdout/stderr：`b0/evidence/logs/runtime-*.log`。启动脚本当前日志会覆盖；重启前应保存快照，本轮已有对应 snapshots。
- UI：终端输出；本轮 `ui-start-turbo.log` 保存成功启动记录。
- API：`b0/evidence/api-results/`；T01–T08 及 UI SSE、CORS、语义检查。
- 截图：`b0/evidence/screenshots/`。编号 04、13 是保留的异常证据，不当作通过截图。
- 版本、依赖、资源：`b0/evidence/versions/`；目录清单及 hashes 见最终 manifest。

## 9. 生产 build 检查

先结束浏览器测试，再停止本项目 UI，避免 Next dev 与 build 争用 `.next`：

```powershell
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/stop-ui.sh
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/build-ui.sh
```

不绕过 lint/typecheck。结果以 `B0_TEST_REPORT.md` 和 `ui-build.log` 为准。结束后再次运行 start-ui.sh 恢复本地开发页面。

## 10. 停止与下次启动

本机默认Webpack路径出现编译停滞；实际通过的完整生产构建命令为：

```powershell
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/build-ui.sh --turbopack
```

构建脚本设置300秒上限，超时非零退出，不允许把只完成编译阶段当作完整构建通过。本轮Turbopack构建已完成全部阶段，日志在`ui-build-turbo.log`。运行build前仍须先停止本项目UI，构建结束再用start-ui.sh启动。

```powershell
Set-Location D:/deepinsight-lite
wsl -d Ubuntu -- bash /mnt/d/deepinsight-lite/b0/scripts/stop-ui.sh
& ./b0/scripts/stop-runtime.ps1
```

先确认 `/schedules` 所有本轮测试行 `enabled=false`。停止脚本只处理校验为本轮所属的服务；不会为释放端口终止其他项目。

下次无需重新安装，直接 `start-runtime.ps1 -NativeTests` 与 `start-ui.sh`；保留 native.db 即可恢复 Session 与调度历史。当前所有测试调度应处于停用状态，不在启动时自动创建业务任务。B0 完成后停止业务扩展，等待负责人审核再开始 B1。
