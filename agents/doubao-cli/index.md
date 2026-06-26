Updated: 2026-06-26

# Doubao CLI Wrapper

`botmux_doubao` 是豆包桌面端 / Web 自动化 runner 的本地包装层，为小说创意 Agent 提供稳定 CLI 入口。

## 职责

- 提供 CLI 入口 `python -m botmux_doubao` 和安装脚本名 `botmux-doubao`。
- 统一封装 OpenCLI `doubao-app`、OpenCLI Web adapter 和第三方 `doubao-cli` runner。
- 为 `ask`、`read`、`status`、`launch` 提供一致参数、超时、JSON 输出和缺依赖诊断。
- 提供 `creative`、`dialogue`、`rewrite` prompt preset，约束豆包输出只作为候选素材。

## 边界

- 本模块不调用豆包非公开 API，不保存账号、Cookie 或会话凭证。
- 真实登录、会话和 UI 自动化由外部 runner 负责。
- 当前默认推荐 OpenCLI 桌面端适配器；Web adapter 和第三方 `doubao-cli` 作为兼容入口。
- 豆包输出不能直接写入项目事实、记忆或最终稿，必须由 Codex / Agent 链再整理和验证。

## 主流程

1. `botmux_doubao.cli` 解析命令、prompt 来源、provider、runner、timeout 和输出格式。
2. `DoubaoRuntime` 根据 provider 选择 runner：`opencli-app`、`opencli-web` 或 `doubao-cli`。
3. `ask` 在需要时先调用 runner 的新建会话命令，再调用实际提问命令。
4. `status` 检查 runner 是否存在，并对桌面端模式补充 Doubao App、CDP endpoint 等诊断。
5. `launch` 生成或执行豆包桌面端 CDP 启动命令，供 OpenCLI `doubao-app` 使用。

## 代码锚点

- `botmux_doubao/runtime.py`：provider 选择、runner 命令拼装、执行和诊断。
- `botmux_doubao/cli.py`：命令行解析、prompt 读取和输出格式控制。
- `tests/test_doubao_cli.py`：真实 Python 模块入口、fake runner、缺依赖和 launch dry-run 验证。
