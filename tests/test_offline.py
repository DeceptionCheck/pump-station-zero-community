"""The whole journey runs with outside connections and private imports denied."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import http.client,json,socket,sys,threading
sys.path.insert(0,sys.argv[1])
connections=[]
def audit(event,args):
    if event == 'import' and args[0].split('.')[0] in {'analyst','brain','app_runtime','ui'}:
        raise RuntimeError('private import forbidden')
    if event == 'socket.connect':
        address=args[1]
        if not isinstance(address,tuple) or address[0]!='127.0.0.1':
            raise PermissionError('outside connection forbidden')
        connections.append(address[0])
    if event == 'socket.getaddrinfo' and args[0]!='127.0.0.1':
        raise PermissionError('outside resolution forbidden')
sys.addaudithook(audit)
probe=socket.socket()
try:
    try: probe.connect(('192.0.2.1',1))
    except PermissionError: guard=True
    else: raise AssertionError('guard did not reject outside connection')
finally: probe.close()
from community.server import CommunityServer
app=CommunityServer(('127.0.0.1',0))
worker=threading.Thread(target=app.serve_forever,kwargs={'poll_interval':.02},daemon=True);worker.start()
def request(path,cookie=None,action=None):
    c=http.client.HTTPConnection('127.0.0.1',app.server_port,timeout=4)
    h={}
    if cookie:h['Cookie']=cookie
    if action:h.update({'Content-Type':'application/json','Origin':app.origin})
    try:
        c.request('POST' if action else 'GET',path,json.dumps({'action':action}) if action else None,h)
        r=c.getresponse();return r.status,dict(r.getheaders()),r.read()
    finally:c.close()
try:
    status,headers,_=request('/');assert status==200
    cookie=headers['Set-Cookie'].split(';')[0]
    assert request('/overview',cookie)[0]==200
    for action in ('ready','stop','rejected'):assert request('/api/action',cookie,action)[0]==200
    status,_,raw=request('/api/action',cookie,'finish');assert status==200
    ident=json.loads(raw)['encounter_id']
    status,_,raw=request('/report?id='+ident+'&format=json',cookie)
    value=json.loads(raw);assert status==200 and value['source']=='deterministic'
    assert value['protocol_receipt']['independent_read_connection']
    assert value['counts']['rejected_writes']==1
    assert request('/api/action',cookie,'new')[0]==200
    print(json.dumps({'outside_guard_positive_control':guard,'loopback_connections':len(connections),
                     'private_imports':0,'journey':'PASS','real_modbus':True}))
finally:app.shutdown();app.server_close();worker.join(1)
'''


class OfflineTests(unittest.TestCase):
    def test_isolated_interpreter_complete_journey_with_network_and_import_guard(self):
        completed = subprocess.run([sys.executable,'-I','-c',SCRIPT,str(ROOT)],
                                   capture_output=True,text=True,timeout=15)
        self.assertEqual(completed.returncode,0,completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value['journey'],'PASS')
        self.assertTrue(value['outside_guard_positive_control'])
        self.assertGreater(value['loopback_connections'],5)


if __name__ == '__main__': unittest.main()
