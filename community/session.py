"""One browser-owned synthetic station, real Modbus listener and saved reports.

Simulator/protocol implementations are retained from the reviewed source.
Only the fixed exercise is exposed through HTTP. Loopback is the sole network
target; no model, credentials, private files or external service is consulted.
"""
import asyncio
from collections import OrderedDict
import copy
from datetime import datetime, timezone
import secrets
import threading
import time

from decoy_modbus.server import ModbusDecoy
from sim.station import StationSim
from .events import EventLog
from .hmi import ViewState
from . import wire


IDENTITY = {'identity_version':'public-example-v1',
    'utility':{'name':'Example','short':'Example'},
    'station':{'name':'Example station','number':0,'display':'Example station'},
    'hmi':{'vendor':'Example','family':'Example','model':'Example','model_short':'Example',
           'firmware':'0','serial':'Example','server_header':'Example/0',
           'modbus_device_id':{'VendorName':'Example','ProductCode':'Example','MajorMinorRevision':'0'}},
    'portal':{'product':'Example','version':'0','server_header':'Example/0'},
    'domains':{'print_any_url':False}}


class Session:
    def __init__(self):
        self.sim = StationSim()
        self.log = EventLog()
        self.view = ViewState()
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.used = time.monotonic()
        self.error = False
        self.reports = OrderedDict()
        self.receipt = None
        self.last_rejection = None
        self.modbus = ModbusDecoy(self.sim,self.log,IDENTITY['hmi']['modbus_device_id'],port=0,
                                 max_connections=8,idle_timeout_s=2)
        self.worker = threading.Thread(target=self._run,daemon=True)
        self.worker.start()
        if not self.ready.wait(2) or self.error:
            self.close()
            raise ValueError('station unavailable')
        self.prime()

    def _run(self):
        async def owned():
            job = asyncio.create_task(self.modbus.serve())
            try:
                while self.modbus.server is None:
                    if job.done(): await job
                    await asyncio.sleep(.005)
                self.ready.set()
                next_tick = time.monotonic()+1
                while not self.stop.is_set():
                    if time.monotonic() >= next_tick:
                        with self.lock:
                            self.sim.tick(1)
                            self.view.observe(self.sim.snapshot())
                        next_tick = time.monotonic()+1
                    await asyncio.sleep(.05)
            finally:
                self.modbus.close()
                job.cancel()
                try: await job
                except asyncio.CancelledError: pass
        try: asyncio.run(owned())
        except Exception:
            self.error = True
            self.ready.set()

    def prime(self):
        """Stage the one disclosed exercise, with all interlocks still evaluated."""
        with self.lock:
            self.sim.force('tank_level_ft',24)
            self.sim.force('suction_psi',50)
            self.sim.write('alarm_ack',True,'test')
            self.sim.write('pump2_cmd',True,'test')
            self.sim.tick(1)
            snapshot = self.sim.snapshot()
            if not snapshot['pump2_running']: raise ValueError('interlock prevents readiness')
            self.receipt = None
            self.view.observe(snapshot)
            self.log.write({'surface':'scenario','reason':'fixed scenario readied'})
            return {'ready':True,'pump2_display':snapshot['pump2_display']}

    def action(self, action, deadline):
        """Only known fixed actions, never an arbitrary endpoint/point/value."""
        with self.lock:
            if action == 'ready': return self.prime()
            if action == 'stop':
                before = self.sim.snapshot()
                if not before['pump2_running']: raise ValueError('Ready the station first')
                protocol = wire.stop_and_readback(self.modbus.port,deadline)
                self.sim.tick(1)
                after = self.sim.snapshot()
                if after['pump2_running'] or after['pump2_display'] != 'STOPPED (remote command)':
                    raise ValueError('stopped state not confirmed')
                self.receipt = dict(protocol,controlled_before_running=True,controlled_after_running=False,
                                    utc=datetime.now(timezone.utc).isoformat())
                self.view.observe(after)
                return {'stopped':True,'receipt':copy.deepcopy(self.receipt)}
            if action == 'rejected':
                before = self.sim.snapshot()
                protocol = wire.rejected_write(self.modbus.port,deadline)
                unchanged = self.sim.snapshot() == before
                if not unchanged: raise ValueError('rejected write changed state')
                self.last_rejection = protocol
                return {'rejected':True,'state_unchanged':unchanged,'receipt':protocol}
            if action == 'finish':
                from .report import build
                report = build(self)
                self.reports[report['encounter_id']] = report
                while len(self.reports) > 8: self.reports.popitem(last=False)
                return {'encounter_id':report['encounter_id'],'source':'deterministic'}
            raise ValueError('unknown fixed action')

    def snapshot(self):
        with self.lock:
            snapshot = self.sim.snapshot()
            self.view.observe(snapshot)
            return self.view.decorate(snapshot)

    def public(self):
        with self.lock: return self._public()

    def _public(self):
        events,dropped = self.log.snapshot()
        snapshot = self.snapshot()
        stopped = snapshot['pump2_display'] == 'STOPPED (remote command)'
        return {'schema':'community-state-v1','station':snapshot,'events':events,'dropped_events':dropped,
                'received_utc':datetime.now(timezone.utc).isoformat(),
                'headline':'A remote command stopped Pump 2' if stopped else 'The practice station is running',
                'meaning':'A device command can affect a process. This exercise changes only your simulated station.' if stopped
                          else 'Explore the equipment display, then send the fixed local stop command.',
                'next_action':'Open the supporting write, then finish and download the report.' if stopped
                              else 'Choose Send remote stop to see the request and its consequence.',
                'source':'deterministic','protocol_receipt':copy.deepcopy(self.receipt),
                'technical':{'modbus_port':self.modbus.port,'scope':'Owned loopback station only'},
                'reports':list(self.reports)}

    def close(self):
        self.stop.set()
        self.modbus.close()
        self.worker.join(3)
