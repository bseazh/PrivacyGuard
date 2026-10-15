import {ENTITY_TYPES,POLICY_META,buildRedaction,exportReadiness,groupedEntities,normalizeResult,overlapsConfirmed,policyForType,reviewStats,updateEntityValue} from './ui-core.js';

let result=null;
let serviceReady=false;
let lastMapping=null;
let previewApproved=false;
let currentFile=null;
const api='http://127.0.0.1:8766';
const $=id=>document.getElementById(id);
const esc=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

function setService(state,label){serviceReady=state==='ready';$('status').className=`service-status ${state}`;$('status').textContent=label;$('file').disabled=!serviceReady;}
function setPhase(phase,label,percent){$('progressLabel').textContent=label;$('progressBar').style.width=`${percent}%`;const phases=['upload','extract','ner','review','export'];const current=phases.indexOf(phase);document.querySelectorAll('#phaseList li').forEach((item,index)=>{item.classList.toggle('active',index===current);item.classList.toggle('done',index<current);});}
function setRequest(id=''){$('requestId').textContent=id?`任务 ID：${id}`:'';}

function resetResultView(){
  result=null;lastMapping=null;previewApproved=false;
  $('reviewPanel').scrollTop=0;
  $('reviewSummary').textContent='正在等待识别结果';
  $('policyStats').innerHTML='';
  $('entities').innerHTML='<p class="empty-note">当前文件尚无识别结果。</p>';
  $('content').textContent='正在处理当前文件…';
  $('content').classList.add('empty');
  $('preview').textContent='完成识别并复核候选后，可在此检查脱敏结果。';
  $('preview').classList.add('empty');
  $('previewApproved').checked=false;$('previewApproved').disabled=true;
  $('exportHint').textContent='完成所有候选复核后可导出。';
  $('exportText').disabled=true;$('exportMapping').disabled=true;$('confirmRequired').disabled=true;
  $('exportPdf').disabled=true;
}

function renderDocument(){
  if(!result)return;
  const list=result.entities.map((entity,index)=>({...entity,_index:index})).filter(entity=>entity.offsetValid!==false&&Number.isInteger(entity.start)&&Number.isInteger(entity.end)&&entity.start>=0&&entity.end>entity.start).sort((a,b)=>a.start-b.start||b.end-a.end);
  let html='',cursor=0;
  for(const entity of list){
    if(entity.start<cursor)continue;
    html+=esc(result.text.slice(cursor,entity.start));
    html+=`<mark class="entity-mark mark-${esc(entity.type)} ${esc(entity.review)}" title="${esc(entity.type)} · ${esc(POLICY_META[entity.policy]?.label||entity.policy)}" data-entity-index="${entity._index}">${esc(result.text.slice(entity.start,entity.end))}</mark>`;
    cursor=entity.end;
  }
  $('content').innerHTML=html+esc(result.text.slice(cursor));
  $('content').classList.remove('empty');
  document.querySelectorAll('.entity-mark').forEach(mark=>mark.addEventListener('click',()=>{$('#e'+mark.dataset.entityIndex)?.scrollIntoView({behavior:'smooth',block:'center'});}));
  const redaction=buildRedaction(result.text,result.entities,$('replacementMode').value);
  $('preview').textContent=redaction.text;
  $('preview').classList.toggle('empty',redaction.count===0);
}

function renderReview(){
  if(!result)return;
  const stats=reviewStats(result.entities);
  $('reviewSummary').textContent=`共 ${stats.total} 个 · 自动脱敏 ${stats.automatic} · 需人工确认 ${stats.needsReview} · 待处理 ${stats.pending} · 已确认 ${stats.confirmed} · 已忽略 ${stats.rejected}`;
  const groups=groupedEntities(result.entities);
  $('policyStats').innerHTML=Object.entries(POLICY_META).map(([policy,meta])=>`<div class="policy-stat">${meta.label}<strong>${groups[policy].length}</strong></div>`).join('');
  $('entities').innerHTML=Object.entries(POLICY_META).sort((a,b)=>a[1].order-b[1].order).map(([policy,meta])=>{
    const cards=groups[policy].map(entity=>{
      const index=entity._index;
      return `<article class="entity ${esc(entity.review)} ${overlapsConfirmed(result.entities,index)?'overlap':''} ${entity.offsetValid===false?'invalid':''}" id="e${index}"><div class="entity-top"><b>${esc(entity.type)}</b><span>${entity.start}:${entity.end} · <span class="source">${esc(entity.source||'ner')}</span></span></div><div class="entity-value">${esc(entity.value)}</div>${entity.offsetValid===false?'<div class="offset-warning">原文位置校验失败，请修改文本后再确认</div>':''}<div class="controls"><input aria-label="实体文本" value="${esc(entity.value)}" data-edit-value="${index}"><select aria-label="实体类型" data-edit-type="${index}">${ENTITY_TYPES.map(type=>`<option ${type===entity.type?'selected':''}>${type}</option>`).join('')}</select></div><div class="actions"><button data-review="confirm" data-index="${index}" ${entity.offsetValid===false?'disabled':''}>确认</button><button data-review="reject" data-index="${index}">忽略</button></div></article>`;
    }).join('');
    return cards?`<section class="policy-group"><h3>${meta.label} · ${groups[policy].length}</h3>${cards}</section>`:'';
  }).join('')||'<p class="empty-note">未识别到候选实体。</p>';
  document.querySelectorAll('[data-review]').forEach(button=>button.addEventListener('click',()=>reviewEntity(Number(button.dataset.index),button.dataset.review==='confirm')));
  document.querySelectorAll('[data-edit-type]').forEach(select=>select.addEventListener('change',()=>editType(Number(select.dataset.editType),select.value)));
  document.querySelectorAll('[data-edit-value]').forEach(input=>input.addEventListener('change',()=>editValue(Number(input.dataset.editValue),input.value)));
  $('confirmRequired').disabled=!groups.must_redact.some(entity=>entity.review==='pending');
  $('previewApproved').disabled=stats.pending>0;
  $('previewApproved').checked=previewApproved;
  const readiness=exportReadiness(result.entities,previewApproved);
  $('exportHint').textContent=readiness.message;
  $('exportText').disabled=!readiness.ready;
  $('exportPdf').disabled=!readiness.ready||!currentFile||!currentFile.name.toLowerCase().endsWith('.pdf')||$('replacementMode').value==='token';
  $('exportMapping').disabled=!lastMapping;
  if(previewApproved)setPhase('review','预览已确认，可以导出',100);
  else if(stats.pending===0)setPhase('review',stats.total?'复核完成：请核对脱敏预览':'识别完成：未发现候选，请核对原文',100);
  else if(stats.pending===stats.total&&result.diagnostics?.parse_failures)setPhase('review',`识别完成，但有 ${result.diagnostics.parse_failures} 个子段解析失败；请谨慎复核`,100);
  else if(stats.pending===stats.total)setPhase('review',`识别完成：${stats.total} 个候选，等待人工复核`,100);
  else setPhase('review',`人工复核中：剩余 ${stats.pending} 个候选`,100);
  renderDocument();
}

function reviewEntity(index,confirmed){
  if(confirmed&&overlapsConfirmed(result.entities,index)){setPhase('review','该候选与已确认实体重叠，请先忽略其中一个',100);return;}
  result.entities[index].review=confirmed?'confirmed':'rejected';lastMapping=null;previewApproved=false;renderReview();
}
function editType(index,type){result.entities[index].type=type;result.entities[index].policy=policyForType(type);result.entities[index].review='pending';lastMapping=null;previewApproved=false;renderReview();}
function editValue(index,value){try{result.entities[index]=updateEntityValue(result.text,result.entities[index],value);result.entities[index].review='pending';lastMapping=null;previewApproved=false;renderReview();}catch(error){setPhase('review',error.message,100);renderReview();}}

async function pollJob(jobId){
  for(;;){
    await new Promise(resolve=>setTimeout(resolve,700));
    const response=await fetch(`${api}/jobs/${encodeURIComponent(jobId)}`,{cache:'no-store'});
    if(!response.ok)throw new Error(`无法读取任务状态（HTTP ${response.status}）`);
    const state=await response.json();
    if(state.phase==='extract')setPhase('extract',`${state.name}：正在提取文本`,25);
    else if(state.phase==='ner')setPhase('ner',state.message||'模型识别中',state.progress||30);
    else if(state.status==='queued')setPhase('upload',state.message||'已进入本地队列',12);
    if(state.status==='done')return state.result;
    if(state.status==='error')throw new Error(`后端处理失败：${state.message}`);
  }
}

async function analyze(file){
  if(!serviceReady)return;
  currentFile=file;
  resetResultView();$('file').disabled=true;$('fileName').textContent=file.name;$('fileMeta').textContent=`${Math.ceil(file.size/1024)} KB · 本地处理`;
  const requestId=crypto.randomUUID?crypto.randomUUID():Date.now().toString(36);setRequest(requestId);setPhase('upload',`正在上传：${file.name}`,8);
  try{
    const bytes=new Uint8Array(await file.arrayBuffer());
    let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);
    const response=await fetch(`${api}/analyze-upload`,{method:'POST',headers:{'Content-Type':'application/json','X-Request-ID':requestId},body:JSON.stringify({name:file.name,data:btoa(binary)})});
    if(!response.ok)throw new Error(`任务创建失败（HTTP ${response.status}）：${await response.text()}`);
    const job=await response.json();
    result=normalizeResult(job.job_id?await pollJob(job.job_id):job);lastMapping=null;previewApproved=false;
    setPhase('review',`识别完成：${result.entities.length} 个候选，等待人工复核`,100);renderReview();
  }catch(error){const disconnected=error.message==='Load failed'||error instanceof TypeError;const detail=disconnected?'本地服务连接中断，请检查日志和 8766 端口':error.message;setPhase('upload',`处理失败：${detail}`,0);if(disconnected)setService('error','本地服务异常');}
  finally{$('file').disabled=!serviceReady;}
}

function download(name,data,type='text/plain;charset=utf-8'){const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([data],{type}));link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}
function exportText(){const readiness=exportReadiness(result?.entities||[],previewApproved);if(!readiness.ready)return;const mode=$('replacementMode').value;const redaction=buildRedaction(result.text,result.entities,mode);download(`${result.name}.redacted.txt`,redaction.text);lastMapping=redaction.mapping;$('exportMapping').disabled=false;setPhase('export',`已导出脱敏文本，共 ${redaction.count} 个替换项`,100);}
async function exportPdf(){
  const readiness=exportReadiness(result?.entities||[],previewApproved);if(!readiness.ready||!currentFile)return;
  $('exportPdf').disabled=true;setPhase('export','正在安全删除 PDF 原文并写入假名…',55);
  try{
    const bytes=new Uint8Array(await currentFile.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);
    const entities=result.entities.filter(entity=>entity.review==='confirmed').map(({type,value})=>({type,value}));
    const response=await fetch(`${api}/redact-pdf-upload`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:currentFile.name,data:btoa(binary),entities,replacement_mode:$('replacementMode').value})});
    const payload=await response.json();if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
    const output=Uint8Array.from(atob(payload.data),char=>char.charCodeAt(0));download(payload.name,output,'application/pdf');
    lastMapping=payload.audit.mapping;$('exportMapping').disabled=false;setPhase('export',`假名化 PDF 已通过原文残留检查，共 ${Object.keys(lastMapping).length} 个替换项`,100);
  }catch(error){setPhase('export',`PDF 导出失败：${error.message}`,0);}
  finally{renderReview();}
}
async function getKey(){const stored=localStorage.getItem('legalredaction-key');if(stored)return crypto.subtle.importKey('raw',Uint8Array.from(atob(stored),char=>char.charCodeAt(0)),{name:'AES-GCM'},false,['encrypt']);const key=await crypto.subtle.generateKey({name:'AES-GCM',length:256},true,['encrypt']);const raw=new Uint8Array(await crypto.subtle.exportKey('raw',key));localStorage.setItem('legalredaction-key',btoa(String.fromCharCode(...raw)));return key;}
async function exportMapping(){if(!lastMapping)return;const iv=crypto.getRandomValues(new Uint8Array(12));const encrypted=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},await getKey(),new TextEncoder().encode(JSON.stringify(lastMapping))));download(`${result.name}.mapping.enc.json`,JSON.stringify({version:1,algorithm:'AES-256-GCM',iv:[...iv],ciphertext:[...encrypted]},null,2),'application/json');setPhase('export','脱敏文本和加密映射表均已导出',100);}

$('file').addEventListener('change',event=>{const file=event.target.files[0];if(file)analyze(file);event.target.value='';});
$('confirmRequired').addEventListener('click',()=>{result.entities.forEach((entity,index)=>{if(entity.policy==='must_redact'&&entity.review==='pending'&&entity.offsetValid!==false&&!overlapsConfirmed(result.entities,index))entity.review='confirmed';});lastMapping=null;previewApproved=false;renderReview();});
$('previewApproved').addEventListener('change',event=>{previewApproved=event.target.checked;renderReview();});
$('exportText').addEventListener('click',exportText);$('exportMapping').addEventListener('click',exportMapping);
$('exportPdf').addEventListener('click',exportPdf);
$('replacementMode').addEventListener('change',()=>{previewApproved=false;renderReview();});
document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(item=>item.classList.toggle('active',item===tab));$('sourceView').classList.toggle('hidden',tab.dataset.view!=='source');$('previewView').classList.toggle('hidden',tab.dataset.view!=='preview');}));

async function checkHealth(){try{const response=await fetch(`${api}/health`,{cache:'no-store'});if(!response.ok)throw new Error();setService('ready','本地服务已连接');}catch{setService('connecting','正在连接本地服务');}}
checkHealth();setInterval(checkHealth,2000);
