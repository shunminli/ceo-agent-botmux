# Novel Prior Archive Context

Added prior archive loading for local chapter production.

## Behavior

- `python3 -m botmux_novel chapter` now scans earlier `runs/archive-{chapter}.json` files before generating the next chapter.
- The runtime writes `runs/{chapter_run_id}/prior-context.json` with source chapters, source refs, facts, timeline entries, foreshadowing, character state, and continuity issues.
- `ContextPackBuilder` injects prior archive data into `context-pack.json` so later chapters can see established facts and source refs like `archive:ch-001`.

## Validation

- Added a two-chapter runtime test that generates chapter 1, then verifies chapter 2 loads chapter 1 archive context.
- `python3 -m unittest tests.test_novel_runtime -v`
- `python3 -m py_compile botmux_novel/*.py tests/*.py`
