# Limitations

- **Fictional scenario.** The station, its equipment, its readings and every sample in `samples/` are synthetic. No real utility, site or person is represented.
- **No real equipment.** Commands reach the built-in simulator only. Nothing here can drive physical equipment.
- **No AI or model.** Timelines and reports come from deterministic rules. Nothing in this repository calls a model or a remote service, and no output is presented as model output.
- **Not the full demonstration.** The commercial analyst, model verification, qualified prompts, voice and cloud integrations, private data and fleet systems of the full Pump Station Zero demonstration are not included.
- **Modbus subset.** The server implements a finite register map and a bounded set of function codes, enough for the practice journey. It is not a complete Modbus implementation.
- **Memory only.** Sessions, events and saved reports live in memory and disappear when the process stops. Download a report first if you want to keep it.
- **Local use only.** See [SECURITY.md](SECURITY.md).
- **Testing scope.** The automated tests exercise the protocol, simulator, sessions and reports. They do not measure human usability, accessibility with assistive technology or behaviour under hostile local users.
