# Build timeline, 28 October to 4 November 2026

Pump Station Zero was built inside the Meta Global AI Developer Hackathon window. This repository is the licensed Community release; its two commits are a packaging history. The development history, with its original commit timestamps, is held in a private repository that carried the qualified prompt pack and other withheld material, and it is published here as a dated record. The full development repository will be published after its history has been scanned and the withheld files removed from every commit; until then it is available to judges on request.

| Date (ET) | What happened | Evidence |
|---|---|---|
| Tue 28 Oct | Plan, design brief, test plan, and research notes written; nine stock model configurations measured (4,320 attempts) | Report, Part 1 |
| Wed 29 Oct | Plan revision 2; reasoning removed from the attacker-facing model, eight demonstrations added; two-client p95 from several seconds to 0.735 s | Report, Part 2 |
| Thu 30 Oct | Repository skeleton committed (`7bd654d`); handler contract and the first tie with deterministic content; typed task interface takes both models to 768 of 768 | Report, Parts 3 to 5 |
| Fri 31 Oct | Three coding agents build the simulator, Modbus decoy, HTTP decoy, and brain service from one specification and one test set (first commits 13:57 to 14:41 ET); independent review; repair round (20:08 to 20:51 UTC); model program's counterbalanced confirmation (1,028 of 1,028) | Report, Parts 6 and 7; repair tips `7b328ac`, `72ed930`, `99d51ab` |
| Sat 1 Nov | Repair-round review; defender wall, operator card, analyst, and benchmark harness built; intellectual-property review of the public manifest | Report, "How the code was built" |
| Sun 2 Nov | Llama queued-coordinator release reviewed (1,008 of 1,008); operator UI acceptance round | Report, Part 6 |
| Mon 3 Nov | Installed-path run from a second machine; public report written; provisional patent packet prepared | Report, Part 7 |
| Tue 4 Nov | Provisional application filed; Community release licensed under AGPL-3.0-only (`43b7ca1`); DecoyBench reference release R6 (source `b1ff53c`); demo video and hosted demo published | This repository; the DecoyBench repositories |

Elapsed times above are clock intervals from commit and session records, not measured effort. The report at https://meta.deceptioncheck.ai/research/DecoyBench-Report.html carries the measurements for each row.
