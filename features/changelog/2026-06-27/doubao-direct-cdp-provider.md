# Doubao Direct CDP Provider

## Change

- Added the `cdp-app` provider to `botmux_doubao`.
- The provider uses Node to connect directly to a Doubao Desktop CDP endpoint, find a `doubao-chat` page, send prompts, read replies, and report status diagnostics.
- `launch` now reports `cdp-app` and suggests `DOUBAO_CDP_ENDPOINT`.

## Impact

- Novel Creative Architect can use Doubao as a local Creative Assist Tool without requiring OpenCLI as the primary desktop adapter.
- OpenCLI app/web and third-party `doubao-cli` providers remain compatibility paths.
