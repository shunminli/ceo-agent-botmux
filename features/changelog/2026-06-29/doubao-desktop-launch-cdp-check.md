# Doubao Desktop Launch CDP Check

## Context

Direct `cdp-app` usage depends on Doubao Desktop being launched with a reachable remote debugging endpoint. Launching the executable directly is brittle on macOS because GUI apps are usually represented by a `.app` bundle, and custom binaries should not make the CLI wait until the desktop process exits.

## Change Summary

- `botmux_doubao launch` now detects the containing `.app` bundle and uses `open -na <bundle> --args --remote-debugging-port=<port>` when available.
- Non-dry-run launch waits for `<endpoint>/json/version` before reporting success, so downstream `cdp-app` calls do not treat a spawned app as ready too early.
- Explicit non-`.app` executables are still respected and are started in the background without waiting for process exit.
- Launch diagnostics now include the app bundle, launch command, return code, CDP endpoint, CDP availability, and custom executable PID when applicable.

## Impact Surface

- `python3 -m botmux_doubao launch --dry-run --json`
- `python3 -m botmux_doubao launch --relaunch`
- `python3 -m botmux_doubao ask --provider cdp-app`
- Novel Creative Architect's preferred Doubao CLI invocation path

## Compatibility

OpenCLI app/web providers and third-party `doubao-cli` compatibility paths are unchanged. Custom `--app-binary` paths outside a `.app` bundle remain supported and now avoid blocking on long-running GUI processes.

## Related Docs

- `agents/doubao-cli/index.md`
- `features/doubao-cli/index.md`
