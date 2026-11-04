"""Check that this computer can run Pump Station Zero Community. Installs nothing and uses no network."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.version_info < (3, 11):
        print(f"Python 3.11 or newer is required; this is {sys.version.split()[0]}.")
        return 1
    sys.path.insert(0, str(ROOT))
    for name in ("sim.station", "decoy_modbus.server", "community.server"):
        importlib.import_module(name)
    print(f"Ready: Python {sys.version.split()[0]}. Start with scripts/run.sh or scripts/run.ps1, then open http://127.0.0.1:8180/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
