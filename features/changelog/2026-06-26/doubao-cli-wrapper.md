Date: 2026-06-26

# Doubao CLI Wrapper

## Context

小说创意 Agent 需要把豆包作为可选 Creative Assist Tool，用于生成候选创意、对白、段落和改写版本。仓库此前只有设计文档中的边界说明，没有可执行 CLI 入口。

## Change Summary

- 新增 `botmux_doubao` 标准库 Python 包。
- 新增 `python -m botmux_doubao` / `botmux-doubao` CLI 入口。
- 支持 OpenCLI `doubao-app` 桌面端适配器、OpenCLI Web adapter 和第三方 `doubao-cli` runner。
- 支持 `ask`、`read`、`status`、`launch` 命令，以及 `creative`、`dialogue`、`rewrite` prompt preset。
- 补齐 `pyproject.toml` build-system 和 setuptools package discovery，确保 wheel 构建和 `botmux-doubao` console script 安装可验证。
- `launch` 增加显式 `--relaunch` 模式，用于在已有豆包实例没有 CDP 时先退出再带 remote debugging 端口重启。
- 新增 fake runner 测试，验证真实 Python 模块入口、命令拼装、缺依赖诊断和 launch dry-run。

## Impact Surface

- 影响本地 CLI、小说创意 Agent 可选工具链、README 和本地 memory。
- 不改变 `botmux_novel` 现有确定性本地小说 runtime。
- 不引入运行时依赖，也不保存豆包账号、Cookie 或会话凭证。

## Notes / Compatibility

真实豆包调用依赖用户本机安装并登录外部 runner。OpenCLI 桌面端模式需要豆包 App 以 CDP 端口启动，并设置 `OPENCLI_CDP_ENDPOINT`；如果已有豆包实例没有 CDP，需要退出后重启。OpenCLI Web 模式需要 Browser Bridge extension 已连接。

## Related Docs

- `agents/doubao-cli/index.md`
- `features/doubao-cli/index.md`
