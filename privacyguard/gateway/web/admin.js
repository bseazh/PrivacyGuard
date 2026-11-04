'use strict';
const $ = id => document.getElementById(id);
let csrf = '', snapshot = null, issued = null;
function notice(message, error=false) { $('notice').textContent=message; $('notice').className=error?'error':''; }
async function api(path, data) {
  const options={credentials:'same-origin',headers:{}};
  if(data!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-CSRF-Token':csrf};options.body=JSON.stringify(data);}
  const response=await fetch('/admin/api/'+path,options), body=await response.json();
  if(!response.ok){if(response.status===401) showLogin();throw new Error(body.error||'请求失败');}
  return body;
}
function clearKey(){issued=null;$('client-config').value='';$('key-result').hidden=true;$('probe-result').textContent='';}
function showLogin(){csrf='';snapshot=null;clearKey();$('console').hidden=true;$('login').hidden=false;$('logout').hidden=true;}
function button(label, handler){const b=document.createElement('button');b.textContent=label;b.onclick=()=>run(handler,b);return b;}
async function run(handler, element){if(element)element.disabled=true;try{await handler();}catch(e){notice(e.message,true);}finally{if(element)element.disabled=false;}}
function table(id, headers, rows){const root=$(id);root.replaceChildren();if(!rows.length){root.textContent='暂无记录';return;}const t=document.createElement('table'),head=t.createTHead().insertRow();for(const label of headers){const th=document.createElement('th');th.textContent=label;head.append(th);}const body=t.createTBody();for(const values of rows){const row=body.insertRow();for(const value of values){const cell=row.insertCell();if(value instanceof Node)cell.append(value);else cell.textContent=String(value??'');}}root.append(t);}
function names(items,id){return items.find(x=>x.id===id)?.name||id;}
function select(id,items){const el=$(id),previous=el.value;el.replaceChildren();for(const item of items){const op=document.createElement('option');op.value=item.id;op.textContent=item.name+(item.enabled?'':'（已禁用）');el.append(op);}if(items.some(x=>x.id===previous))el.value=previous;}
async function mutate(action,data){await api(action,data);await refresh();notice('操作已完成');}
async function refresh(){snapshot=await api('snapshot');$('console').hidden=false;$('login').hidden=true;$('logout').hidden=false;const s=snapshot;$('stats').replaceChildren();for(const [label,value] of [['用户',s.users.length],['已启用通道',s.channels.filter(x=>x.enabled).length],['有效 Key',s.keys.filter(x=>!x.revoked&&x.expires>Date.now()/1000).length],['最近阻断',s.events.filter(x=>x.action==='BLOCK').length]]){const box=document.createElement('div');box.className='stat';box.textContent=label;const n=document.createElement('strong');n.textContent=value;box.append(n);$('stats').append(box);}
  $('upstream').textContent='上游：'+s.upstream.upstream_url+' · 固定策略：'+s.policy;
  select('grant-user',s.users);select('grant-channel',s.channels);
  table('user-list',['用户','状态','操作'],s.users.map(u=>[u.name,u.enabled?'启用':'禁用',button(u.enabled?'禁用用户':'启用用户',()=>mutate('user_status',{id:u.id,enabled:!u.enabled}))]));
  table('channel-list',['通道','模型别名','状态','操作'],s.channels.map(c=>[c.name,JSON.parse(c.config).public_model,c.enabled?'已启用':'待启用 / 禁用',button(c.enabled?'禁用通道':'启用通道',()=>mutate('channel_status',{id:c.id,enabled:!c.enabled}))]));
  table('grant-list',['用户','获准通道','操作'],s.grants.map(g=>[names(s.users,g.user_id),names(s.channels,g.channel_id),button('撤销授权',()=>mutate('ungrant',g))]));
  table('key-list',['用户','通道','到期时间','状态','操作'],s.keys.map(k=>[names(s.users,k.user_id),names(s.channels,k.channel_id),new Date(k.expires*1000).toLocaleString(),k.revoked?'已撤销':k.expires<Date.now()/1000?'已到期':'未撤销',k.revoked?'—':button('撤销 Key',()=>mutate('revoke_key',{id:String(k.id)}))]));
  table('event-list',['时间','用户','通道','动作','原因','实体数'],s.events.map(e=>[new Date(e.created*1000).toLocaleTimeString(),names(s.users,e.user_id),names(s.channels,e.channel_id),e.action,e.code,e.entity_count]));
  table('change-list',['时间','操作','对象'],s.changes.map(e=>[new Date(e.created*1000).toLocaleTimeString(),e.action,e.target]));
}
$('login-form').onsubmit=e=>{e.preventDefault();run(async()=>{const password=$('password').value;$('password').value='';const result=await api('login',{password});csrf=result.csrf;await refresh();notice('已登录本机管理后台');},e.submitter);};
$('password-file').onchange=()=>run(async()=>{const f=$('password-file').files[0];if(!f)return;if(f.size>512)throw new Error('密码文件过大');$('password').value=(await f.text()).trim();$('password-file').value='';$('login-form').requestSubmit();});
$('logout').onclick=()=>run(async()=>{await api('logout',{});showLogin();notice('已退出登录');});
$('refresh').onclick=()=>run(refresh);
$('user-form').onsubmit=e=>{e.preventDefault();run(async()=>{await mutate('user_create',{name:$('user-name').value});$('user-name').value='';},e.submitter);};
$('channel-form').onsubmit=e=>{e.preventDefault();run(async()=>{await mutate('channel_create',{name:$('channel-name').value,model:$('channel-model').value});$('channel-name').value='';},e.submitter);};
function grant(){return {user_id:$('grant-user').value,channel_id:$('grant-channel').value};}
$('grant-form').onsubmit=e=>{e.preventDefault();run(()=>mutate('grant',grant()),e.submitter);};
$('issue-key').onclick=()=>run(async()=>{clearKey();const g=grant(),result=await api('issue_key',g),channel=snapshot.channels.find(c=>c.id===g.channel_id);issued={base_url:'http://127.0.0.1:8787/v1',model:JSON.parse(channel.config).public_model,api_key:result.api_key};$('client-config').value=JSON.stringify(issued,null,2);$('key-result').hidden=false;await refresh();notice('Key 已发放，24 小时后到期，请立即保存。');},$('issue-key'));
$('clear-key').onclick=clearKey;
$('download-key').onclick=()=>{if(!issued)return;const url=URL.createObjectURL(new Blob([JSON.stringify(issued,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='privacyguard-client.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('probe-key').onclick=()=>run(async()=>{if(!issued)return;$('probe-result').textContent='正在识别并调用本机模型，请稍候…';const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+issued.api_key},body:JSON.stringify({model:issued.model,stream:false,messages:[{role:'user',content:'请用一句话说明付款期限未约定的风险，不复述联系方式。虚构邮箱 alice@example.com，手机号13800138000。'}]})});const d=await r.json();$('probe-result').textContent=r.ok?'真实调用通过；脱敏实体 '+d.privacyguard.entity_count+' 项。':'已阻断：'+(d.error?.code||r.status);await refresh();},$('probe-key'));
(async()=>{try{const s=await api('session');csrf=s.csrf;await refresh();}catch(e){if(e.message!=='login_required')notice(e.message,true);}})();
