# Novel BotMux Offline Run Limitation

Documented a BotMux CLI limitation found during local workflow smoke attempts.

`botmux workflow run --bot-resolver echo` is useful for graph and runner plumbing, but it does not generate outputs that satisfy the novel agent contract. The echo resolver returns fields such as `activityId`, `bot`, and `echo`; it does not synthesize `preview`, `handoff`, or `data`.

For the novel workflows, this means the second node fails with `InputBindingFailed` when it tries to bind `${upstream.output.handoff}`. This is expected for the offline echo resolver and does not contradict `botmux workflow validate` or readiness binding checks.

Current automatic coverage remains:

- `botmux workflow validate` for BotMux template structure and graph invariants.
- `python3 -m botmux_novel readiness` for static `${params.*}` and `${node.output.*}` binding checks.
- `python3 -m botmux_novel readiness --series-smoke --smoke-chapter-count 20` for local runtime continuity, archive, and prior-context stability.
- `python3 -m botmux_novel readiness --llmwiki-smoke` for approved temporary llmwiki workspace write, lint, and reindex coverage.

Real BotMux workflow execution still requires real bot output and will stop at `humanGate` for user approval.
