Updated: 2026-06-26

# Doubao Creative Assist CLI

## 能力

用户或小说创意 Agent 可以通过本地 CLI 调用已登录的豆包桌面端或 Web 会话，生成候选创意、对白、段落和改写版本。

## 触发方式

```bash
python3 -m botmux_doubao ask \
  --provider opencli-app \
  --purpose creative \
  "为旧案悬疑小说生成三个章节钩子。"
```

安装包入口等价为：

```bash
botmux-doubao ask --purpose dialogue "生成兄妹在旧书楼重逢的对白候选。"
```

## 主要模式

- `opencli-app`：默认推荐，调用 OpenCLI `doubao-app` 桌面端适配器。
- `opencli-web`：调用 OpenCLI Web adapter，adapter 名可用 `--opencli-adapter` 覆盖。
- `doubao-cli`：兼容基于浏览器会话的第三方 `doubao-cli` runner。

## 规则与状态

- `ask` 成功时返回豆包回复；加 `--json` 会返回 provider、runner、prompt、response 和诊断信息。
- `--new` 会在提问前尝试新建会话。
- `status` 用于检查 runner、Doubao App 和 CDP endpoint 状态。
- `launch --dry-run` 输出豆包桌面端 CDP 启动命令；不加 `--dry-run` 会启动本机 App；`--relaunch` 会显式退出已有 Doubao 再重启。
- `creative`、`dialogue`、`rewrite` preset 会把输出限定为候选素材，避免把新增设定当成已确认事实。

## 限制

- 需要用户自行安装并登录 OpenCLI / `doubao-cli` 对应 runner。
- 桌面端模式需要豆包以 remote debugging 端口启动；如果已有豆包实例没有 CDP，需要退出后重启。
- Web 模式需要 OpenCLI Browser Bridge extension 处于已连接状态。
- 当前仓库测试使用 fake runner 验证包装层，不验证真实豆包账号、登录态或 UI 选择器稳定性。
- 豆包候选内容可能事实漂移，进入小说项目事实、记忆或定稿前必须经过 Codex 整理和一致性验证。

## 相关逻辑文档

- [Doubao CLI Wrapper](../../agents/doubao-cli/index.md)
