"""T-SIM acceptance cases, using only the public simulator interface."""

import inspect
import math
import unittest
import threading

from sim.station import StationSim


class SimulatorTests(unittest.TestCase):
    def test_SOL_05_D3_high_stop_active_fill_recovery_and_lead(self):
        for source in ("modbus", "hmi", "test"):
            sim = StationSim(start_utc=0)
            sim.write_many({"sp_tank_start_ft": 37, "sp_tank_stop_ft": 39}, "test")
            sim.force("tank_level_ft", 35)
            sim.write_many({"pump1_cmd": True, "pump2_cmd": True}, source)
            sim.tick()
            self.assertTrue(sim.read("pump1_running") and sim.read("pump2_running"))
            sim.force("tank_level_ft", 38)
            sim.tick()
            self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
            self.assertEqual(sim.read("lead_pump"), 2)
            self.assertEqual(sim.read("remote_command_active"), source == "modbus")
            sim.force("tank_level_ft", 37.5)
            sim.tick()
            self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
            sim.force("tank_level_ft", 37)
            sim.tick()
            self.assertTrue(sim.read("pump2_running"))
            self.assertFalse(sim.read("pump1_running"))
            sim.force("tank_level_ft", 38)
            sim.tick()
            self.assertEqual(sim.read("lead_pump"), 1)

    def test_SOL_02_exact_hard_stops_all_sources_and_pumps(self):
        for source in ("modbus", "hmi", "test"):
            for high_first in (False, True):
                for pump in (1, 2):
                    for above in (0, .1):
                        with self.subTest(source=source, high_first=high_first, pump=pump, above=above):
                            sim = StationSim(start_utc=0)
                            if high_first:
                                self.assertTrue(sim.write_many({"sp_tank_start_ft": 37, "sp_tank_stop_ft": 39}, "test").ok)
                            threshold = 38 if high_first else 36
                            sim.force("tank_level_ft", threshold + above)
                            sim.write(f"pump{pump}_cmd", True, source)
                            sim.tick()
                            s = sim.snapshot()
                            self.assertFalse(s["pump1_running"] or s["pump2_running"])
                            self.assertEqual(s[f"pump{pump}_display"], "STOPPED")
                            self.assertEqual(s["remote_command_active"], source == "modbus")
                            # A consumed start cannot restart above the normal
                            # start threshold when the safety condition clears.
                            sim.force("tank_level_ft", threshold - .2)
                            sim.tick()
                            self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))

    def test_SOL_02_active_fill_stops_recovers_and_alternates_once(self):
        for source in ("modbus", "hmi", "test"):
            sim = StationSim(start_utc=0)
            sim.force("tank_level_ft", 30)
            sim.write_many({"pump1_cmd": True, "pump2_cmd": True}, source)
            sim.tick()
            self.assertTrue(sim.read("pump1_running") and sim.read("pump2_running"))
            sim.force("tank_level_ft", 36)
            sim.tick()
            self.assertEqual(sim.read("lead_pump"), 2)
            self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
            sim.force("tank_level_ft", 37)
            sim.tick(3)
            self.assertEqual(sim.read("lead_pump"), 2)
            sim.force("tank_level_ft", 28)
            sim.tick()
            self.assertTrue(sim.read("pump2_running"))
            self.assertFalse(sim.read("pump1_running"))
            sim.force("tank_level_ft", 36)
            sim.tick()
            self.assertEqual(sim.read("lead_pump"), 1)

    def test_SOL_02_remote_stop_provenance_survives_safety_and_recovery(self):
        sim = StationSim(start_utc=0)
        sim.force("tank_level_ft", 24)
        sim.tick()
        sim.write("pump2_cmd", False, "modbus")
        sim.force("tank_level_ft", 36)
        sim.tick()
        s = sim.snapshot()
        self.assertTrue(s["remote_command_active"])
        self.assertEqual(s["pump1_display"], "STOPPED")
        self.assertEqual(s["pump2_display"], "STOPPED (remote command)")
        sim.force("tank_level_ft", 24)
        sim.tick()
        self.assertFalse(sim.read("pump2_running"))
        sim.write("pump2_cmd", True, "hmi")
        sim.tick()
        self.assertTrue(sim.read("pump2_running"))
        self.assertFalse(sim.read("remote_command_active"))

    def test_SOL_02_fault_trip_and_lower_high_threshold_precede_start(self):
        for source in ("modbus", "hmi", "test"):
            for pump in (1, 2):
                sim = StationSim(start_utc=0)
                sim.force("tank_level_ft", 24)
                sim.force(f"pump{pump}_fault", True)
                sim.write(f"pump{pump}_cmd", True, source)
                sim.tick()
                self.assertFalse(sim.read(f"pump{pump}_running"))
                sim.force(f"pump{pump}_fault", False)
                sim.force("suction_psi", 19)
                sim.tick()
                self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
                sim.force("suction_psi", 26)
                sim.write("alarm_ack", True, "test")
                sim.tick()
                self.assertTrue(sim.read(f"pump{pump}_running"))
        sim = StationSim(start_utc=0)
        sim.write("sp_high_tank_alarm_ft", 28, "test")
        sim.force("tank_level_ft", 28)
        sim.tick()
        self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
        sim.force("tank_level_ft", 27.9)
        sim.tick()
        self.assertTrue(sim.read("pump1_running"))

    def test_SOL_02_physics_threshold_crossing_stops_before_snapshot(self):
        sim = StationSim(start_utc=0)
        sim.force("tank_level_ft", 35.9999)
        sim.write_many({"pump1_cmd": True, "pump2_cmd": True}, "modbus")
        sim.tick()
        self.assertGreaterEqual(sim.read("tank_level_ft"), 36)
        self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
        self.assertEqual(sim.read("flow_gpm"), 0)

    def test_SOL_01_batch_rejects_without_any_side_effect(self):
        sim = StationSim(start_utc=0)
        sim.force("suction_psi", 19)
        sim.tick()
        sim.force("suction_psi", 26)
        before = sim.snapshot()
        for updates in ({"alarm_ack": True, "pump1_cmd": True, "pump2_cmd": "invalid"},
                        {"pump1_cmd": True, "alarm_ack": True, "sp_tank_stop_ft": 10}):
            for source in ("modbus", "hmi", "test"):
                self.assertFalse(sim.write_many(updates, source).ok)
                self.assertEqual(sim.snapshot(), before)

    def test_SOL_01_concurrent_snapshots_never_see_partial_batches(self):
        sim = StationSim(start_utc=0)
        start = threading.Barrier(2)
        failures = []

        def writer():
            try:
                start.wait()
                for _ in range(1000):
                    for a, b, command in ((37, 39, True), (28, 36, False)):
                        result = sim.write_many({"sp_tank_start_ft": a, "sp_tank_stop_ft": b,
                                                 "pump1_cmd": command, "pump2_cmd": command}, "modbus")
                        if not result.ok:
                            failures.append(result)
            except BaseException as error:
                failures.append(type(error).__name__)

        thread = threading.Thread(target=writer)
        thread.start()
        start.wait()
        for _ in range(2000):
            s = sim.snapshot()
            self.assertIn((s["sp_tank_start_ft"], s["sp_tank_stop_ft"], s["pump1_cmd"], s["pump2_cmd"]),
                          ((28, 36, False, False), (37, 39, True, True)))
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])

    def test_T_SIM_01(self):
        for seed in (1, 2):
            sim = StationSim(seed, 0)
            twin = StationSim(seed, 0)
            for _ in range(1440):
                sim.tick(60)
                twin.tick(60)
                s = sim.snapshot()
                self.assertEqual(s, twin.snapshot())
                for key, low, high in (("tank_level_ft", 0, 40), ("suction_psi", 45, 55),
                                       ("discharge_psi", 55, 85), ("flow_gpm", 0, 1500),
                                       ("chlorine_mg_l", .8, 1.5)):
                    self.assertTrue(math.isfinite(s[key]))
                    self.assertTrue(low <= s[key] <= high, (key, s[key]))

    def test_T_SIM_02(self):
        sim = StationSim(start_utc=0)
        for lead in (1, 2, 1):
            self.assertEqual(sim.read("lead_pump"), lead)
            sim.force("tank_level_ft", 28)
            sim.tick()
            self.assertTrue(sim.read(f"pump{lead}_running"))
            sim.force("tank_level_ft", 25)
            sim.tick()
            self.assertTrue(sim.read("pump1_running") and sim.read("pump2_running"))
            sim.force("tank_level_ft", 36)
            sim.tick()
            self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
            self.assertEqual(sim.read("lead_pump"), 3 - lead)

    def test_T_SIM_03(self):
        sim = StationSim(start_utc=0)
        sim.force("tank_level_ft", 24)
        sim.tick()
        sim.force("suction_psi", 19.9)
        sim.tick()
        self.assertFalse(sim.read("pump1_running") or sim.read("pump2_running"))
        trip = next(a for a in sim.alarms() if a["tag"] == "low_suction_trip")
        self.assertEqual((trip["description"], trip["priority"], trip["active"]), ("LOW SUCTION TRIP", "P1", True))
        sim.write("alarm_ack", True, "hmi")
        self.assertTrue(sim.snapshot()["suction_trip_latched"])
        sim.force("suction_psi", 26)
        sim.write("alarm_ack", True, "modbus")
        sim.tick()
        self.assertTrue(sim.snapshot()["suction_trip_latched"])
        sim.write("alarm_ack", True, "hmi")
        sim.tick()
        self.assertFalse(sim.snapshot()["suction_trip_latched"])
        self.assertTrue(sim.read("pump1_running"))
        self.assertFalse(next(a for a in sim.alarms() if a["tag"] == "low_suction_trip")["active"])

    def test_T_SIM_04(self):
        sim = StationSim(start_utc=0)
        self.assertEqual(sim.write("discharge_psi", 99, "test").reason, "read_only")
        with self.assertRaises(ValueError):
            sim.force("discharge_psi", 99)
        # Every computed discharge assignment belongs to the physics method.
        source = inspect.getsource(StationSim)
        outside = source[:source.index("    def _physics")] + source[source.index("    def _update_alarms"):]
        self.assertNotIn('s["discharge_psi"] =', outside)
        sim.write("pump1_cmd", True, "test")
        sim.tick()
        self.assertTrue(70 <= sim.read("discharge_psi") <= 80)
        sim.write("pump1_cmd", False, "test")
        sim.tick(120)
        self.assertTrue(55 < sim.read("discharge_psi") < 65)

    def test_T_SIM_05(self):
        sim = StationSim(start_utc=0)
        sim.force("tank_level_ft", 24)
        sim.tick()
        hours = sim.read("pump2_run_hours")
        self.assertTrue(sim.write("pump2_cmd", False, "modbus").ok)
        sim.tick(10)
        self.assertFalse(sim.read("pump2_running"))
        self.assertEqual(sim.read("pump2_run_hours"), hours)
        self.assertTrue(sim.read("remote_command_active"))
        self.assertEqual(sim.snapshot()["pump2_display"], "STOPPED (remote command)")
        sim.write("pump2_cmd", True, "hmi")
        sim.tick()
        self.assertFalse(sim.read("remote_command_active"))
        self.assertTrue(sim.read("pump2_running"))

    def test_T_SIM_06(self):
        sim = StationSim(start_utc=0)
        before = sim.snapshot()
        self.assertEqual(sim.write("sp_tank_stop_ft", 27, "modbus").reason, "out_of_band")
        self.assertEqual(sim.write("sp_tank_start_ft", 36, "hmi").reason, "out_of_band")
        self.assertEqual(sim.write("sp_tank_start_ft", float("nan"), "test").reason, "bad_value")
        self.assertEqual(sim.write("no_point", 0, "test").reason, "unknown_point")
        self.assertEqual(sim.write("pump1_cmd", "false", "test").reason, "bad_value")
        self.assertEqual(sim.snapshot(), before)

    def test_T_SIM_07(self):
        sim = StationSim(start_utc=0)
        initial = sim.snapshot()
        sim.write("pump1_cmd", True, "modbus")
        sim.tick(100)
        self.assertFalse(sim.reset_from("192.0.2.1"))
        self.assertNotEqual(initial, sim.snapshot())
        self.assertTrue(sim.reset_from("127.0.0.1"))
        self.assertEqual(initial, sim.snapshot())


if __name__ == "__main__":
    unittest.main()
