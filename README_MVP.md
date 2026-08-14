# Pangdun KOL / Media CRM MVP

这是一个给硬件品牌内部试用的局域网 CRM，用来管理媒体、红人、联系人、推广项目、寄样物流、费用与内容产出。

## 如何启动

1. 第一次双击 `start.bat`。它会在桌面创建带胖墩西高地图标的 `Pangdun CRM` 快捷方式。
2. 已交付数据库的日常启动会完全在后台运行，准备完成后自动打开浏览器，不需要保留命令行窗口。
3. 以后直接双击桌面的 `Pangdun CRM` 即可；仓库移动位置后重新运行一次 `start.bat` 可更新快捷方式。
4. 全新空库首次启动需要安装依赖并创建管理员，因此只在这一次显示安装窗口。直接回车会创建 `admin@example.local / admin123456`。
5. 需要关闭后台服务时双击 `stop.bat`。启动失败日志位于 `backend\data\crm-start.log`。

## 如何访问

- 本机访问：`http://127.0.0.1:8000`
- 局域网访问：启动窗口会显示类似 `http://192.168.1.23:8000` 的地址。

其他同事需要连接同一个公司局域网，然后在浏览器打开这台主机显示的局域网地址。

## 开发验证

安装后端测试依赖：

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

运行后端 API 集成测试：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

运行前端交互测试与生产构建：

```powershell
cd frontend
npm test
npm run build
```

后端测试使用临时 SQLite 数据库，不会读取或改写 `backend/data/kol_crm.db`。

## 查看本机局域网 IP

打开命令提示符，运行：

```bat
ipconfig
```

找到 `IPv4 地址`，通常形如 `192.168.x.x`、`10.x.x.x` 或 `172.16.x.x`。

## 防火墙放行 8000 端口

如果别人打不开网页：

1. 打开 Windows Defender 防火墙。
2. 进入“高级设置”。
3. 新建“入站规则”。
4. 类型选择“端口”。
5. TCP，端口填写 `8000`。
6. 选择“允许连接”。
7. 勾选当前网络环境。
8. 名称填写 `Pangdun CRM 8000`。

## 关闭自动睡眠

运行 CRM 的电脑不要自动睡眠：

1. 打开“设置”。
2. 进入“系统 / 电源和电池”。
3. 将“睡眠”调整为“从不”或足够长。

## 导入历史媒体库

1. 登录 Admin 账号。
2. 进入“Excel 导入”。
3. 选择 `红人库.xlsx`。
4. 先点“预览”，确认字段和行数。
5. 再点“确认导入”。

导入不会覆盖已有媒体。系统按“媒体名称 + 链接”去重；没有链接时按“媒体名称 + 国家”辅助去重。

## 导入费用统计表

1. 登录 Admin 账号，进入“费用表导入”。
2. 选择 `费用统计表.xlsx`。
3. 先点“审核预览”，检查项目编号、执行状态、产品、物流单号和需要确认的提示。
4. 确认后点击“确认导入”。

导入会创建项目、合作执行单、寄样、费用和内容链接记录。含 `OA PI编号` 的行按编号归入同一个项目；缺少该编号的行会进入“历史导入待归类”，避免系统猜错项目。原始 Excel 不会被修改。

## 日常使用

1. 在“推广项目”创建一个产品推广项目。
2. 在“合作执行单”把项目、媒体/KOL、负责人和当前执行状态关联起来。
3. 打开项目后直接登记寄样、费用、内容产出与跟进动态。
4. 从“执行工作台”每天查看待发货、运输中、已签收待产出、内容超期和待付款事项。

## 创建用户

1. 登录 Admin 账号。
2. 进入“用户管理”。
3. 点击“新增”。
4. 填写邮箱、姓名、角色和密码。

角色说明：

- `Admin`：管理用户、导入 Excel、删除数据、编辑所有数据。
- `Editor`：新增和编辑媒体、产品、合作、产出、联系人。
- `Viewer`：只能查看。

## CLI 与 Agent 接入

网页端会继续保留；仓库根目录新增了 `pangdun.cmd`，用于从终端或 Agent 安全访问同一套 CRM API。

首次登录：

```bat
pangdun.cmd auth login --email admin@example.local
```

密码通过隐藏输入读取，CLI 只在当前 Windows 用户的本地配置目录保存有效期 90 天的 Token，不保存密码。也可以通过 `PANGDUN_TOKEN` 环境变量提供 Token。

常用只读命令：

```bat
pangdun.cmd auth status
pangdun.cmd media list --channel YouTube
pangdun.cmd media show 172
pangdun.cmd media normalize
pangdun.cmd tasks today
pangdun.cmd collab list
pangdun.cmd audit --limit 20
```

媒体和执行单更新默认只输出变更预览。真正写入时必须同时传入 `--apply` 与修改原因：

```bat
pangdun.cmd media update 172 --tier B
pangdun.cmd media update 172 --tier B --apply --reason "人工核对粉丝量后调整等级"
pangdun.cmd collab update 36 --status 运输中 --apply --reason "物流单已确认揽收"
pangdun.cmd media normalize --apply --reason "统一历史渠道、等级和明确的状态同义词"
```

在全局参数中加入 `--json` 可获得适合 Agent 读取的结构化输出，例如：

```bat
pangdun.cmd --json tasks overdue
```

CLI 写入媒体、数据归一和合作执行单时会记录操作者、修改前后内容及原因，可通过 `pangdun.cmd audit` 查看。

## 本地 MCP（Codex / ChatGPT 桌面端）

本地 MCP 与 CLI 共用同一套 CRM API、成员身份和审计记录。先完成一次 CLI 登录：

```bat
pangdun.cmd auth login --email admin@example.local
```

然后在 Codex 或 ChatGPT 桌面端的 MCP 设置中添加 STDIO Server，启动命令选择仓库根目录的：

```text
pangdun-mcp.cmd
```

也可以在 Codex 的 `config.toml` 中配置：

```toml
[mcp_servers.pangdun-crm]
command = "D:\\KOL插件\\Pangdun-CRM\\pangdun-mcp.cmd"
cwd = "D:\\KOL插件\\Pangdun-CRM"
default_tools_approval_mode = "writes"
```

保存后重启 Codex / ChatGPT 桌面端。MCP 不会返回 Token；默认读取当前 Windows 用户通过 CLI 登录后保存的成员身份。也可以通过 `PANGDUN_URL` 和 `PANGDUN_TOKEN` 环境变量单独配置。

MCP 支持媒体与合作查询、今日待办、审计记录和安全的两阶段修改。批量状态清洗与主页拆分同样分为两步：

1. 调用 `preview_bulk_status_cleanup` 或 `preview_bulk_profile_link_split` 生成预览。
2. 人工确认预览后，使用对应的 `apply_...` 工具并填写修改原因。

预览生成的 `change_set_id` 只保存在 MCP 进程内，15 分钟后失效。确认写入时会重新读取 CRM；预览后被其他成员修改的记录会跳过，不会覆盖新数据。

## 配置胖墩 Agent（DeepSeek）

Agent 第一版使用 DeepSeek 的 OpenAI 兼容 Chat Completions 接口，默认模型是 `deepseek-v4-flash`。密钥只由后端读取，不会进入网页、数据库或 Git。

1. 将 `backend\agent.env.example` 复制为 `backend\data\agent.env`。
2. 在新文件中填写 `DEEPSEEK_API_KEY`。
3. 重新运行 `start.bat`。
4. 进入左侧“胖墩 Agent”，顶部显示“已连接”后即可使用。

首版支持：

- 读取公开网页文字，或粘贴 Media Kit、邮件和表格文字。
- 提取媒体名称、国家、渠道、主页、粉丝/流量和联系人。
- 为每个字段展示原文证据和置信度。
- 匹配已有媒体，并由人工勾选字段后写入。
- 保留采用、拒绝、失败、Token 用量和审计记录。

安全边界：

- Agent 不允许访问本机、局域网或保留地址。
- 不会静默修改或删除 CRM 数据。
- 不会自动发送邮件。
- 低置信度或缺少证据的结果不会自动预选。
- PDF Media Kit 暂不直接上传，请先复制其中的文字；文件解析会在后续版本补充。

## 设置 YouTube 合作 Tag

进入“项目管理”，打开项目详情并选择“编辑项目信息”，在“内容识别 Tag”中填写完整标签，例如 `#MAXSUN`。内容监测会在该项目合作的预计发布日期窗口内读取对应 YouTube 频道，并只关联 Description 中包含这个完整 Tag 的视频。修改后下一轮扫描立即生效；多个项目可以设置不同 Tag，避免同一达人同期合作时归属混淆。

## 备份数据库

双击 `backup.bat`。脚本使用 SQLite 在线备份接口，因此 CRM 正在运行时也可以生成一致快照，不会直接复制一个可能正在写入的数据库文件。备份完成后会自动检查 SQLite 完整性，并在 `backups` 目录生成：

- `kol_crm_backup_日期_时间.db`：可恢复、可交付的完整数据库。
- 同名 `.db.sha256`：用于确认传输前后文件完全一致。

如果完整性检查失败，脚本会删除临时文件并保留原数据库不变。

## 恢复数据库

在命令行中运行：

```bat
restore.bat backups\kol_crm_backup_2026-07-07_153000.db
```

恢复前请先关闭 CRM。脚本会拒绝覆盖正在使用的数据库，先验证所选快照，再使用在线备份方式保护当前数据库，并要求输入 `YES` 确认。恢复完成后会再次执行完整性检查，然后请重新启动 CRM。

## 把清洗后的数据交付给其他人

可以直接交付 `kol_crm.db`，而且这是完整迁移 CRM 数据的推荐方式。SQLite 数据库会保留媒体、联系人、收件地址、项目、合作执行、寄样、内容、费用、用户和审计记录；单张 CSV 无法无损表达这些一对多关系。

不要在资源管理器里直接复制正在运行的 `backend\data\kol_crm.db`。请先运行 `backup.bat`，把新生成的 `.db` 和 `.db.sha256` 一起交付：

1. 代码通过 Git 获取，数据库通过可信私有渠道单独发送。
2. 不要发送 `backend\data\agent.env`、DeepSeek/YouTube 密钥或本机 CLI/MCP Token。
3. 接收方首次启动前，将备份文件复制为 `backend\data\kol_crm.db`；也可以放入 `backups` 后使用 `restore.bat`。
4. 接收方自行创建 `backend\data\agent.env`，填入自己的 API 密钥。
5. 启动后确认媒体、项目和合作数量，并重新登录 CLI/MCP。
6. 使用 PowerShell 的 `Get-FileHash 文件路径 -Algorithm SHA256`，与 `.sha256` 中的值对比。

数据库内包含业务联系人、地址、用户密码哈希和审计记录。向外部组织交付时应使用加密压缩包或受控文件传输；如果对方只需要媒体名录，应另行生成脱敏 CSV，不要交付完整数据库。

## 别人打不开网页时检查什么

1. 运行 CRM 的电脑是否开机。
2. 本机能否打开 `http://127.0.0.1:8000`；如果不能，重新双击桌面的 `Pangdun CRM`。
3. 两台电脑是否在同一个局域网。
4. 访问地址是否用了主机局域网 IP，而不是 `127.0.0.1`。
5. Windows 防火墙是否放行 TCP 8000。
6. 公司网络是否隔离了不同 Wi-Fi 或 VLAN。
7. 主机是否进入睡眠。
8. 如果后台启动没有自动打开网页，查看 `backend\data\crm-start.log`。

## MVP 限制

- 这是局域网 MVP，不是正式生产部署。
- 运行 CRM 的同事主机关机或睡眠后，其他人无法访问。
- SQLite 适合小团队低频编辑，不适合大量并发写入。
- 请定期运行 `backup.bat` 备份数据库。
- 长期正式使用时，建议迁移到专门内网主机 + PostgreSQL。
- 前端使用项目内自有组件与 Radix 基础交互组件，不依赖此前的非商用 UI 组件库。
