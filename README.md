# Pump Station Zero Community

Stop a simulated pump, watch its equipment display change, and follow the actual command into a saved report. This is a local practice tool for understanding an industrial decoy. A decoy is a safe copy that records interactions; no real water equipment is connected.

This Community source is separate from the full recorded and hosted demonstration. It contains the existing pump/tank simulator, finite Modbus TCP implementation, industrial HMI, a simple operator console and deterministic timeline/report. It does not contain the commercial analyst, model verifier, qualified prompts, intelligence mappings, voice/cloud integrations, private data or fleet systems. Public access to the full demonstration does not license its source.

## Run without a model or Internet

Python 3.11 or newer is the only dependency. No packages, credentials, environment file, model download or private directory are required. From this directory:

```text
python -m community.server --port 8180
```

Open `http://127.0.0.1:8180/`. Stop with Ctrl+C. A different local port may be selected, including `--port 0` to print an available port. The application accepts only loopback binding; there is no external bind or target option. Do not expose this listener through a public proxy. A separately reviewed authenticated hosting perimeter would be required for that use.

1. Your browser gets its own running synthetic station. Explore Pumps or Station overview. The equipment display uses the same simulator as its local Modbus server.
2. Ready sets the fixed synthetic operating conditions; it is a practice setup action, not a remotely available plant capability. It still evaluates interlocks.
3. Send remote stop transmits a real local FC5 request for coil 1, then reconnects independently to read the off bit with FC1. Pump 2 stops and turns red. The operator warning turns magenta.
4. Inspect the timeline and Technical details drawer. Registers, protocol reply bytes and raw synthetic events remain available without needing to understand them first.
5. Save report, then download HTML or JSON. The report is deterministic, not AI output or an externally sent notification.
6. Try the rejected setting. An actual multi-register write tries to put the stop level below the start level. The whole write is refused, with no partial state change.
7. Start a new independent session. The old report does not become accessible in the new session. A separate browser/private profile also owns a separate station.

Session cookies are HttpOnly and SameSite=Strict. HTTP loopback is not advertised as TLS. Host and Origin checks protect the local controls against ordinary cross-site requests. Anyone who can run software on the same operating system is trusted; loopback is not isolation against a malicious local user. There are at most eight idle-expiring browser stations, eight saved reports per station, 256 retained events and a two-hour bounded HMI history. Closing the process discards in-memory sessions and reports. Download a report before shutdown if you want to retain it.

## Tests and protocol reference

```text
python -m unittest discover -s tests -v
python -m decoy_modbus.register_map --markdown
```

The suite covers actual TCP stop/readback, rejected and partial multi-writes, atomic simulator updates, tank/suction/fault hard stops, independent session ownership, saved-report immutability, escaping, body limits and loopback/access checks. Automated tests are not human usability, physical cable-pull or production qualification.

Modbus addresses are zero based. The Technical details drawer shows the finite register map and the loopback port owned by that session. The fixed HTTP controls do not accept an IP address, port, arbitrary register or command value. HTTP setup/login forms always reject and do not change state. The protocol implementation can be inspected or exercised locally by experienced users; it cannot drive physical equipment.

## Source and licensing status

The simulator, Modbus server/map and HMI are deliberately extracted first-party files. The event projection, report, session management and console are Community-owned modules rather than imports from the full intelligence application. [DEPENDENCIES.md](DEPENDENCIES.md) lists the entire runtime graph. [COMPATIBILITY-INVENTORY.json](COMPATIBILITY-INVENTORY.json) identifies every shipped file and its origin category.

AGPL-3.0-only is the proposed Community license. **No final license grant has been applied to this private candidate.** See [LICENSE-STATUS.md](LICENSE-STATUS.md) for the precise owner decision still required. No old default license, proprietary parent history, third-party model material or trademark/logo permission is inherited by this directory. Neutral DecoyBench is a separate source candidate with its own standard MIT license; it is not included in this application or required to run it.

This is preparation for exact-artifact owner and competition-rule review, not publication or release approval.
