# Pump Station Zero Community

Stop a simulated pump, watch its equipment display change, and follow the actual command into a saved report. This is a local practice tool for understanding an industrial decoy. A decoy is a safe copy that records interactions; no real water equipment is connected.

It contains a pump and tank simulator, a finite Modbus TCP server, an industrial HMI, a simple operator console and a deterministic timeline and report. Everything runs on your own computer with Python alone.

## Community edition and the full demonstration

Pump Station Zero also exists as a full demonstration, recorded and hosted by Deception Check. The two are separate.

| | Community edition (this repository) | Full demonstration |
| --- | --- | --- |
| Simulator, Modbus server, HMI | Yes | Yes |
| Operator view | Simple console | Full operator wall |
| Timeline and report | Deterministic rules | Deterministic report plus a model-assisted analyst, checked by a verifier |
| AI models, prompts, voice | None | Yes |
| Where it runs | Your computer, loopback only | Deception Check's private hosting |
| Source | This repository, [AGPL-3.0-only](LICENSE) | Proprietary; not included here |

Using or watching the full demonstration does not license its source.

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
