"""Basic deterministic report of this synthetic encounter, no analyst policy.

This deliberately does not import full-demo fact verification, mappings, prompt
packs or model code. A controlled command receipt is labeled as such; ordinary
protocol attempts are never turned into claims of real-equipment damage.
"""
import copy
from datetime import datetime, timezone
from html import escape
import json
import secrets


def build(session):
    events,dropped = session.log.snapshot()
    writes = [row for row in events if row.get('modbus',{}).get('function_code') in (5,6,15,16)]
    rejected = [row for row in writes if row['modbus'].get('exception_code')]
    stopped = bool(session.receipt and session.receipt['off_bit_confirmed'])
    return {'schema':'community-report-v1','encounter_id':secrets.token_hex(16),
        'generated_utc':datetime.now(timezone.utc).isoformat(),'source':'deterministic',
        'title':'Remote stop observed in the practice station' if stopped else 'Practice station interaction recorded',
        'summary':'The fixed command stopped the simulated Pump 2. A separate connection read its command bit back as off.'
                  if stopped else 'No controlled stop is selected for this run. Review the requests and replies in the timeline.',
        'why_it_matters':'Equipment commands can interrupt a process. A decoy lets a team inspect that interaction without connecting real equipment.',
        'next_action':'Check whether the activity was an approved test. Share the saved request and reply with the person responsible for the system.',
        'counts':{'retained_events':len(events),'write_attempts':len(writes),'rejected_writes':len(rejected)},
        'events':events,'station_snapshot':session.snapshot(),'protocol_receipt':copy.deepcopy(session.receipt),
        'limits':{'synthetic':True,'earlier_events_dropped':dropped,'no_real_equipment':True,
                  'no_actor_attribution':True,'report_not_sent_externally':True}}


def html(report):
    e = lambda value: escape(str(value))
    rows = ''.join('<tr><td>'+e(row['ts'])+'</td><td>'+e(row['surface'])+'</td><td>'+e(row.get('modbus') or row.get('http') or row['reason'])+'</td><td>'+e(row['reason'])+'</td></tr>' for row in report['events'])
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Community interaction report</title><style>body{font:17px/1.5 system-ui;color:#13253F;background:white;max-width:1000px;margin:24px auto;padding:16px}'
        'h2{color:#067A63}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #CBD8D4;text-align:left;overflow-wrap:anywhere}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}.limit{background:#FFF4DE;padding:16px}@media print{body{font-size:12px}}</style>'
        '<h1>'+e(report['title'])+'</h1><p>Fictional synthetic exercise. Source: deterministic rules.</p><p>'+e(report['summary'])+'</p>'
        '<h2>Why it matters</h2><p>'+e(report['why_it_matters'])+'</p><h2>What to check next</h2><p>'+e(report['next_action'])+'</p>'
        '<h2>Supporting timeline</h2><table><tr><th>UTC</th><th>Surface</th><th>Request</th><th>Recorded result</th></tr>'+rows+'</table>'
        '<details><summary>Technical receipt and snapshot</summary><pre>'+e(json.dumps({'receipt':report['protocol_receipt'],'station':report['station_snapshot']},indent=2))+'</pre></details>'
        '<p class="limit">No real equipment is connected. This report does not identify an actor, prove intent or send a notification. '
        'Earlier events omitted by the bounded history: '+e(report['limits']['earlier_events_dropped'])+'.</p>'
        '<footer>Encounter '+e(report['encounter_id'])+'; generated '+e(report['generated_utc'])+'</footer></html>')
