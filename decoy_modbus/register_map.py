"""Single register-map source. Print its documentation with --markdown."""

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Register:
    area: str
    address: int
    reference: str
    point: str
    scale: str
    access: str
    words: int = 1


REGISTERS = (
    Register("Coils", 0, "00001", "pump1_cmd", "bit", "RW"),
    Register("Coils", 1, "00002", "pump2_cmd", "bit", "RW"),
    Register("Coils", 2, "00003", "alarm_ack", "bit", "RW"),
    *(Register("Discrete inputs", i, f"{10001+i}", point, "bit", "R") for i, point in enumerate((
        "pump1_running", "pump2_running", "pump1_fault", "pump2_fault", "low_tank_alarm_active",
        "high_discharge_alarm_active", "low_suction_alarm_active", "remote_command_active"))),
    *(Register("Input registers", i, f"{30001+i}", point, scale, "R") for i, point, scale in (
        (0, "tank_level_ft", "x10"), (1, "suction_psi", "x10"), (2, "discharge_psi", "x10"),
        (3, "flow_gpm", "x1"), (4, "chlorine_mg_l", "x100"))),
    Register("Input registers", 5, "30006 to 30007", "pump1_run_hours", "uint32, high word first, hours x10", "R", 2),
    Register("Input registers", 7, "30008 to 30009", "pump2_run_hours", "uint32, high word first, hours x10", "R", 2),
    Register("Input registers", 9, "30010", "lead_pump", "1 or 2", "R"),
    *(Register("Holding registers", i, f"{40001+i}", point, "x10", "RW") for i, point in enumerate((
        "sp_tank_start_ft", "sp_tank_stop_ft", "sp_low_tank_alarm_ft", "sp_high_tank_alarm_ft",
        "sp_high_discharge_alarm_psi", "sp_low_suction_trip_psi", "sp_low_suction_alarm_psi"))),
)


def area_rows(area):
    """Return ordered entries for a protocol area."""
    return tuple(row for row in REGISTERS if row.area == area)


def markdown():
    """Render the public map byte for byte, including address conventions."""
    lines = ["# Modbus register map", "", "Addresses on the wire are zero based. References are one based.",
             "Unit IDs 0, 1, and 255 address the same device. Other IDs receive 0x0B,",
             "as a gateway with no matching serial target would respond.", "",
             "Run hours are unsigned 32-bit values, high word first, in tenths of an hour.",
             "Reads above a function's quantity limit return 03; legal quantities beyond",
             "the finite map return 02. There is no padding to the protocol quantity limit.", "",
             "| Area | 0-based | 1-based | Point | Scale | Access |",
             "|---|---|---|---|---|---|"]
    for row in REGISTERS:
        address = str(row.address) if row.words == 1 else f"{row.address} to {row.address + row.words - 1}"
        lines.append(f"| {row.area} | {address} | {row.reference} | {row.point} | {row.scale} | {row.access} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true", required=True)
    parser.parse_args()
    print(markdown(), end="")
