# Pump Station Zero Community

**A local practice decoy for a small water booster station.** Stop a simulated pump, watch the equipment display change, follow the actual Modbus command and its independent readback into a saved report. A decoy is a safe copy that records interactions; no real water equipment is connected, and everything runs on your own computer with Python alone.

Built for the Meta Global AI Developer Hackathon, November 2026, by Deception Check, Inc.

## Hackathon submission

| | |
|---|---|
| Demo video | https://youtu.be/c8zRYXETCEo |
| Hosted demo, limited-time judge access, DEMO banner | https://meta.deceptioncheck.ai |
| Research report, DecoyBench and the model program | https://meta.deceptioncheck.ai/research/DecoyBench-Report.html |
| Benchmark harness (MIT) | https://github.com/DeceptionCheck/decoybench |
| Build timeline, 28 October to 4 November | [docs/BUILD-TIMELINE.md](docs/BUILD-TIMELINE.md) |
| Two alternate harness implementations (MIT) | https://github.com/DeceptionCheck/decoybench-alt-a and https://github.com/DeceptionCheck/decoybench-alt-b |

**Meta tooling in the full demonstration.** Muse Glimmer supplies constrained decoy wording on four response kinds; Meta Llama writes the operator brief from recorded facts; Meta Voice Transcribe takes spoken questions. In every mode the application controls routes, status codes, and station state, and a validator replaces any model output that fails its contract with deterministic content. Built with Llama.

**What is withheld.** The qualified prompt pack, the guardrail and adversarial corpora, the qualification policy, and the private receipts are withheld pending an intellectual-property review. This Community edition ships the deterministic station without the model path; the video shows the model path (Meta Llama writing the operator brief, and Muse Glimmer's local typed-error results); the hosted demo runs the deterministic path with model and voice disabled, and installed acceptance of the Glimmer path is pending.

## What is in this repository

| Component | Here | Full demonstration |
|---|---|---|
| Pump and tank simulator with interlocks, atomic writes, and hard stops | Yes | Yes |
| Finite Modbus TCP server with device identification, exception codes, and a documented register map | Yes | Yes |
| Industrial HMI (overview, pumps, alarms) | Yes | Yes |
| Operator view | Simple console | Full operator wall and phone card |
| Timeline and report | Deterministic rules | Deterministic report plus a model-assisted brief, checked by a verifier |
| AI models, prompts, voice | None | Muse Glimmer, Meta Llama, Meta Voice Transcribe |
| Where it runs | Your computer, loopback only | Deception Check's private hosting |
| Source | This repository, [AGPL-3.0-only](LICENSE) | Proprietary; not included here |

Using or watching the full demonstration does not license its source.

## Why a decoy

Water and wastewater utilities run on controllers and remote-access boxes that were built to be reached. The joint CISA, EPA, and FBI fact sheet of February 2024 lists eight actions a water system can take; a decoy is how a two-operator utility finds out whether the others are holding. In September 2026 CISA published its first standalone guidance on cyber decoys for critical infrastructure, with a water utility as its worked scenario. NIST SP 800-53 Rev. 5 SC-26 names the control. The report linked above has the sources.

## Run it

Python 3.11 or newer is the only requirement. No packages, credentials, environment file, model download or Internet access are needed. From this directory:

```text
python scripts/install_check.py      # optional: confirms Python and the modules load
python -m community.server --port 8180
```

Or use `scripts/run.sh` (Linux, macOS) or `scripts/run.ps1` (Windows).

Open `http://127.0.0.1:8180/`. Stop with Ctrl+C. `--port 0` picks a free port and prints it. The server binds to loopback only and has no external bind or target option. Do not expose it through a proxy or tunnel; see [SECURITY.md](SECURITY.md).

## The journey

1. **Explore.** Your browser gets its own running synthetic station. Explore Pumps or Station overview. The equipment display uses the same simulator as its local Modbus server.
2. **Ready.** This sets the fixed synthetic operating conditions. It is a practice setup action, not a remotely available plant capability, and it still evaluates interlocks.
3. **Send remote stop.** This sends a real local Modbus FC5 request for coil 1, then reconnects separately to read the off bit back with FC1. Pump 2 stops and turns red, and the operator warning turns magenta.
4. **Inspect.** The timeline and the Technical details drawer show registers, protocol reply bytes and raw synthetic events, available without needing to understand them first.
5. **Save the report.** Download it as HTML or JSON. The report comes from deterministic rules; it is not AI output and is not sent anywhere.
6. **Try the rejected setting.** A real multi-register write tries to put the stop level below the start level. The whole write is refused, with no partial state change.
7. **Start a new session.** The old report is not reachable from the new session. A separate browser or private window owns a separate station.

Sessions are bounded: at most eight idle-expiring stations, eight saved reports per station, 256 retained events and two hours of HMI history. Everything is in memory and disappears when the process stops.

## Tests and protocol reference

```text
python -m unittest discover -s tests -v      # or scripts/test.sh, scripts/test.ps1
python -m decoy_modbus.register_map --markdown
```

**What the tests cover:**

- real TCP stop and readback;
- rejected and partial multi-register writes;
- atomic simulator updates;
- tank, suction and fault hard stops;
- independent session ownership;
- saved-report immutability;
- escaping and body limits;
- loopback and access checks;
- the complete journey with outside network connections denied.

They are not human usability testing or production qualification.

**Addressing and controls:**

- Modbus addresses are zero based. The Technical details drawer shows the finite register map and the loopback port owned by that session.
- The HTTP controls accept no IP address, port, arbitrary register or command value.
- The HMI setup and login forms always reject and never change state.

## More

- [LIMITATIONS.md](LIMITATIONS.md): what this is not.
- [SECURITY.md](SECURITY.md): deployment boundaries and how to report a vulnerability.
- [DEPENDENCIES.md](DEPENDENCIES.md) and [DEPENDENCY-GRAPH.json](DEPENDENCY-GRAPH.json): the entire runtime import graph (Python standard library only).
- [COMPATIBILITY-INVENTORY.json](COMPATIBILITY-INVENTORY.json): every file, its origin and its license.
- [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md): none vendored.

## License

Copyright (C) 2026 Deception Check, Inc. Licensed under the GNU Affero General Public License, version 3 only (AGPL-3.0-only). See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). No trademark or logo rights are granted. DecoyBench, the neutral benchmark, is a separate project under the MIT license and is not part of this repository.

Deception Check, Pump Station Zero, and DecoyBench are names of Deception Check, Inc.; no trademark rights are granted. Patent pending: United States provisional applications filed in 2026 by Deception Check, Inc.
