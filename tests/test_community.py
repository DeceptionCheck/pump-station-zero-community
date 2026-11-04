"""Fresh-user journeys exercise actual local TCP Modbus and HTTP ownership."""
from contextlib import contextmanager
import copy
import http.client
import json
import socket
import struct
import threading
import time
import unittest

from community.server import CommunityServer
from community.session import Session
from community import report, wire
from community.events import EventLog


@contextmanager
def server(**options):
    instance = CommunityServer(('127.0.0.1',0),**options)
    worker = threading.Thread(target=instance.serve_forever,kwargs={'poll_interval':.02},daemon=True)
    worker.start()
    try: yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join(1)


def request(instance, path='/', cookie=None, action=None, method=None, headers=None, raw=None):
    connection = http.client.HTTPConnection('127.0.0.1',instance.server_port,timeout=4)
    fields = dict(headers or {})
    if cookie: fields['Cookie'] = cookie
    if action is not None:
        raw = json.dumps({'action':action})
        fields.update({'Content-Type':'application/json','Origin':instance.origin})
    try:
        connection.request(method or ('POST' if raw is not None else 'GET'),path,raw,fields)
        reply = connection.getresponse()
        return reply.status,dict(reply.getheaders()),reply.read()
    finally: connection.close()


def visitor(instance):
    status,headers,body = request(instance)
    assert status == 200
    return headers['Set-Cookie'].split(';')[0]


class JourneyTests(unittest.TestCase):
    def test_running_station_real_stop_readback_hmi_timeline_and_download(self):
        with server() as app:
            cookie = visitor(app)
            initial = json.loads(request(app,'/api/state',cookie)[2])
            self.assertEqual(initial['station']['pump2_display'],'RUNNING')
            self.assertEqual(request(app,'/api/action',cookie,'ready')[0],200)
            status,_,raw = request(app,'/api/action',cookie,'stop')
            self.assertEqual(status,200)
            receipt = json.loads(raw)['receipt']
            self.assertTrue(receipt['independent_read_connection'])
            self.assertEqual(receipt['write_reply_hex'],'0500010000')
            self.assertEqual(receipt['read_reply_hex'],'010100')
            page = request(app,'/pumps',cookie)[2]
            for value in (b'STOPPED (remote command)',b'#C00000',b'UNACK',b'Fictional pump station.'):
                self.assertIn(value,page)
            state = json.loads(request(app,'/api/state',cookie)[2])
            self.assertEqual([row['modbus']['function_code'] for row in state['events'] if 'modbus' in row],[5,1])
            self.assertEqual(state['source'],'deterministic')
            ident = json.loads(request(app,'/api/action',cookie,'finish')[2])['encounter_id']
            status,headers,page = request(app,'/report?id='+ident+'&format=html',cookie)
            self.assertEqual(status,200)
            self.assertIn('attachment',headers['Content-Disposition'])
            self.assertIn(b'No real equipment',page)
            self.assertIn(b'separate connection',page)
            saved = json.loads(request(app,'/report?id='+ident+'&format=json',cookie)[2])
            self.assertEqual(saved['schema'],'community-report-v1')
            self.assertEqual(saved['counts']['write_attempts'],1)

    def test_two_browser_contexts_cannot_read_each_others_reports_or_change_each_others_station(self):
        with server() as app:
            one,two = visitor(app),visitor(app)
            self.assertNotEqual(one,two)
            request(app,'/api/action',one,'stop')
            ident = json.loads(request(app,'/api/action',one,'finish')[2])['encounter_id']
            for format in ('html','json'):
                self.assertEqual(request(app,'/report?id='+ident+'&format='+format,two)[0],410)
                self.assertEqual(request(app,'/report?id='+ident+'&format='+format)[0],410)
            other = json.loads(request(app,'/api/state',two)[2])
            self.assertEqual(other['station']['pump2_display'],'RUNNING')
            self.assertFalse(any(row.get('modbus') for row in other['events']))
            self.assertEqual(request(app,'/report?id='+ident+'&format=json',one)[0],200)

    def test_new_session_keeps_old_report_out_of_new_cookie_scope(self):
        with server() as app:
            old = visitor(app)
            ident = json.loads(request(app,'/api/action',old,'finish')[2])['encounter_id']
            status,headers,_ = request(app,'/api/action',old,'new')
            self.assertEqual(status,200)
            new = headers['Set-Cookie'].split(';')[0]
            self.assertNotEqual(new,old)
            self.assertEqual(request(app,'/report?id='+ident+'&format=html',new)[0],410)
            self.assertEqual(request(app,'/report?id='+ident+'&format=html',old)[0],200)

    def test_rejected_atomic_change_has_visible_evidence_and_no_mutation(self):
        with server() as app:
            cookie = visitor(app)
            result = json.loads(request(app,'/api/action',cookie,'rejected')[2])
            self.assertTrue(result['rejected'] and result['state_unchanged'])
            state = json.loads(request(app,'/api/state',cookie)[2])
            self.assertEqual(state['station']['sp_tank_start_ft'],28)
            self.assertEqual(state['station']['sp_tank_stop_ft'],36)
            rejected = [row for row in state['events'] if 'modbus' in row]
            self.assertEqual(rejected[-1]['modbus']['exception_code'],3)

    def test_origin_host_and_action_scope_reject_before_mutation(self):
        with server() as app:
            cookie = visitor(app)
            for headers in ({'Origin':'https://192.0.2.1'},{'Host':'192.0.2.1'}):
                self.assertEqual(request(app,'/api/state',cookie,headers=headers)[0],403)
            for packet in ({'action':'stop','host':'192.0.2.1'},{'action':'stop','port':5020},
                           {'action':'http://192.0.2.1'},{'action':[]},[]):
                self.assertEqual(request(app,'/api/action',cookie,raw=json.dumps(packet),headers={
                    'Content-Type':'application/json','Origin':app.origin})[0],400)
            self.assertEqual(request(app,'/api/action',cookie,raw='{}',headers={'Content-Type':'application/json'})[0],403)
            self.assertEqual(json.loads(request(app,'/api/state',cookie)[2])['station']['pump2_display'],'RUNNING')

    def test_forms_reject_without_retaining_credentials(self):
        with server() as app:
            cookie = visitor(app)
            injected = 'never-retain-this-credential'
            self.assertEqual(request(app,'/setup',cookie,raw='username=example&password='+injected,
                                     headers={'Origin':app.origin})[0],403)
            self.assertNotIn(injected,request(app,'/api/state',cookie)[2].decode())
            self.assertEqual(json.loads(request(app,'/api/state',cookie)[2])['station']['pump2_display'],'RUNNING')

    def test_capacity_and_nonloopback_binding_fail_closed(self):
        with self.assertRaises(ValueError): CommunityServer(('0.0.0.0',0))
        with server(max_sessions=1) as app:
            cookie = visitor(app)
            self.assertEqual(request(app)[0],503)
            self.assertEqual(request(app,'/api/state',cookie)[0],200)
            self.assertEqual(request(app,'/api/action',cookie,'new')[0],503)

    def test_report_is_immutable_after_a_later_scenario_and_requires_known_format(self):
        with server() as app:
            cookie = visitor(app)
            request(app,'/api/action',cookie,'stop')
            ident = json.loads(request(app,'/api/action',cookie,'finish')[2])['encounter_id']
            before = request(app,'/report?id='+ident+'&format=json',cookie)[2]
            request(app,'/api/action',cookie,'ready')
            self.assertEqual(before,request(app,'/report?id='+ident+'&format=json',cookie)[2])
            self.assertEqual(request(app,'/report?id='+ident+'&format=other',cookie)[0],400)
            self.assertEqual(request(app,'/report?id='+ident+'&id=second&format=json',cookie)[0],400)

    def test_hmi_pages_and_state_stream_use_same_station(self):
        with server() as app:
            cookie = visitor(app)
            for path in ('/overview','/pumps','/tank','/alarms','/trends','/setup','/about','/login','/vpn/status'):
                self.assertEqual(request(app,path,cookie)[0],200,path)
            request(app,'/api/action',cookie,'stop')
            connection = http.client.HTTPConnection('127.0.0.1',app.server_port,timeout=3)
            try:
                connection.request('GET','/events',headers={'Cookie':cookie})
                reply = connection.getresponse()
                line = reply.fp.readline(65536)
                snapshot = json.loads(line.decode().removeprefix('data: '))
                self.assertEqual(snapshot['pump2_display'],'STOPPED (remote command)')
                self.assertTrue(snapshot['remote_indications'])
            finally: connection.close()

    def test_partial_and_oversized_http_bodies_cannot_run_actions(self):
        with server() as app:
            cookie = visitor(app)
            with socket.create_connection(('127.0.0.1',app.server_port),timeout=3) as connection:
                request_bytes = ('POST /api/action HTTP/1.1\r\nHost: 127.0.0.1:'+str(app.server_port)+'\r\nOrigin: '+app.origin+
                    '\r\nCookie: '+cookie+'\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{"action":"stop"}').encode()
                connection.sendall(request_bytes)
                connection.shutdown(socket.SHUT_WR)
                self.assertIn(b'400',connection.recv(4096).split(b'\r\n')[0])
            self.assertEqual(request(app,'/api/action',cookie,raw='x'*4097,headers={'Origin':app.origin})[0],400)
            self.assertEqual(json.loads(request(app,'/api/state',cookie)[2])['station']['pump2_display'],'RUNNING')


class ProtocolAndProjectionTests(unittest.TestCase):
    def test_invalid_and_partial_multiwrites_leave_entire_state_unchanged(self):
        station = Session()
        try:
            with station.lock:
                for pdu in (struct.pack('>BHHBHH',16,0,2,4,280,270),
                            struct.pack('>BHHBHH',16,6,2,4,300,400),
                            struct.pack('>BHHB',15,2,2,1)+b'\x03',
                            struct.pack('>BHHB',16,0,2,4)+b'\x01\x18'):
                    before = station.sim.snapshot()
                    response,_,_ = station.modbus._dispatch(1,pdu)
                    self.assertTrue(response[0]&128)
                    self.assertEqual(before,station.sim.snapshot())
                before = station.sim.snapshot()
                with socket.create_connection(('127.0.0.1',station.modbus.port),timeout=2) as connection:
                    pdu = struct.pack('>BHHBHH',16,0,2,4,250,350)
                    frame = struct.pack('>HHHB',12,0,len(pdu)+1,1)+pdu
                    connection.sendall(frame[:-1])
                    connection.shutdown(socket.SHUT_WR)
                    connection.settimeout(1)
                    self.assertEqual(connection.recv(32),b'')
                self.assertEqual(before,station.sim.snapshot())
        finally: station.close()

    def test_actual_multiwrite_atomic_success_and_hard_stop_override(self):
        station = Session()
        try:
            with station.lock:
                response = wire.exchange(station.modbus.port,struct.pack('>BHHBHH',16,0,2,4,250,350),time.monotonic()+2)
                self.assertEqual(response,struct.pack('>BHH',16,0,2))
                self.assertEqual(station.sim.read('sp_tank_start_ft'),25)
                self.assertEqual(station.sim.read('sp_tank_stop_ft'),35)
                station.sim.force('tank_level_ft',35)
                wire.exchange(station.modbus.port,struct.pack('>BHH',5,1,65280),time.monotonic()+2)
                station.sim.tick(1)
                self.assertFalse(station.sim.read('pump2_running'))
        finally: station.close()

    def test_projection_omits_arbitrary_text_bodies_and_all_credentials_and_is_bounded(self):
        log = EventLog()
        marker = 'never-retain-this-credential'
        for index in range(300):
            log.write({'surface':'http','reason':marker,'http':{'path':'/password='+marker,
                'method':'GET','password':marker,'body':marker,'headers':{'Authorization':marker}}})
        rows,dropped = log.snapshot()
        self.assertEqual((len(rows),dropped),(256,44))
        self.assertNotIn(marker,json.dumps(rows))
        rows[0]['reason'] = 'mutated'
        self.assertNotEqual(log.snapshot()[0][0]['reason'],'mutated')

    def test_report_escapes_all_evidence_fields(self):
        station = Session()
        try:
            value = report.build(station)
            value['summary'] = '<script>alert(1)</script>'
            value['events'][0]['reason'] = '<img src=x onerror=alert(1)>'
            rendered = report.html(value)
            self.assertNotIn('<script>',rendered)
            self.assertNotIn('<img ',rendered)
            self.assertIn('&lt;script&gt;',rendered)
        finally: station.close()


if __name__ == '__main__': unittest.main()
