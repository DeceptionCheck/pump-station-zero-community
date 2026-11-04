"""Tank-level control, computed hydraulics, and latched protection.

All public operations are thread safe. Protocol callers log attempted writes;
the simulator never performs I/O. Stop commands persist until another command
or reset. Start requests end at either tank hard stop and cannot bypass faults
or suction protection. Remote provenance survives a tank safety stop.
"""

import math
import random
import threading
import time
from typing import NamedTuple


class WriteResult(NamedTuple):
    ok: bool
    reason: str


SETPOINTS = {
    "sp_tank_start_ft": (28.0, 1.0, 38.0),
    "sp_tank_stop_ft": (36.0, 2.0, 40.0),
    "sp_low_tank_alarm_ft": (15.0, 0.0, 28.0),
    "sp_high_tank_alarm_ft": (38.0, 28.0, 40.0),
    "sp_high_discharge_alarm_psi": (95.0, 60.0, 120.0),
    "sp_low_suction_trip_psi": (20.0, 5.0, 35.0),
    "sp_low_suction_alarm_psi": (25.0, 10.0, 45.0),
}


class StationSim:
    """Advance in at most one-second steps with a resettable seeded RNG.

    ``force`` holds suction or chlorine at a test measurement until reset or
    another force. Tank level and fault forces change the current state only.
    Discharge is always derived, including during initialization and reset.
    """

    def __init__(self, seed: int = 1, start_utc: float | None = None):
        self._lock = threading.RLock()
        self._seed = seed
        self._start = time.time() if start_utc is None else float(start_utc)
        self.reset()

    def reset(self) -> None:
        """Restore the original seeded state and initial simulation time."""
        with self._lock:
            self._rng = random.Random(self._seed)
            self._s = {key: values[0] for key, values in SETPOINTS.items()}
            self._s.update(tank_level_ft=32.0, suction_psi=50.0,
                           flow_gpm=0.0, chlorine_mg_l=1.1, lead_pump=1,
                           remote_command_active=False, alarm_ack=False)
            for pump in (1, 2):
                for suffix in ("cmd", "running", "fault"):
                    self._s[f"pump{pump}_{suffix}"] = False
                self._s[f"pump{pump}_run_hours"] = 0.0
            self._time = self._start
            self._cycle = False
            self._call_active = False
            self._trip = False
            self._manual = {}
            self._remote = set()
            self._forced = {}
            self._alarms = {}
            self._physics(0.0, initial=True)

    def reset_from(self, src: str) -> bool:
        """Loopback authorization boundary for a demo reset caller."""
        if src != "127.0.0.1":
            return False
        self.reset()
        return True

    def read(self, point: str) -> float | int | bool:
        """Return a point or raise KeyError for an unknown point."""
        with self._lock:
            return self._s[point]

    def snapshot(self) -> dict:
        """Return independent point, alarm, display, and simulation-time data."""
        with self._lock:
            result = dict(self._s)
            result.update(sim_time=self._time, suction_trip_latched=self._trip,
                          alarms=self.alarms())
            for pump in (1, 2):
                result[f"pump{pump}_display"] = (
                    "FAULT" if self._s[f"pump{pump}_fault"] else
                    "RUNNING" if self._s[f"pump{pump}_running"] else
                    "STOPPED (remote command)" if pump in self._remote else "STOPPED")
            return result

    def write(self, point: str, value, source: str) -> WriteResult:
        """Apply one point using the same atomic boundary as protocol batches."""
        return self.write_many({point: value}, source)

    def write_many(self, updates: dict, source: str) -> WriteResult:
        """Validate the proposed final state, then commit values and side effects.

        A rejected batch changes neither points, commands, provenance, trip
        latch nor acknowledgement history. Snapshot readers share this lock
        and can observe only the complete old or complete new state.
        """
        with self._lock:
            if source not in {"modbus", "hmi", "test"}:
                return WriteResult(False, "bad_value")
            if not isinstance(updates, dict) or not updates:
                return WriteResult(False, "bad_value")
            normalized = {}
            for point, value in updates.items():
                if point not in self._s:
                    return WriteResult(False, "unknown_point")
                if point in SETPOINTS:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        return WriteResult(False, "bad_value")
                    _, low, high = SETPOINTS[point]
                    if not low <= value <= high:
                        return WriteResult(False, "out_of_band")
                    normalized[point] = float(value)
                elif point in {"pump1_cmd", "pump2_cmd", "alarm_ack"}:
                    if not isinstance(value, (bool, int)) or value not in (0, 1):
                        return WriteResult(False, "bad_value")
                    normalized[point] = bool(value)
                else:
                    return WriteResult(False, "read_only")
            proposed = dict(self._s, **normalized)
            if proposed["sp_tank_stop_ft"] <= proposed["sp_tank_start_ft"]:
                return WriteResult(False, "out_of_band")
            self._s.update(normalized)
            for point, value in normalized.items():
                if point == "alarm_ack" and value and source in {"hmi", "test"}:
                    for alarm in self._alarms.values():
                        alarm["acked"] = True
                    if self._s["suction_psi"] > self._s["sp_low_suction_alarm_psi"]:
                        self._trip = False
                    self._update_alarms()
                elif point in {"pump1_cmd", "pump2_cmd"}:
                    pump = int(point[4])
                    self._manual[pump] = bool(value)
                    if source == "modbus":
                        if not value:
                            self._remote.add(pump)
                        else:
                            self._remote.discard(pump)
                        self._s["remote_command_active"] = True
                    else:
                        self._remote.clear()
                        self._s["remote_command_active"] = False
            if source == "hmi":
                self._remote.clear()
                self._s["remote_command_active"] = False
            return WriteResult(True, "ok")

    def force(self, point: str, value) -> None:
        """Test hook for measured tank, suction, chlorine, faults, communications."""
        with self._lock:
            allowed = {"tank_level_ft", "suction_psi", "chlorine_mg_l",
                       "pump1_fault", "pump2_fault", "communications_fault"}
            if point not in allowed:
                raise ValueError("not a forceable measurement")
            if not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError("finite numeric measurement required")
            if point in {"suction_psi", "chlorine_mg_l", "communications_fault"}:
                self._forced[point] = value
            if point != "communications_fault":
                self._s[point] = bool(value) if point.endswith("fault") else float(value)

    def tick(self, dt_s: float = 1.0) -> None:
        """Advance control and physics; invalid durations leave state unchanged."""
        if not isinstance(dt_s, (int, float)) or not math.isfinite(dt_s) or dt_s < 0:
            raise ValueError("nonnegative finite duration required")
        with self._lock:
            remaining = dt_s
            while remaining > 0:
                step = min(1.0, remaining)
                self._time += step
                self._control()
                self._physics(step)
                # A filling step can cross a tank threshold. Enforce the same
                # protection at the end of the step before any snapshot reader
                # can see running pumps above a hard stop.
                if self._tank_hard_stop():
                    self._control()
                    self._physics(0.0)
                self._update_alarms()
                self._s["alarm_ack"] = False
                remaining -= step

    def _tank_hard_stop(self):
        return self._s["tank_level_ft"] >= min(self._s["sp_tank_stop_ft"], self._s["sp_high_tank_alarm_ft"])

    def _control(self):
        s = self._s
        if s["suction_psi"] < s["sp_low_suction_trip_psi"]:
            self._trip = True
        level = s["tank_level_ft"]
        if self._tank_hard_stop():
            if self._cycle or self._call_active:
                s["lead_pump"] = 3 - s["lead_pump"]
            self._cycle = self._call_active = False
            for pump in (1, 2):
                # Consume starts, retaining persistent stop requests. In
                # particular a safety stop must not create a remote-stop tag.
                if self._manual.get(pump) is True:
                    self._manual.pop(pump)
                s[f"pump{pump}_cmd"] = False
                s[f"pump{pump}_running"] = False
            return
        if level <= s["sp_tank_start_ft"]:
            self._cycle = True
        for pump in (1, 2):
            automatic = self._cycle and (pump == s["lead_pump"] or
                                         level <= s["sp_tank_start_ft"] - 3.0 or
                                         s[f"pump{pump}_cmd"])
            command = self._manual.get(pump, automatic)
            s[f"pump{pump}_cmd"] = command
            s[f"pump{pump}_running"] = command and not s[f"pump{pump}_fault"] and not self._trip
            if s[f"pump{pump}_running"]:
                self._call_active = True

    def _physics(self, dt, initial=False):
        s = self._s
        count = sum(s[f"pump{pump}_running"] for pump in (1, 2))
        if initial:
            s["discharge_psi"] = 55.0
        elif count:
            s["discharge_psi"] = (75.0 if count == 1 else 81.5) + self._rng.uniform(-1.0, 1.0)
        else:
            s["discharge_psi"] = 55.0 + (s["discharge_psi"] - 55.0) * math.exp(-dt / 120.0)
        for point, low, high, delta in (("suction_psi", 45, 55, .12),
                                         ("chlorine_mg_l", .8, 1.5, .003)):
            s[point] = self._forced.get(point, min(high, max(low, s[point] + self._rng.uniform(-delta, delta) * dt)))
        hour = (self._time % 86400) / 3600
        peak = math.exp(-((hour - 7) / 2) ** 2) + math.exp(-((hour - 19) / 2.5) ** 2)
        demand = 320.0 + 280.0 * peak
        s["flow_gpm"] = (650 + 300 * peak) if count == 1 else (1100 + 350 * peak) if count == 2 else 0.0
        s["tank_level_ft"] = min(40.0, max(0.0, s["tank_level_ft"] +
                                          (s["flow_gpm"] - demand) * dt / (60 * 6250)))
        for pump in (1, 2):
            if s[f"pump{pump}_running"]:
                s[f"pump{pump}_run_hours"] += dt / 3600

    def _update_alarms(self):
        s = self._s
        conditions = [
            ("low_suction_trip", "LOW SUCTION TRIP", "P1", self._trip),
            ("pump1_fault", "PUMP 1 FAULT", "P1", s["pump1_fault"]),
            ("pump2_fault", "PUMP 2 FAULT", "P1", s["pump2_fault"]),
            ("high_discharge", "HIGH DISCHARGE", "P1", s["discharge_psi"] > s["sp_high_discharge_alarm_psi"]),
            ("low_tank", "LOW TANK", "P2", s["tank_level_ft"] < s["sp_low_tank_alarm_ft"]),
            ("high_tank", "HIGH TANK", "P2", s["tank_level_ft"] > s["sp_high_tank_alarm_ft"]),
            ("low_suction", "LOW SUCTION", "P2", s["suction_psi"] < s["sp_low_suction_alarm_psi"]),
            ("communications", "COMMUNICATIONS", "P3", bool(self._forced.get("communications_fault"))),
        ]
        for tag, description, priority, active in conditions:
            previous = self._alarms.get(tag)
            if active and (previous is None or not previous["active"]):
                self._alarms[tag] = dict(tag=tag, description=description,
                                         priority=priority, raised_at=self._time,
                                         acked=False, active=True)
            elif previous:
                previous["active"] = bool(active)

    def alarms(self) -> list[dict]:
        """Return active and cleared alarms, with acknowledgement history."""
        with self._lock:
            return [dict(alarm) for alarm in self._alarms.values()]
