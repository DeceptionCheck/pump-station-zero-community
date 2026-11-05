# Pump Station Zero: build timeline

**From a command that stops a fictional pump to a record a person can understand.**

Pump Station Zero began with a practical question: when someone touches a decoy water station, can we show what happened, preserve the evidence, and help a person decide what to check next? The build connected a simulated water process, real protocol requests, a live station display, and an operator workflow. The full demonstration also explored Meta models and voice services. DecoyBench grew alongside it so that model and transport failures could be measured rather than edited out of the story.

This page records selected milestones from **October 28 through November 4, 2026**. The first two rows are model-program measurements that preceded the repository; the rest cover the primary application and its related benchmark work. It is not a complete history of the separately developed Muse applications or other benchmark implementations.

## Why the public commit history starts later

The public Community and benchmark repositories were prepared from reviewed source exports. Their initial commits record release preparation, not the beginning of development. The earlier development repositories also contain material outside the public release scope, so their complete history was not copied into these repositories.

The milestones below come from retained development commits and acceptance records. Short identifiers refer to the original development repository; they may not resolve in this public repository. They are provenance references, not links to undisclosed source. No development commits have been backdated or reconstructed for this timeline.

Dates in the milestone table use **America/New_York**, including the November 1 daylight-saving transition. Git author timestamps are recorded metadata, not independent proof of when every line was written or how many hours a task took. Test results below are historical results for the identified scope, not a blanket claim about every later build or deployment.

## The build, step by step

| Date | What changed | Why it mattered | Original development references |
| --- | --- | --- | --- |
| Oct 28 | Measured nine stock model configurations, five Llama builds and four Muse Glimmer configurations, on the same 120 prompts: 4,320 attempts. | Established the starting point: fluent replies that passed lexical checks could still invent interfaces or confirm actions that never happened, and the 30B model missed the four-second deadline on every reply. | Research report, Part 1 (measurements, not repository commits) |
| Oct 29 | Removed reasoning from the attacker-facing model and added eight demonstrations of correct device replies; measured one, two, and four concurrent clients. | Two-client p95 fell from several seconds to under a second while correctness rose to 59 of 60 on fresh prompts; this became the serving configuration the application was built around. | Research report, Part 2 (measurements, not repository commits) |
| Oct 30 | Created the repository skeleton, project documentation, notices and security policy. | Established the structure for a testable implementation and a separately reviewed release. | `7bd654d` |
| Oct 31 | Built the water-process simulator, protected controls and redacted event records. Added the Modbus listener, register map and wire-level tests. | A protocol request could affect the same simulated plant state shown by the interface. This was actual protocol interaction with a fictional station. | `1c4c67c`, `c08a08a` |
| Oct 31 | Connected station pages and the live state feed; added a typed model coordinator and local model stub. | The plant interface could update from shared state. Early model-path tests used a stub and did not establish real-model acceptance. | `0b707e0`, `d7667de` |
| Oct 31 | Repaired atomic Modbus writes, tank hard-stop enforcement and credential handling. | Invalid batches could not partially change state; safety limits continued to override start requests; sensitive inputs required redaction. | `d6750b3`, `502ee29`, `34c9ec1` |
| Oct 31 | Added live operator views, the scripted Modbus demonstration, fact extraction, checked briefs and typed questions. Started the direct-ingress benchmark and safe artifact export. | The workflow began to connect a visitor's action to evidence an operator could inspect. The closing suite for this stage recorded 163 passing tests. | `8440b76`, `8f79ae5`, `130fc57`, `e6a3144` |
| Oct 31 | Tightened verification of factual relationships; repaired feed restart handling, stale-data indications, mixed-log measurement and bounded observation windows. | A plausible sentence was insufficient: relationships had to match the captured facts. Missing or stale evidence needed to remain visible. | `4a37046`, `e0c0320`, `cc12e75`, `4659a17` |
| Nov 1 | Added the pinned-evidence workspace, bounded charts and responsive operator views. Repaired mobile priorities, threshold labels and controls across viewport changes. | A newcomer could start with meaning and a next step, while technical users retained access to the underlying evidence. | `eb9084a`, `2c8dfe8`, `7f864d2` |
| Nov 1 | Separated private resources, added bounded provider and voice paths, and strengthened authenticated proxy handling and response deadlines. | Optional model and voice services had to fit within explicit application boundaries. Adding an integration was not the same as qualifying its live service. | `0f69cce`, `0018215`, `290db3a`, `476dd8c` |
| Nov 2 | Refined question placement, plain-language answers, small-screen layout and expired-evidence recovery using laptop feedback. | The operator's question and the selected evidence needed to stay understandable and usable during a real interaction. | `e6e3469`, `f9b7a84` |
| Nov 3 | Completed the visitor console, isolated encounter workflow, visible pump-stop consequence and downloadable reports. Built the standalone model runner, scorer and neutral benchmark corpus. | The demonstration could follow **Ready → Act → pump stops → evidence → report**. The benchmark could run independently of the private application. | `68ba9e1`, `fe10c6d`, `4177821`, `20813bd` |
| Nov 3 | Repaired the concurrent benchmark fixture, made strict acceptance criteria explicit, synchronized the UI test fixture, and tightened refused-response timing. | A successful command exit alone could not hide missing responses. Test races and timing misses were investigated rather than dismissed after a later green run. | `2eadbd5`, `386b310`, `be1cd09`, `3c578fd`, `8601ef2` |
| Nov 3 to 4 | Prepared isolated, licensed Community and benchmark exports; tested fresh archives; completed a separately reviewed real-target demo qualification round. | Public source could be exercised without private modules, credentials or model packages. Full-demo model results remained separate from Community and fixture results. | Export and qualification evidence summarized below |

## Evidence that shaped the release

These are separate cohorts with different purposes. Their counts should not be added together or used as a ranking of models.

| Scope | Recorded result | What it establishes, and what it does not |
| --- | --- | --- |
| Community source export | **30 tests passed** from the extracted archive in isolation. | Tests exercised the stripped Community edition without the private application on its import path. This is not model qualification. |
| Community browser workflow | **30 automated checks passed**, including an actual Modbus stop, independently connected readback, visible HMI consequence, safety refusal, report downloads and session isolation. | The observed pump indication changed in approximately **0.77 seconds** in this run. These were automated browser checks, not a substitute for human acceptance or actual browser zoom testing. |
| Standalone DecoyBench R6 | **16 tests passed** from the exported source. Twenty strict fixture matrices at **1, 2, 4 and 8 clients** produced **800 planned, completed and usable final responses**, with **0 failed and 0 unattempted**. | All 800 responses were independently rescored. **80 intentional lexical findings remained visible.** This measures harness behavior against a deterministic fixture, not the quality or speed of a language model. |
| Real-target full-demo qualification, Nov 4 | **75 cases attempted; 100 checks passed.** There were 55 complete HTTP 200 responses, 16 expected rate-limit responses and 4 deliberate client aborts; none were unattempted. | The cohort included **17 accepted real-model responses** within the four-second limit and **30 refused-service calls**, the slowest completing in **60.7 ms**. Rate limits and aborts are reported separately from successful answers. Installed acceptance of the Muse Glimmer path is still pending; the accepted model responses in this cohort came from the Llama operator-brief path. |
| Recovery in that same demo cohort | **7 of 12 stall/abort resolutions required controlled restart recovery.** | The reviewed recovery workflow succeeded, but automatic cancellation and drain did not pass in those seven cases. A working demonstration does not erase that limitation. |

The exported Community acceptance source was `43b7ca1d7d56d340b6b1fd75f161cd6957a97685`. The standalone R6 implementation was derived from `b1ff53c32a1ef582f66271a41bead46d222bbad0`; subsequent release packaging retained its Python code, tests and neutral corpus. Consult each repository's release manifest for its distributed archive identity. These references do not imply that all repositories share a commit graph or implementation.

## What we learned from the failures

- **Transport success is not answer success.** An HTTP 200 can still contain an incomplete, malformed or unusable answer. The benchmark records complete responses and explicit acceptance criteria.
- **A green rerun does not remove a failure.** Earlier fixture timeouts, UI races, startup failures and incomplete qualification rounds were retained alongside corrected runs.
- **Fast answers and safe recovery are separate questions.** A model can answer within budget yet fail to drain cleanly after cancellation. Controlled recovery must be disclosed as such.
- **Model results belong to a configuration.** Glimmer, Llama, Spark and Voice Transcribe were explored in different roles and environments. A result for one model, task, runtime or GPU does not qualify another. Fixture results are never presented as model inference.
- **People need meaning before detail.** Human direction and laptop feedback shaped the visible pump-stop event, the plain-language evidence view, report workflow and editable voice-question interaction. Technical evidence remained available underneath.

## What the public editions contain

**Pump Station Zero Community** is the separately scoped, AGPL-3.0-only application edition: a fictional station, simulator, protocol interaction, realistic HMI, basic operator workflow and deterministic reports. Its local default does not require a model, credentials or Internet access. It does not contain the full demonstration's private intelligence implementation.

**DecoyBench** is released under MIT, with distinct implementations retained separately. The primary R6 harness includes a standalone runner, documented rule-based scoring, neutral fixtures, reproducibility fields and independent rescoring. Lexical checks have limitations; a passing score is not a general safety or realism certification.

The full demonstration, Community source and benchmark releases have different scopes. A public demonstration URL does not license every part of the full demonstration's source, and the project licenses do not relicense third-party model weights or runtimes.

## Explore the project

- [Demo and research hub](https://meta.deceptioncheck.ai)
- [Three-minute demonstration](https://youtu.be/c8zRYXETCEo)
- [Pump Station Zero Community source](https://github.com/DeceptionCheck/pump-station-zero-community)
- [DecoyBench source](https://github.com/DeceptionCheck/decoybench)

This timeline is a summary of retained evidence. Any future publication of filtered development history requires its own review. The public release history is intentionally left intact rather than rewritten to resemble the private development graph.
