Updated: 2026-06-29

# Doubao Creative Assist CLI

## 能力

用户或小说创意 Agent 可以通过本地 CLI 调用已登录的豆包桌面端或 Web 会话，生成候选创意、对白、段落和改写版本。

## 触发方式

```bash
python3 -m botmux_doubao ask \
  --provider cdp-app \
  --purpose creative \
  "为旧案悬疑小说生成三个章节钩子。"
```

安装包入口等价为：

```bash
botmux-doubao ask --purpose dialogue "生成兄妹在旧书楼重逢的对白候选。"
```

## 主要模式

- `cdp-app`：桌面端推荐模式，用 Node 直接连接 Doubao Desktop CDP 端口，选择 `doubao-chat` 页面并从消息块提取回复。
- `opencli-app`：兼容模式，调用 OpenCLI `doubao-app` 桌面端适配器。
- `opencli-web`：调用 OpenCLI Web adapter，adapter 名可用 `--opencli-adapter` 覆盖。
- `doubao-cli`：兼容基于浏览器会话的第三方 `doubao-cli` runner。

## 规则与状态

- `ask` 成功时返回豆包回复；加 `--json` 会返回 provider、runner、prompt、response 和诊断信息。
- `--new` 会在提问前尝试新建会话。
- `status` 用于检查 runner、Doubao App、CDP endpoint、聊天 target 和输入框状态。
- `launch --dry-run` 输出豆包桌面端 CDP 启动命令；不加 `--dry-run` 会启动本机 App 并等待 CDP `/json/version` 可用后返回成功；`--relaunch` 会显式退出已有 Doubao 再重启。
- 默认 Doubao `.app` 可定位时，桌面端通过 `open -na /Applications/Doubao.app --args --remote-debugging-port=9225` 启动；`--app-binary` 指向非 `.app` executable 时会后台启动该 executable，避免 CLI 等待 GUI 进程退出。
- `creative`、`dialogue`、`rewrite` preset 会把输出限定为候选素材，避免把新增设定当成已确认事实。

## 限制

- `cdp-app` 需要本机 Node 提供内置 `fetch` / `WebSocket`，并且 Doubao Desktop 已登录。
- OpenCLI / `doubao-cli` 兼容模式需要用户自行安装并登录对应 runner。
- 桌面端模式需要豆包以 remote debugging 端口启动；如果已有豆包实例没有 CDP，需要退出后重启。
- Web 模式需要 OpenCLI Browser Bridge extension 处于已连接状态。
- 仓库单元测试使用 fake runner 验证包装层；真实豆包账号、登录态和 UI selector 需要通过本机 `cdp-app` smoke 验证。
- 豆包候选内容可能事实漂移，进入小说项目事实、记忆或定稿前必须经过 Codex 整理和一致性验证。

## 相关逻辑文档

- [Doubao CLI Wrapper](../../agents/doubao-cli/index.md)
