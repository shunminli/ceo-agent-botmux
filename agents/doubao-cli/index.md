Updated: 2026-06-27

# Doubao CLI Wrapper

`botmux_doubao` 是豆包桌面端 / Web 自动化 runner 的本地包装层，为小说创意 Agent 提供稳定 CLI 入口。

## 职责

- 提供 CLI 入口 `python -m botmux_doubao` 和安装脚本名 `botmux-doubao`。
- 统一封装直接桌面端 CDP、OpenCLI `doubao-app`、OpenCLI Web adapter 和第三方 `doubao-cli` runner。
- 为 `ask`、`read`、`status`、`launch` 提供一致参数、超时、JSON 输出和缺依赖诊断。
- 提供 `creative`、`dialogue`、`rewrite` prompt preset，约束豆包输出只作为候选素材。

## 边界

- 本模块不调用豆包非公开 API，不保存账号、Cookie 或会话凭证。
- 真实登录和会话由本机豆包桌面端或 Web profile 负责；模块只操作已登录 UI。
- 当前桌面端默认推荐 `cdp-app`，它用 Node 直接连接 Doubao Desktop 的 CDP 端口并选择 `doubao-chat` 页面；桌面端必须以 remote debugging 端口启动，已有无 CDP 实例时需要先退出再重启。
- OpenCLI `doubao-app` 作为兼容入口保留；当 OpenCLI adapter 选择到后台页或 selector 漂移时，优先显式使用 `--provider cdp-app`。
- OpenCLI Web adapter 需要 Browser Bridge extension 已连接；第三方 `doubao-cli` 作为兼容入口。
- 豆包输出不能直接写入项目事实、记忆或最终稿，必须由 Codex / Agent 链再整理和验证。

## 主流程

1. `botmux_doubao.cli` 解析命令、prompt 来源、provider、runner、timeout 和输出格式。
2. `DoubaoRuntime` 根据 provider 选择 runner：`cdp-app`、`opencli-app`、`opencli-web` 或 `doubao-cli`；`auto` 在已有 CDP endpoint 且可用 Node 时优先选择 `cdp-app`。
3. `cdp-app` 通过 DevTools `/json/list` 找到 `doubao-chat` 页面，填入 `textarea[data-testid="chat_input_input"]`，点击发送按钮，并从 prompt 后的下一条 `message-block-container` 提取回复。
4. 其它 provider 的 `ask` 在需要时先调用 runner 的新建会话命令，再调用实际提问命令。
5. `status` 检查 runner 是否存在，并对桌面端模式补充 Doubao App、CDP endpoint、CDP target 和页面输入框等诊断。
6. `launch` 生成或执行豆包桌面端 CDP 启动命令，供 `cdp-app` 和 OpenCLI `doubao-app` 使用；`--relaunch` 会显式退出已有 Doubao 再重启。

## 代码锚点

- `botmux_doubao/runtime.py`：provider 选择、runner 命令拼装、执行和诊断。
- `botmux_doubao/cdp_app.py`：直接桌面端 CDP driver，封装 target 选择、输入发送、消息块提取和状态检查。
- `botmux_doubao/cli.py`：命令行解析、prompt 读取和输出格式控制。
- `pyproject.toml`：包安装配置和 `botmux-doubao` console script。
- `tests/test_doubao_cli.py`：真实 Python 模块入口、fake runner、缺依赖和 launch dry-run 验证。
