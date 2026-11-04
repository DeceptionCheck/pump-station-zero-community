"""Community-owned bounded event projection, with no intelligence inference.

Bodies, query strings, headers, credentials and source addresses are never
retained. Only protocol fields needed to explain this synthetic exercise enter
memory. Returned records are copies and cannot change retained evidence.
"""
from collections import deque
import copy
from datetime import datetime, timezone
import threading

PATHS = frozenset(('/','/overview','/pumps','/tank','/alarms','/trends','/setup','/about',
                   '/login','/vpn/status','/admin','/acknowledge'))
REASONS = frozenset(('ok','bad_value','bad_address','illegal_function','gateway_no_target',
                     'internal_failure','out_of_band','unknown_point','read_only',
                     'fixed scenario readied','restricted_form','page'))


class EventLog:
    def __init__(self):
        self._rows = deque(maxlen=256)
        self._lock = threading.Lock()
        self._sequence = 0
        self.dropped = 0

    def write(self, event):
        with self._lock:
            self._sequence += 1
            surface,reason = event.get('surface'),event.get('reason','ok')
            row = {'event_id':str(self._sequence), 'ts':datetime.now(timezone.utc).isoformat(),
                   'surface':surface if surface in {'http','hmi','portal','modbus','scenario'} else 'http',
                   'reason':reason if reason in REASONS else 'recorded event'}
            if isinstance(event.get('http'),dict):
                value = event['http']
                method,path = value.get('method'),value.get('path')
                row['http'] = {'method':method if method in {'GET','HEAD','POST'} else 'OTHER',
                               'path':path if path in PATHS else '/unrecognized'}
                row['status'] = int(event.get('status',200))
            if isinstance(event.get('modbus'),dict):
                value = event['modbus']
                row['modbus'] = {key:value.get(key) for key in
                    ('unit_id','function_code','address','quantity','exception_code')}
                row['modbus']['values'] = [number for number in value.get('values',[])[:256]
                                           if type(number) is int and 0 <= number <= 65535]
            if len(self._rows) == self._rows.maxlen:
                self.dropped += 1
            self._rows.append(copy.deepcopy(row))
            return copy.deepcopy(row)

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(list(self._rows)), self.dropped
