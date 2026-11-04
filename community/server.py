"""Loopback-only Community HTTP surfaces and independent browser ownership.

No external bind or target option exists. Local operating-system users are
trusted; this is not a public hosting or multi-tenant security boundary. Host,
Origin, finite actions, bounded framing and cookie ownership are enforced here.
"""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
import socketserver
import threading
import time
from urllib.parse import parse_qs, urlsplit

from decoy_modbus.register_map import REGISTERS
from . import hmi, report
from .session import IDENTITY, Session

ASSETS = Path(__file__).with_name('assets')
HMI_PATHS = frozenset(('/overview','/pumps','/tank','/alarms','/trends','/setup','/about'))


class CommunityServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 64

    def __init__(self, address=('127.0.0.1',8180), *, max_sessions=8, ttl=1200):
        if address[0] != '127.0.0.1': raise ValueError('Community requires loopback')
        if not 1 <= max_sessions <= 8 or not 1 <= ttl <= 1200: raise ValueError('invalid capacity')
        self.sessions = {}
        self.sessions_lock = threading.RLock()
        self.maximum, self.ttl = max_sessions, ttl
        self.capacity = threading.BoundedSemaphore(32)
        super().__init__(address,Handler)
        self.origin = 'http://127.0.0.1:'+str(self.server_port)

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'Example'
        self.server_port = self.server_address[1]

    def process_request(self, request, client_address):
        if not self.capacity.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try: super().process_request(request,client_address)
        except BaseException:
            self.capacity.release()
            raise

    def process_request_thread(self, request, client_address):
        try: super().process_request_thread(request,client_address)
        finally: self.capacity.release()

    def session(self, raw_cookie, create=False, fresh=False):
        jar = SimpleCookie()
        try: jar.load(raw_cookie or '')
        except Exception: return None,None
        ident = jar['psz_community'].value if 'psz_community' in jar else ''
        with self.sessions_lock:
            expired = [key for key,value in self.sessions.items() if time.monotonic()-value.used > self.ttl]
            for key in expired: self.sessions.pop(key).close()
            if not fresh and ident in self.sessions:
                value = self.sessions[ident]
                value.used = time.monotonic()
                return ident,value
            if not create: return None,None
            if len(self.sessions) >= self.maximum: return None,None
            ident = secrets.token_hex(24)
            value = Session()
            self.sessions[ident] = value
            return ident,value

    def server_close(self):
        with self.sessions_lock:
            for value in self.sessions.values(): value.close()
            self.sessions.clear()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = 'Example/0'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args): pass

    def handle_one_request(self):
        self.entered = time.monotonic()
        self.committed = False
        self.connection.settimeout(2)
        self.timer = threading.Timer(4,self.abort)
        self.timer.daemon = True
        self.timer.start()
        try: super().handle_one_request()
        finally:
            self.timer.cancel()
            self.close_connection = True

    def abort(self):
        try: self.connection.shutdown(socket.SHUT_RDWR)
        except OSError: pass

    def answer(self, status, body, media='text/plain; charset=utf-8', headers=()):
        if self.committed: return
        raw = body.encode() if isinstance(body,str) else body
        if len(raw) > 1024*1024:
            status,raw = 503,b'Bounded response unavailable.'
        self.committed = True
        self.send_response(status)
        for name,value in [('Content-Type',media),('Content-Length',str(len(raw))),
            ('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),
            ('Referrer-Policy','no-referrer'),('X-Frame-Options','SAMEORIGIN'),
            ('Content-Security-Policy',"default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; form-action 'self'"),
            ('Connection','close'),*headers]: self.send_header(name,value)
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(raw)

    def document(self, value, status=200, headers=()):
        self.answer(status,json.dumps(value,allow_nan=False),'application/json; charset=utf-8',headers)

    def boundary(self):
        hosts = self.headers.get_all('Host',[])
        if hosts != ['127.0.0.1:'+str(self.server.server_port)]:
            self.answer(403,'Host rejected. Open the printed loopback URL.')
            return False
        origins = self.headers.get_all('Origin',[])
        if origins and origins != [self.server.origin] or self.command == 'POST' and origins != [self.server.origin]:
            self.answer(403,'Origin rejected.')
            return False
        if self.headers.get('Transfer-Encoding'):
            self.answer(400,'Unsupported framing.')
            return False
        return True

    def do_GET(self): self.route()
    def do_HEAD(self): self.route()
    def do_POST(self): self.route()

    def route(self):
        try:
            if not self.boundary(): return
            parsed = urlsplit(self.path)
            if parsed.scheme or parsed.netloc or len(self.path) > 256:
                self.answer(400,'Invalid target.'); return
            path = parsed.path
            if path in {'/assets/console.js','/assets/console.css'} and self.command in {'GET','HEAD'}:
                file = ASSETS/path.rsplit('/',1)[1]
                self.answer(200,file.read_bytes(),'text/javascript' if file.suffix == '.js' else 'text/css'); return
            ident,station = self.server.session(self.headers.get('Cookie'),create=path=='/' and self.command=='GET')
            if station is None:
                self.answer(503 if path=='/' else 410,'Open the Community start page for an available new session.'); return
            cookie = ('Set-Cookie','psz_community='+ident+'; Path=/; HttpOnly; SameSite=Strict')
            if self.command == 'POST':
                lengths = self.headers.get_all('Content-Length',[])
                if len(lengths)!=1 or not lengths[0].isascii() or not lengths[0].isdigit() or int(lengths[0]) > 4096:
                    self.answer(400,'Invalid body length.'); return
                raw = self.rfile.read(int(lengths[0]))
                if len(raw) != int(lengths[0]): self.answer(400,'Incomplete body.'); return
                if path in {'/login','/setup','/acknowledge'}:
                    station.log.write({'surface':'http','http':{'method':'POST','path':path},'status':403,'reason':'restricted_form'})
                    self.answer(403,'Access restricted.'); return
                if path != '/api/action' or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    self.answer(400,'Use the fixed Community action.'); return
                packet = json.loads(raw)
                if not isinstance(packet,dict) or set(packet) != {'action'} or not isinstance(packet['action'],str):
                    self.answer(400,'One fixed action is required.'); return
                if packet['action'] == 'new':
                    new_id,new_session = self.server.session(None,create=True,fresh=True)
                    if new_session is None: self.answer(503,'Session capacity reached. Wait for an idle session to expire.'); return
                    self.document({'new_session':True},headers=(('Set-Cookie','psz_community='+new_id+'; Path=/; HttpOnly; SameSite=Strict'),)); return
                self.document(station.action(packet['action'],self.entered+3.6)); return
            if path == '/':
                self.answer(200,(ASSETS/'console.html').read_bytes(),'text/html; charset=utf-8',(cookie,)); return
            if path == '/api/state': self.document(station.public()); return
            if path == '/api/registers': self.document([vars(row) for row in REGISTERS]); return
            if path == '/report':
                query = parse_qs(parsed.query,keep_blank_values=True)
                if set(query) != {'id','format'} or any(len(values)!=1 for values in query.values()):
                    self.answer(400,'Choose a saved report.'); return
                with station.lock: saved = station.reports.get(query['id'][0])
                if saved is None: self.answer(410,'Report not in this session.'); return
                if query['format'][0] == 'html':
                    self.answer(200,report.html(saved),'text/html; charset=utf-8',(('Content-Disposition','attachment; filename="community-report.html"'),)); return
                if query['format'][0] == 'json':
                    self.document(saved,headers=(('Content-Disposition','attachment; filename="community-report.json"'),)); return
                self.answer(400,'Unsupported report format.'); return
            if path == '/events':
                if self.command == 'HEAD': self.answer(200,b'','text/event-stream'); return
                self.committed = True
                self.timer.cancel()
                self.connection.settimeout(2)
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Cache-Control','no-store')
                self.send_header('Connection','close')
                self.end_headers()
                end = time.monotonic()+10
                while time.monotonic()<end and not station.stop.is_set():
                    self.wfile.write(('data: '+json.dumps(station.snapshot())+'\n\n').encode())
                    self.wfile.flush()
                    if station.stop.wait(1): break
                return
            if path in HMI_PATHS or path in {'/login','/vpn/status','/admin'}:
                surface = 'hmi' if path in HMI_PATHS else 'portal'
                status = 403 if path == '/admin' else 200
                station.log.write({'surface':surface,'http':{'method':self.command,'path':path},'status':status,'reason':'page'})
                with station.lock:
                    page = hmi.render(surface,path,station.snapshot(),IDENTITY,station.view,'hosted')
                self.answer(status,page,'text/html; charset=utf-8'); return
            self.answer(404,'Resource unavailable on this device.')
        except (ValueError,UnicodeError,TypeError): self.answer(400,'Request or fixed action rejected.')
        except TimeoutError: self.answer(408,'Timed out. No retry was performed.')
        except (OSError,ConnectionError):
            if not self.committed:
                try: self.answer(503,'Local station unavailable. Retry the local controls after recovery.')
                except OSError: pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8180)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535: parser.error('port out of range')
    server = CommunityServer(('127.0.0.1',args.port))
    print('Community synthetic station: '+server.origin+'/',flush=True)
    print('Loopback only. No model or Internet connection required.',flush=True)
    try: server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
