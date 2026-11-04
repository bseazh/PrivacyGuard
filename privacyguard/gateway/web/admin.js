'use strict';
const $ = id => document.getElementById(id);
let csrf = '', snapshot = null, issued = null, workflow = null;
function notice(message, error=false) { $('notice').textContent=message; $('notice').className=error?'error':''; }
async function api(path, data) {
  const options={credentials:'same-origin',headers:{}};
  if(data!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-CSRF-Token':csrf};options.body=JSON.stringify(data);}
  const response=await fetch('/admin/api/'+path,options), body=await response.json();
  if(!response.ok){if(response.status===401) showLogin();throw new Error(body.error||'请求失败');}
  return body;
}
function clearKey(){issued=null;$('client-config').value='';$('key-result').hidden=true;$('probe-result').textContent='';$('probe-answer').textContent='';}
function showLogin(){csrf='';snapshot=null;clearKey();$('trace-detail').hidden=true;$('trace-spans').replaceChildren();$('console').hidden=true;$('login').hidden=false;$('logout').hidden=true;}
function button(label, handler){const b=document.createElement('button');b.textContent=label;b.onclick=()=>run(handler,b);return b;}
async function run(handler, element){if(element)element.disabled=true;try{await handler();}catch(e){notice(e.message,true);}finally{if(element)element.disabled=false;}}
function table(id, headers, rows){const root=$(id);root.replaceChildren();if(!rows.length){root.textContent='暂无记录';return;}const t=document.createElement('table'),head=t.createTHead().insertRow();for(const label of headers){const th=document.createElement('th');th.textContent=label;head.append(th);}const body=t.createTBody();for(const values of rows){const row=body.insertRow();for(const value of values){const cell=row.insertCell();if(value instanceof Node)cell.append(value);else cell.textContent=String(value??'');}}root.append(t);}
function names(items,id){return items.find(x=>x.id===id)?.name||id;}
function select(id,items){const el=$(id),previous=el.value;el.replaceChildren();for(const item of items){const op=document.createElement('option');op.value=item.id;op.textContent=item.name+(item.enabled?'':'（已禁用）');el.append(op);}if(items.some(x=>x.id===previous))el.value=previous;}
async function mutate(action,data){await api(action,data);await refresh();notice('操作已完成');}
async function refresh(){snapshot=await api('snapshot');$('console').hidden=false;$('login').hidden=true;$('logout').hidden=false;const s=snapshot;$('stats').replaceChildren();for(const [label,value] of [['用户',s.users.length],['已启用通道',s.channels.filter(x=>x.enabled).length],['有效 Key',s.keys.filter(x=>!x.revoked&&x.expires>Date.now()/1000).length],['最近阻断',s.events.filter(x=>x.action==='BLOCK').length]]){const box=document.createElement('div');box.className='stat';box.textContent=label;const n=document.createElement('strong');n.textContent=value;box.append(n);$('stats').append(box);}
  $('upstream').textContent='上游：'+s.upstream.upstream_url+' · 内置匹配器：'+s.policy;
  select('grant-user',s.users);select('grant-channel',s.channels);
  table('user-list',['用户','状态','操作'],s.users.map(u=>[u.name,u.enabled?'启用':'禁用',button(u.enabled?'禁用用户':'启用用户',()=>mutate('user_status',{id:u.id,enabled:!u.enabled}))]));
  table('channel-list',['通道','模型别名','状态','操作'],s.channels.map(c=>[c.name,JSON.parse(c.config).public_model,c.enabled?'已启用':'待启用 / 禁用',button(c.enabled?'禁用通道':'启用通道',()=>mutate('channel_status',{id:c.id,enabled:!c.enabled}))]));
  table('grant-list',['用户','获准通道','操作'],s.grants.map(g=>[names(s.users,g.user_id),names(s.channels,g.channel_id),button('撤销授权',()=>mutate('ungrant',g))]));
  table('key-list',['用户','通道','到期时间','状态','操作'],s.keys.map(k=>[names(s.users,k.user_id),names(s.channels,k.channel_id),new Date(k.expires*1000).toLocaleString(),k.revoked?'已撤销':k.expires<Date.now()/1000?'已到期':'未撤销',k.revoked?'—':button('撤销 Key',()=>mutate('revoke_key',{id:String(k.id)}))]));
  table('event-list',['时间','用户','通道','动作','原因','实体数','详情'],s.events.map(e=>[new Date(e.created*1000).toLocaleTimeString(),names(s.users,e.user_id),names(s.channels,e.channel_id),e.action,e.code,e.entity_count,button('Trace',()=>showTrace(e.request_id))]));
  table('change-list',['时间','操作','对象'],s.changes.map(e=>[new Date(e.created*1000).toLocaleTimeString(),e.action,e.target]));
  const policies=await api('policies');
  table('policy-list',['规则 / 类型','实际匹配表达式','校验与边界','请求 / 回答','占位符'],policies.rules.map(p=>[p.id+' / '+p.type,p.expression,p.validation,p.request+' / '+p.response,p.replacement]));
  await refreshWorkflow();
}
async function refreshWorkflow(){
  workflow=await api('policy-workflow');
  const draft=workflow.draft;
  table('draft-editor',['类型','请求动作','回答动作'],['default',...workflow.kinds].map(kind=>{
    const controls=['request','response'].map(direction=>{
      const control=document.createElement('select');control.dataset.kind=kind;control.dataset.direction=direction;
      for(const value of kind==='default'?['REDACT','BLOCK']:['inherit','REDACT','BLOCK']){
        const option=document.createElement('option');option.value=value;option.textContent=value==='inherit'?'使用默认':value;control.append(option);
      }
      control.value=draft.content[direction][kind]||'inherit';
      control.onchange=()=>{$('draft-status').textContent='尚未保存；保存后必须重新测试';$('draft-check').disabled=true;$('draft-publish').disabled=true;};
      return control;
    });return [kind,...controls];
  }));
  const tested=draft.test?.passed&&draft.test.suite===workflow.suite;
  $('draft-status').textContent='草稿修订 '+draft.generation+' · '+draft.hash.slice(0,12)+' · '+(tested?'测试通过，可发布':'尚未通过当前测试');
  $('draft-check').disabled=false;$('draft-publish').disabled=!tested;
  table('draft-tests',['测试','断言'],(draft.test?.results||[]).map(r=>[r.name,r.passed?'通过':'失败']));
  select('policy-channel',snapshot.channels);
  const versions=$('policy-version'),previous=versions.value;versions.replaceChildren();
  for(const version of workflow.versions){const option=document.createElement('option');option.value=version.id;option.textContent=(version.baseline?'基线 ':'发布版本 ')+version.id.slice(0,19);versions.append(option);}
  if(workflow.versions.some(v=>v.id===previous))versions.value=previous;
  showPolicyDiff();
  table('policy-history',['通道','原版本 → 新版本','时间'],workflow.history.map(h=>[names(snapshot.channels,h.channel_id),h.previous.slice(0,19)+' → '+h.version.slice(0,19),new Date(h.created*1000).toLocaleString()]));
}
function showPolicyDiff(){
  if(!workflow)return;
  const binding=workflow.bindings.find(b=>b.channel_id===$('policy-channel').value);
  const before=workflow.versions.find(v=>v.id===binding?.version),after=workflow.versions.find(v=>v.id===$('policy-version').value);
  $('policy-current').textContent='当前通道版本：'+(binding?.version||'未知')+'；只影响此通道的新请求。';
  const rows=[];
  if(before&&after)for(const direction of ['request','response'])for(const kind of ['default',...workflow.kinds]){
    const old=before.content[direction][kind]||before.content[direction].default,newValue=after.content[direction][kind]||after.content[direction].default;
    if(old!==newValue)rows.push([direction,kind,old,newValue]);
  }
  table('policy-diff',['方向','类型','当前动作','目标动作'],rows);
  $('policy-activate').disabled=!before||!after||before.id===after.id;
}
$('policy-channel').onchange=showPolicyDiff;$('policy-version').onchange=showPolicyDiff;
$('draft-save').onclick=()=>run(async()=>{
  const content={request:{},response:{}};
  for(const s of $('draft-editor').querySelectorAll('select'))if(s.value!=='inherit')content[s.dataset.direction][s.dataset.kind]=s.value;
  await api('policy-save',{generation:workflow.draft.generation,content});await refreshWorkflow();notice('草稿已保存；线上通道未改变，请重新测试。');
},$('draft-save'));
$('draft-check').onclick=()=>run(async()=>{const result=await api('policy-check',{generation:workflow.draft.generation});await refreshWorkflow();notice(result.passed?'草稿测试全部通过，可发布。':'测试失败，禁止发布。',!result.passed);},$('draft-check'));
$('draft-publish').onclick=()=>run(async()=>{const result=await api('policy-publish',{generation:workflow.draft.generation});await refreshWorkflow();$('policy-version').value=result.version;showPolicyDiff();notice('已发布不可变版本；请核对目标通道和差异后单独启用。');},$('draft-publish'));
$('policy-activate').onclick=()=>run(async()=>{const channel=$('policy-channel').value,version=$('policy-version').value,expected=workflow.bindings.find(b=>b.channel_id===channel).version;await api('policy-activate',{channel,version,expected});await refresh();notice('通道版本已切换，请发起测试请求并核对 Trace。');},$('policy-activate'));
const stageLabels={'authorization':'身份与 Channel 权限','request.validation':'请求结构校验','request.policy':'请求规则、假名化与复检','upstream.authorization':'发送前权限复核','upstream.call':'上游模型调用','response.policy':'回答敏感信息检查','response.release':'返回前授权与审计'};
async function showTrace(id){const t=await api('trace?id='+encodeURIComponent(id));$('trace-detail').hidden=false;$('trace-summary').textContent='请求 '+id+' · '+t.event.action+' / '+t.event.code+' · '+t.event.revision+' · 正文未留存';table('trace-spans',['步骤','状态','耗时(ms)','结构与处理详情'],t.spans.map(s=>{const pre=document.createElement('pre');pre.textContent=JSON.stringify(s.details,null,2);return [stageLabels[s.stage]||s.stage,s.status,s.duration_ms??'进行中',pre];}));}
$('policy-test').onclick=()=>run(async()=>{const r=await api('policy-tests',{});$('policy-test-summary').textContent=r.version+' · '+r.results.filter(t=>t.passed).length+'/'+r.results.length+' 通过；仅虚构格式规则测试，不调用模型。';table('policy-test-list',['用例','虚构输入','请求处理','处理后内容','回答处理','断言'],r.results.map(t=>[t.name,t.input,t.request_action,t.request_output??'已阻断，无内容返回',t.response_action,t.passed?'通过':'失败']));},$('policy-test'));
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
$('probe-key').onclick=()=>run(async()=>{if(!issued)return;$('probe-answer').textContent='';$('probe-result').textContent='正在识别并调用本机模型，请稍候…';const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+issued.api_key},body:JSON.stringify({model:issued.model,stream:false,messages:[{role:'user',content:'请用一句话说明付款期限未约定的风险，不复述联系方式。虚构邮箱 alice@example.com，手机号13800138000。'}]})});const d=await r.json();$('probe-result').textContent=r.ok?'真实调用通过；脱敏实体 '+d.privacyguard.entity_count+' 项。':'已阻断：'+(d.error?.code||r.status);if(r.ok)$('probe-answer').textContent=d.choices[0].message.content;await refresh();const rid=d.privacyguard?.request_id||d.request_id;if(rid)await showTrace(rid);},$('probe-key'));
(async()=>{try{const s=await api('session');csrf=s.csrf;await refresh();}catch(e){if(e.message!=='login_required')notice(e.message,true);}})();
