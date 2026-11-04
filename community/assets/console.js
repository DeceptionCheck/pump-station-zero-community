'use strict';
const $=id=>document.getElementById(id);
let busy=false;
function describe(row){
  const mb=row.modbus;
  if(mb){
    if(mb.exception_code)return 'Setting change refused. Exception '+mb.exception_code+'; no accepted write is claimed.';
    if(mb.function_code===5)return 'Pump command recorded: coil '+mb.address+', value '+mb.values.join(', ')+'.';
    if(mb.function_code===1)return 'Command bit read back from the controller.';
    return 'Device request FC '+mb.function_code+', address '+mb.address+'.';
  }
  if(row.http)return row.http.method+' '+row.http.path+' returned '+row.status+'.';
  return 'Fixed practice conditions readied.';
}
async function poll(){
  try{
    const reply=await fetch('/api/state',{cache:'no-store'});
    if(!reply.ok)throw Error('Station unavailable');
    const state=await reply.json();
    $('headline').textContent=state.headline;$('meaning').textContent=state.meaning;$('next-action').textContent=state.next_action;
    document.querySelector('.finding').classList.toggle('warning',state.station.pump2_display==='STOPPED (remote command)');
    $('freshness').className='';$('freshness').textContent='Current readings received '+new Date().toLocaleTimeString()+'.';
    const nodes=state.events.slice().reverse().map(row=>{const item=document.createElement('li');const stamp=document.createElement('time');stamp.textContent=new Date(row.ts).toLocaleTimeString();item.append(stamp,document.createTextNode(describe(row)));if(row.modbus&&[5,6,15,16].includes(row.modbus.function_code))item.className='event-warning';return item;});
    $('timeline').replaceChildren(...nodes);
    $('history-limit').textContent=state.events.length+' retained records. Earlier omitted records: '+state.dropped_events+'.';
    $('receipt').textContent=state.protocol_receipt?JSON.stringify(state.protocol_receipt,null,2):'No stop selected yet.';
    $('raw-events').textContent=JSON.stringify(state.events,null,2);
    $('local-port').textContent='This session owns loopback Modbus port '+state.technical.modbus_port+'. No external target can be selected.';
  }catch(error){$('freshness').className='stale';$('freshness').textContent='STALE: the station could not be reached. Last-known information stays visible. Retry the page when the local service returns.';}
}
document.querySelectorAll('[data-action]').forEach(button=>button.addEventListener('click',async()=>{
  if(busy)return;busy=true;document.querySelectorAll('[data-action]').forEach(node=>node.disabled=true);
  try{
    const action=button.dataset.action;
    const reply=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
    if(!reply.ok)throw Error('Action refused or unavailable. Ready the station or start a new session.');
    const result=await reply.json();
    if(action==='new'){location.assign('/');return;}
    if(action==='finish'){
      $('report-html').href='/report?id='+encodeURIComponent(result.encounter_id)+'&format=html';
      $('report-json').href='/report?id='+encodeURIComponent(result.encounter_id)+'&format=json';$('report-links').hidden=false;
      $('action-result').textContent='Evidence saved. Download the deterministic report using the links below.';
    }else $('action-result').textContent=action==='stop'?'Pump 2 stopped. The command and a separate readback are recorded.':action==='rejected'?'The unsafe setting was refused; station state stayed unchanged.':'The fixed practice station is ready, with its interlocks intact.';
    await poll();
  }catch(error){$('action-result').textContent=error.message;}
  finally{busy=false;document.querySelectorAll('[data-action]').forEach(node=>node.disabled=false);}
}));
fetch('/api/registers').then(reply=>reply.json()).then(rows=>{$('registers').replaceChildren(...rows.map(row=>{const tr=document.createElement('tr');for(const key of ['area','address','point','scale','access']){const td=document.createElement('td');td.textContent=String(row[key]);tr.append(td);}return tr;}));}).catch(()=>{});
poll();setInterval(poll,1000);
