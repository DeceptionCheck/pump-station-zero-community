"""Inline HMI graphics and fixed copy, rendered only from trusted identity/state."""

from collections import deque
from datetime import datetime, timezone
from html import escape
import threading


STYLE = """
*{box-sizing:border-box}body{margin:0;background:#D4D4D4;color:#1F1F1F;
font:16px "Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}header,footer{padding:16px}
header{border-bottom:1px solid #9A9A9A}h1{font-size:22px;margin:4px 0}h2{font-size:20px}
.layout{max-width:1280px;margin:auto;padding:16px;display:grid;grid-template-columns:150px minmax(0,1fr);gap:16px}
nav a{display:flex;align-items:center;min-height:44px;padding:8px;color:inherit}main{min-width:0}
.panel{padding:16px;background:#E4E4E4;border:1px solid #9A9A9A;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.value{font-size:20px;font-variant-numeric:tabular-nums}
.muted,.unit{color:#5C5C5C}.unit{font-size:14px}.bar{width:100%;height:48px}.process{width:100%;height:auto}
.banner{font-size:18px;font-weight:bold;margin:0 16px;padding:12px;background:#E4E4E4;border:1px solid #9A9A9A}
.P1,.remote,.fault{color:#C00000;font-weight:bold}.P2{color:#E39B00;font-weight:bold}.P3{color:#1F5AA6;font-weight:bold}
.chip.P1{background:#C00000;color:white}.chip.P2{background:#E39B00;color:black}.chip.P3{background:#1F5AA6;color:white}
.chip{padding:4px 8px}.acked{background:#E4E4E4!important;color:inherit!important;border:2px solid currentColor}
.new{animation:pulse .4s 1}@keyframes pulse{50%{opacity:.45}}.running{fill:#FFFFFF}.stopped{fill:#7A7A7A}
.pump-state.remote{font-size:32px;line-height:1.2}@media(prefers-reduced-motion:reduce){.new{animation:none}}
table{width:100%;border-collapse:collapse}th,td{padding:10px;text-align:left;border-bottom:1px solid #9A9A9A}
button,input{min-height:44px;font:inherit;padding:8px}label{display:block;margin:12px 0}button{background:#E4E4E4;border:1px solid #9A9A9A}
.portal{max-width:450px;margin:8vh auto;padding:24px}.portal input{width:100%}.demo{padding:12px;border:2px solid #9A9A9A}
svg text{fill:#1F1F1F;font-family:inherit}footer{font-size:14px;color:#5C5C5C}@media(max-width:700px){.layout{grid-template-columns:1fr}nav{display:flex;flex-wrap:wrap}.grid{grid-template-columns:1fr}}
"""


class ViewState:
    """Keep at most two hours of sampled readings and observed pump edges."""

    def __init__(self):
        self.history = deque(maxlen=7201)
        self.edges = {1: {}, 2: {}}
        self.remote_indications = {}
        self._lock = threading.RLock()

    def observe(self, snapshot):
        with self._lock:
            # HMI annunciation only. Do not insert a new alarm into StationSim
            # or infer that an arbitrary historical request caused this state.
            for pump in (1, 2):
                active = not snapshot[f'pump{pump}_running'] and snapshot[f'pump{pump}_display']=='STOPPED (remote command)'
                previous = self.remote_indications.get(pump)
                if active and (previous is None or not previous['active']):
                    self.remote_indications[pump] = {'tag':f'pump{pump}_remote_stop',
                        'description':f'PUMP {pump} STOPPED, remote command','priority':'P1',
                        'raised_at':snapshot['sim_time'],'acked':False,'active':True,
                        'origin':'hmi_state_indication'}
                elif previous is not None:
                    previous['active'] = bool(active)
            previous = self.history[-1] if self.history else None
            if previous and snapshot["sim_time"] == previous["sim_time"]:
                return
            for pump in (1, 2):
                point = f"pump{pump}_running"
                if previous and snapshot[point] != previous[point]:
                    self.edges[pump]["start" if snapshot[point] else "stop"] = snapshot["sim_time"]
            self.history.append(snapshot)
            while self.history and snapshot["sim_time"] - self.history[0]["sim_time"] > 7200:
                self.history.popleft()

    def decorate(self, snapshot):
        """Copy active display indications, keeping PLC alarms and state intact.

        Time means first HMI observation of the remote-stop state. The decoy's
        rejected acknowledgement form does not acknowledge these indications.
        """
        with self._lock:
            return dict(snapshot,remote_indications=[dict(row) for row in self.remote_indications.values() if row['active']])

    def trend(self, point, maximum, now):
        with self._lock:
            points = " ".join(f"{max(0, (s['sim_time'] - now + 7200) / 7200 * 800):.2f},{140 - s[point] / maximum * 120:.2f}" for s in self.history)
        return (f'<svg viewBox="0 0 820 180" class="process" role="img" aria-label="{escape(point)} two-hour trend">'
                f'<path d="M0 140 H800" stroke="#9A9A9A"/><polyline points="{points}" fill="none" stroke="#3A3A3A" stroke-width="2"/>'
                f'<text x="0" y="170">{clock(now - 7200)}</text><text x="750" y="170">{clock(now)}</text></svg>')


def clock(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%H:%M:%S")


def form(action, title):
    return (f'<h2>{title}</h2><form method="post" action="{action}"><label>Username '
            '<input name="username" maxlength="64" autocomplete="username"></label><label>Password '
            '<input type="password" name="password" autocomplete="current-password"></label><button>Sign in</button></form>')


def alarm_banner(snapshot):
    active = sorted((a for a in snapshot["alarms"]+snapshot.get('remote_indications',[]) if a["active"]), key=lambda a: a["raised_at"], reverse=True)
    rows = []
    for alarm in active[:3]:
        rows.append(f'<div class="{alarm["priority"]}" data-alarm="{alarm["tag"]}">{clock(alarm["raised_at"])} '
                    f'{alarm["tag"]} {alarm["description"]} <span class="chip {alarm["priority"]} {"acked" if alarm["acked"] else ""}">'
                    f'{alarm["priority"]}</span> {"ACK" if alarm["acked"] else "UNACK"}</div>')
    if len(active) > 3:
        rows.append(f"<div>{len(active) - 3} more alarms</div>")
    if snapshot["remote_command_active"]:
        rows.append('<div class="remote">Remote command active</div>')
    return "".join(rows) or "No active alarms"


def bar(snapshot, point, label, unit, maximum, normal, ticks=(), priority="P2"):
    """Compact labelled gauge row, actual reading and explicit scale/unit."""
    value = snapshot[point]
    markers = "".join(f'<line x1="{t / maximum * 500}" y1="5" x2="{t / maximum * 500}" y2="35" stroke="#3A3A3A"/>' for t in ticks)
    return (f'<div class="gauge-row"><span>{label}</span><svg class="bar" viewBox="0 0 500 40" role="img" aria-label="{label}, scale 0 to {maximum} {unit}">'
            f'<rect y="10" width="500" height="20" fill="#ECECEC"/><rect x="{normal[0] / maximum * 500}" y="10" '
            f'width="{(normal[1] - normal[0]) / maximum * 500}" height="20" fill="#BDBDBD"/>{markers}'
            f'<path data-pointer="{point}" d="M{value / maximum * 500} 5 v30" stroke="#1F1F1F" stroke-width="3"/></svg>'
            f'<span><strong data-value="{point}">{value:.2f}</strong> {unit}</span><span class="range">0 to {maximum} {unit}</span></div>')


def control_boundary(snapshot, number):
    """Describe active simulator interlocks without inferring request causation."""
    if snapshot[f"pump{number}_fault"]:
        return "Fault interlock; start requests may be overridden"
    if snapshot["suction_trip_latched"]:
        return "Suction trip latched; start requests overridden"
    if snapshot["tank_level_ft"] >= min(snapshot["sp_tank_stop_ft"], snapshot["sp_high_tank_alarm_ft"]):
        return "Tank hard stop; start requests overridden"
    if snapshot[f"pump{number}_cmd"] and not snapshot[f"pump{number}_running"]:
        return "Requested ON, not running; further cause unavailable"
    return "Current equipment state shown; remote requests remain subject to interlocks"


def pump(snapshot, number, view):
    state = snapshot[f"pump{number}_display"]
    bad = "remote" if "remote command" in state else "fault" if state == "FAULT" else ""
    running = snapshot[f"pump{number}_running"]
    times = view.edges[number]
    return (f'<div class="panel"><h2>P-{number} (Pump {number}) <span class="muted">{"LEAD" if snapshot["lead_pump"] == number else ""}</span></h2>'
            f'<svg viewBox="0 0 200 100" width="200" role="img" aria-label="Pump {number}"><path data-flow="pump{number}" d="M0 50 H200" stroke="{"#5A5A5A" if running else "#8C8C8C"}" stroke-width="8"/>'
            f'<circle data-symbol="pump{number}" cx="75" cy="50" r="32" fill="{"#FFFFFF" if running else "#7A7A7A"}" '
            f'stroke="{"#C00000" if bad else "#3A3A3A"}" stroke-width="3"/><path d="M135 35 L155 50 L135 65 Z" fill="#E4E4E4" stroke="#3A3A3A"/></svg>'
            f'<p data-state="pump{number}" class="value pump-state {bad}">{state}</p><p>Run command: <span data-command="pump{number}">{snapshot[f"pump{number}_cmd"]}</span></p>'
            f'<p>Run hours: <span data-value="pump{number}_run_hours">{snapshot[f"pump{number}_run_hours"]:.1f}</span> h</p>'
            f'<p>Control boundary: <span data-boundary="pump{number}">{control_boundary(snapshot, number)}</span></p><p>Fault: {snapshot[f"pump{number}_fault"]}</p><p>Last start: {clock(times["start"]) if "start" in times else ""}</p>'
            f'<p>Last stop: {clock(times["stop"]) if "stop" in times else ""}</p><p>Command source: <span data-command-source="pump{number}">{"remote command" if bad == "remote" else "local"}</span></p></div>')


def tank(snapshot):
    level = snapshot["tank_level_ft"]
    ticks = "".join(f'<path d="M140 {190 - snapshot[key] * 4} h30" stroke="#3A3A3A"/><text x="180" y="{195 - snapshot[key] * 4}">{key.removeprefix("sp_")} {snapshot[key]:.1f} ft</text>'
                    for key in ("sp_tank_start_ft", "sp_tank_stop_ft", "sp_low_tank_alarm_ft", "sp_high_tank_alarm_ft"))
    return (f'<div class="panel"><h2>Tank level</h2><svg viewBox="0 0 650 260" class="process" role="img" aria-label="Tank level">'
            '<path d="M40 190 V20 H140 V190 Z M60 190 V250 M120 190 V250" fill="#E4E4E4" stroke="#3A3A3A" stroke-width="3"/>'
            f'<rect data-tank="fill" x="43" y="{190 - level * 4}" width="94" height="{level * 4}" fill="#BDBDBD"/>{ticks}</svg>'
            f'<span data-value="tank_level_ft" class="value">{level:.1f}</span> <span class="unit">ft</span></div>')


LIVE_SCRIPT = r"""<script>
const ranges={suction_psi:100,discharge_psi:120,flow_gpm:2000,tank_level_ft:40,chlorine_mg_l:3};
let seen=new Set(Array.from(document.querySelectorAll('[data-alarm]'),x=>x.dataset.alarm));
const feed=new EventSource('/events');
feed.onmessage=event=>{const s=JSON.parse(event.data);
document.querySelectorAll('[data-value]').forEach(el=>{const key=el.dataset.value,v=s[key];if(typeof v==='number')el.textContent=key==='lead_pump'?'P-'+Math.round(v):v.toFixed(key==='chlorine_mg_l'?2:key.includes('hours')?1:1);
const tags={suction_psi:['low_suction','low_suction_trip'],discharge_psi:['high_discharge'],tank_level_ft:['low_tank','high_tank']};
const alarms=s.alarms.filter(a=>a.active&&(tags[key]||[]).includes(a.tag));el.classList.toggle('P1',alarms.some(a=>a.priority==='P1'));el.classList.toggle('P2',alarms.some(a=>a.priority==='P2'))});
document.querySelectorAll('[data-pointer]').forEach(el=>el.setAttribute('d','M'+(s[el.dataset.pointer]/ranges[el.dataset.pointer]*500)+' 5 v30'));
for(const n of [1,2]){document.querySelectorAll('[data-state="pump'+n+'"]').forEach(el=>{el.textContent=s['pump'+n+'_display'];el.classList.toggle('remote',el.textContent.includes('remote command'));el.classList.toggle('fault',s['pump'+n+'_fault'])});
document.querySelectorAll('[data-flow="pump'+n+'"]').forEach(el=>el.setAttribute('stroke',s['pump'+n+'_running']?'#5A5A5A':'#8C8C8C'));
document.querySelectorAll('[data-command-source="pump'+n+'"]').forEach(el=>el.textContent=s['pump'+n+'_display'].includes('remote command')?'remote command':'local');
document.querySelectorAll('[data-symbol="pump'+n+'"]').forEach(el=>{el.setAttribute('fill',s['pump'+n+'_running']?'#FFFFFF':'#7A7A7A');el.setAttribute('stroke',s['pump'+n+'_display'].includes('remote command')||s['pump'+n+'_fault']?'#C00000':'#3A3A3A')})}
document.querySelectorAll('[data-tank]').forEach(el=>{const compact=el.dataset.tankCompact==='true',scale=compact?5:4;el.setAttribute('y',(compact?232:190)-s.tank_level_ft*scale);el.setAttribute('height',s.tank_level_ft*scale)});
const banner=document.getElementById('alarm-banner');if(banner){banner.replaceChildren();const alarms=[...s.alarms,...(s.remote_indications||[])].filter(a=>a.active).sort((a,b)=>b.raised_at-a.raised_at);
for(const a of alarms.slice(0,3)){const row=document.createElement('div');row.className=a.priority+(seen.has(a.tag)?'':' new');row.dataset.alarm=a.tag;row.textContent=new Date(a.raised_at*1000).toISOString().slice(11,19)+' '+a.tag+' '+a.description+' ';const chip=document.createElement('span');chip.className='chip '+a.priority+(a.acked?' acked':'');chip.textContent=a.priority;row.append(chip,document.createTextNode(' '+(a.acked?'ACK':'UNACK')));banner.append(row)}
if(alarms.length>3){const row=document.createElement('div');row.textContent=(alarms.length-3)+' more alarms';banner.append(row)}
if(s.remote_command_active){const row=document.createElement('div');row.className='remote';row.textContent='Remote command active';banner.append(row)}
if(!banner.childNodes.length)banner.textContent='No active alarms';seen=new Set(alarms.map(a=>a.tag))}
document.querySelectorAll('[data-command]').forEach(el=>el.textContent=s[el.dataset.command+'_cmd']?'ON requested':'OFF requested');
document.querySelectorAll('[data-boundary]').forEach(el=>{const n=el.dataset.boundary==='lead'?s.lead_pump:Number(el.dataset.boundary.slice(-1));el.textContent=s['pump'+n+'_fault']?'Fault interlock; start requests may be overridden':s.suction_trip_latched?'Suction trip latched; start requests overridden':s.tank_level_ft>=Math.min(s.sp_tank_stop_ft,s.sp_high_tank_alarm_ft)?'Tank hard stop; start requests overridden':s['pump'+n+'_cmd']&&!s['pump'+n+'_running']?'Requested ON, not running; further cause unavailable':'Current equipment state shown; remote requests remain subject to interlocks'});
document.querySelectorAll('[data-remote-request]').forEach(el=>el.textContent=s.remote_command_active?'Active, subject to interlocks':'None active');
document.querySelectorAll('[data-lead]').forEach(el=>el.textContent=Number(el.dataset.lead)===s.lead_pump?'LEAD':'');
const fresh=document.getElementById('hmi-freshness');if(fresh){fresh.textContent='Current process readings';fresh.dataset.last=String(Date.now())}
const clock=document.getElementById('clock');if(clock)clock.textContent=new Date(s.sim_time*1000).toISOString().replace('T',' ').slice(0,19);
};
feed.onerror=()=>{const fresh=document.getElementById('hmi-freshness');if(fresh)fresh.textContent='STALE, last-known readings';};
setInterval(()=>{const f=document.getElementById('hmi-freshness');if(f&&Date.now()-Number(f.dataset.last||0)>2500)f.textContent='STALE, last-known readings'},500);
</script>"""


def state_table(snapshot):
    return (f'<section class="panel state-table"><table><thead><tr><th>Lead pump</th><th>P-1 run hours</th><th>P-2 run hours</th><th>Chlorine residual</th><th>Remote request</th></tr></thead>'
            f'<tbody><tr><td data-value="lead_pump">P-{int(snapshot["lead_pump"])}</td><td><span data-value="pump1_run_hours">{snapshot["pump1_run_hours"]:.1f}</span> h</td>'
            f'<td><span data-value="pump2_run_hours">{snapshot["pump2_run_hours"]:.1f}</span> h</td><td><span data-value="chlorine_mg_l">{snapshot["chlorine_mg_l"]:.2f}</span> mg/L</td>'
            f'<td><span data-remote-request>{"Active, subject to interlocks" if snapshot["remote_command_active"] else "None active"}</span><br><span data-boundary="lead">{control_boundary(snapshot, int(snapshot["lead_pump"]))}</span></td></tr></tbody></table></section>')


def overview(snapshot):
    """One connected parallel-pump mimic; no decorative flow animation."""
    shapes = []
    for n,y in ((1,75),(2,205)):
        display = escape(snapshot[f"pump{n}_display"])
        bad = snapshot[f"pump{n}_fault"] or "remote command" in snapshot[f"pump{n}_display"]
        shapes.append(f'<path data-flow="pump{n}" d="M190 {y} H650" stroke="{"#5A5A5A" if snapshot[f"pump{n}_running"] else "#8C8C8C"}" stroke-width="6"/>'
                      f'<circle data-symbol="pump{n}" cx="350" cy="{y}" r="28" fill="{"#FFFFFF" if snapshot[f"pump{n}_running"] else "#7A7A7A"}" stroke="{"#C00000" if bad else "#3A3A3A"}" stroke-width="3"/>'
                      f'<text x="336" y="{y+5}">P-{n}</text><text data-lead="{n}" x="330" y="{y-40}">{"LEAD" if snapshot["lead_pump"] == n else ""}</text>'
                      f'<text data-state="pump{n}" x="250" y="{y+47}">{display}</text><path d="M490 {y-13} L510 {y} L490 {y+13} Z" fill="#D4D4D4" stroke="#3A3A3A" stroke-width="2"/>')
    return ('<section class="panel mimic"><svg viewBox="0 0 960 285" class="process" role="img" aria-label="Station process overview, parallel P-1 and P-2 between suction and discharge headers and tank">'
            '<path d="M20 140 H190 M190 75 V205 M650 75 V205 M650 140 H800" fill="none" stroke="#737373" stroke-width="6"/>'
            '<text x="20" y="120">Suction header</text><text x="665" y="120">Discharge</text>'+"".join(shapes)+
            f'<path d="M800 235 V15 H910 V235 Z" fill="#E4E4E4" stroke="#3A3A3A" stroke-width="3"/>'
            f'<rect data-tank="fill" data-tank-compact="true" x="803" y="{232-snapshot["tank_level_ft"]*5}" width="104" height="{snapshot["tank_level_ft"]*5}" fill="#BDBDBD"/>'
            f'<text x="800" y="263">Tank <tspan data-value="tank_level_ft">{snapshot["tank_level_ft"]:.1f}</tspan> ft</text></svg></section>')


def render(surface, path, snapshot, identity, view, mode="lab"):
    """Return a complete local-only HTML page, with escaped identity values."""
    hmi = {key: escape(str(value)) for key, value in identity["hmi"].items() if isinstance(value, str)}
    demo = ('<div class="demo">Fictional pump station. Never connected to real equipment. Requests are logged for the demo.</div>' if mode == "hosted" else "")
    if surface == "portal":
        product = escape(identity["portal"]["product"] + " " + identity["portal"]["version"])
        content = ('<h2>VPN status</h2><table><tr><th>Tunnel state</th><td>Disconnected</td></tr>'
                   f'<tr><th>Uptime</th><td>{int(snapshot["sim_time"] - view.history[0]["sim_time"]) if view.history else 0} s</td></tr>'
                   f'<tr><th>Last sync</th><td>{clock(snapshot["sim_time"])}</td></tr></table>' if path == "/vpn/status" else
                   "Access denied." if path == "/admin" else form("/login", "Sign in"))
        return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{product}</title><style>{STYLE}</style></head><body class="portal-body"><header class="portal-header">{product}</header>{demo}<main class="portal panel">{content}</main><footer class="portal-footer">{product}</footer></body></html>'
    title = path.strip("/").title() or "Overview"
    if path in {"/", "/overview"}:
        content = overview(snapshot) + '<section class="panel gauge-panel" aria-label="Station readings">'
        for point, label, unit, maximum, normal, ticks, priority in (
            ("suction_psi", "Suction pressure", "psi", 100, (45, 55), (20, 25), "P1" if snapshot["suction_psi"] < 20 else "P2"),
            ("discharge_psi", "Discharge pressure", "psi", 120, (70, 85), (95,), "P1"),
            ("flow_gpm", "Flow", "gpm", 2000, (0, 1500), (), "P2"),
            ("tank_level_ft", "Tank level", "ft", 40, (28, 36), (15, 38), "P2"),
            ("chlorine_mg_l", "Chlorine residual", "mg/L", 3, (.8, 1.5), (), "P2")):
            content += bar(snapshot, point, label, unit, maximum, normal, ticks, priority)
        content += '</section>' + state_table(snapshot)
    elif path == "/pumps":
        content = '<div class="grid">' + pump(snapshot, 1, view) + pump(snapshot, 2, view) + '</div>'
    elif path == "/tank":
        content = tank(snapshot) + view.trend("tank_level_ft", 40, snapshot["sim_time"])
    elif path == "/trends":
        content = "".join(f'<div class="panel"><h2>{label}</h2>{view.trend(point, maximum, snapshot["sim_time"])}</div>' for point, label, maximum in (
            ("suction_psi", "Suction pressure, psi", 100), ("discharge_psi", "Discharge pressure, psi", 120),
            ("flow_gpm", "Flow, gpm", 2000), ("tank_level_ft", "Tank level, ft", 40)))
    elif path == "/alarms":
        rows = "".join(f'<tr><td>{clock(a["raised_at"])}</td><td>{a["tag"]}</td><td>{a["description"]}</td><td>{a["priority"]}</td><td>{"acknowledged" if a["acked"] and a["active"] else "active" if a["active"] else "cleared"}</td></tr>'
                       for a in sorted(snapshot["alarms"], key=lambda a: a["raised_at"], reverse=True))
        content = f'<table><tr><th>Time</th><th>Tag</th><th>Description</th><th>Priority</th><th>State</th></tr>{rows}</table><form method="post" action="/acknowledge"><button>Acknowledge</button></form>'
    elif path == "/setup":
        content = form("/setup", "Setup access")
    else:
        content = (f'<div class="panel"><p>Device: {escape(identity["station"]["display"])}</p><p>Model: {hmi["model"]}</p>'
                   f'<p>Firmware: {hmi["firmware"]}</p><p>Serial: {hmi["serial"]}</p><p>Support: {hmi["vendor"]}</p></div>')
    nav = "".join(f'<a href="/{name.lower()}" class="{"active" if path == "/" and name == "Overview" or path == "/"+name.lower() else ""}" aria-current="{"page" if path == "/" and name == "Overview" or path == "/"+name.lower() else "false"}">{name}</a>' for name in ("Overview", "Pumps", "Tank", "Alarms", "Trends", "Setup", "About"))
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{STYLE}</style></head><body>{demo}'
            f'<header><span>{escape(identity["utility"]["name"])}</span><h1>{escape(identity["station"]["display"])}</h1><strong>{title}</strong> '
            f'<time id="clock">{datetime.fromtimestamp(snapshot["sim_time"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}</time> UTC <span class="muted">{"Remote request active" if snapshot["remote_command_active"] else "Local control"}</span></header>'
            '<div id="hmi-freshness" class="freshness">Current process readings</div>'
            f'<div id="alarm-banner" class="banner">{alarm_banner(snapshot)}</div><div class="layout"><nav>{nav}</nav><main>{content}</main></div>'
            f'<footer>{hmi["vendor"]} {hmi["model"]} {hmi["firmware"]}</footer>{LIVE_SCRIPT}</body></html>')

# Compact industrial layout, isolated from operator CSS and assets.
STYLE += """
header{display:flex;align-items:center;gap:16px;padding:10px 16px;flex-wrap:wrap}header h1{font-size:18px;margin:0}header time{margin-left:auto}.freshness{padding:3px 16px;font-size:14px;color:#5C5C5C}.banner{padding:8px 12px;margin:0 16px;font-size:16px}.layout{max-width:1366px;padding:12px 16px;gap:16px;grid-template-columns:140px minmax(0,1fr)}nav a{border:1px solid #9A9A9A;margin-bottom:8px;background:#E4E4E4;text-decoration:none}nav a.active{font-weight:700;border-left:4px solid #3A3A3A;background:#ECECEC}.panel{padding:12px;margin-bottom:12px}.mimic .process{display:block;max-height:290px}.gauge-row{display:grid;grid-template-columns:165px minmax(100px,1fr) 135px 110px;align-items:center;gap:12px;min-height:34px}.gauge-row .bar{height:28px}.range{font-size:13px;color:#5C5C5C}.state-table th,.state-table td{padding:8px;font-size:15px}.portal-body{background:#EEEEEE}.portal-header{min-height:56px;border-bottom:1px solid #BDBDBD;background:#E4E4E4}.portal{max-width:420px;margin:48px auto;padding:28px;background:#F4F4F4}.portal h2{margin:0 0 24px}.portal label{margin:16px 0}.portal input{display:block;margin-top:6px}.portal button{width:100%;margin-top:8px}.portal-footer{text-align:center;font-size:14px}button,input{max-width:100%}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #1F5AA6;outline-offset:2px}@media(max-width:700px){header{gap:8px}header time{margin-left:0}.layout{grid-template-columns:1fr;padding:8px}nav{gap:8px}nav a{margin:0}.gauge-row{grid-template-columns:1fr 1fr}.gauge-row .bar{grid-column:1/-1;grid-row:2}.gauge-row .range{grid-column:1/-1}.state-table{overflow:auto}.mimic .process{min-height:180px}.portal{margin:24px 12px}.portal-header{font-size:16px}}
"""

STYLE += ".P1,.remote,.fault{color:#9F1C1C}.P2{color:#805000}"
