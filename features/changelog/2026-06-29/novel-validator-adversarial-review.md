# Novel Validator Adversarial Review

Novel-Continuity-Validator now treats every future review as adversarial by default.

The role identity requires Validator to actively look for evidence that should overturn a `pass`, independently verify Director and Creative claims against source text and canon, distinguish unchecked areas from passed checks, and record `adversarial_checks` in structured review output.

`botmux-assets --write` should be used after this change to regenerate the local Novel-Continuity-Validator workspace `AGENTS.md` from the repository identity.

## Mechanism Repetition Gate

Validator also now requires a cross-chapter `mechanism_repetition_check` for chapter packages.

The agent must compare each chapter's main conflict, main countermeasure, main payoff, hook, and repeated mechanism hits. If the same solution repeatedly becomes the core key to resolving crises, the issue must be raised as a rhythm and reader-satisfaction gate, even when continuity rules, word count, and forbidden terms pass. Repeated mechanisms may remain as auxiliary recordkeeping or responsibility boundaries, but not as the dominant payoff across adjacent chapters.
