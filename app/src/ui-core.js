export const POLICY_META = {
  must_redact: {label: '自动脱敏', order: 0},
  manual_review: {label: '需要人工确认', order: 1},
  do_not_redact: {label: '默认不脱敏', order: 2}
};

export const ENTITY_TYPES = ['PERSON','ORGANIZATION','ADDRESS','DEPARTMENT','PROJECT','COURT','LAW_FIRM','PLAINTIFF','DEFENDANT','APPLICANT','RESPONDENT','ATTORNEY','LEGAL_REPRESENTATIVE','PHONE','ID_NUMBER','BANK_CARD','EMAIL','CASE_NUMBER','CONTRACT_NUMBER'];

const MUST_REDACT = new Set(['PERSON','PHONE','ID_NUMBER','BANK_CARD','ADDRESS','EMAIL','PLAINTIFF','DEFENDANT','APPLICANT','RESPONDENT','ATTORNEY','LEGAL_REPRESENTATIVE']);
const DO_NOT_REDACT = new Set(['CASE_NUMBER','CONTRACT_NUMBER']);
const PERSON_TYPES = new Set(['PERSON','PLAINTIFF','DEFENDANT','APPLICANT','RESPONDENT','ATTORNEY','LEGAL_REPRESENTATIVE']);
const ORGANIZATION_TYPES = new Set(['ORGANIZATION','COURT','LAW_FIRM']);
const TYPE_LABELS = {PERSON:'人员',ORGANIZATION:'机构',ADDRESS:'地址',DEPARTMENT:'部门',PROJECT:'项目',COURT:'法院',LAW_FIRM:'律所',PHONE:'电话',ID_NUMBER:'证件号',BANK_CARD:'账户',EMAIL:'邮箱',CASE_NUMBER:'案号',CONTRACT_NUMBER:'合同号'};
const NATURAL_NAMES = ['李明','王芳','陈晨','赵宁','周安','林悦','吴桐','郑远','许清','何川'];
const NATURAL_ORGANIZATIONS = ['星河科技有限公司','云岚商贸有限公司','青禾咨询有限公司','远川实业有限公司','明海文化有限公司'];

function alphaIndex(index) {
  let output='';
  while(index){index--;output=String.fromCharCode(65+(index%26))+output;index=Math.floor(index/26);}
  return output;
}

function canonicalType(type){if(PERSON_TYPES.has(type))return 'PERSON';if(ORGANIZATION_TYPES.has(type))return 'ORGANIZATION';return type;}

export function buildReplacementMap(entities,mode='semantic') {
  const counters={}, replacements=new Map();
  for(const entity of entities.filter(item=>item.review==='confirmed')){
    const group=canonicalType(entity.type);const identity=`${group}\u0000${entity.value}`;
    if(replacements.has(identity))continue;
    counters[group]=(counters[group]||0)+1;const number=counters[group];
    let replacement=`${TYPE_LABELS[group]||'敏感项'}${alphaIndex(number)}`;
    if(mode==='natural'){
      if(group==='PERSON')replacement=NATURAL_NAMES[(number-1)%NATURAL_NAMES.length];
      else if(group==='ORGANIZATION')replacement=NATURAL_ORGANIZATIONS[(number-1)%NATURAL_ORGANIZATIONS.length];
    }
    replacements.set(identity,replacement);
  }
  return replacements;
}

export function policyForType(type) {
  if (MUST_REDACT.has(type)) return 'must_redact';
  if (DO_NOT_REDACT.has(type)) return 'do_not_redact';
  return 'manual_review';
}

export function normalizeResult(value) {
  const text=value.text||'';
  return {...value, text, entities:(value.entities||[]).map(entity=>{
    const valid=Number.isInteger(entity.start)&&Number.isInteger(entity.end)&&entity.start>=0&&entity.end>entity.start&&text.slice(entity.start,entity.end)===entity.value;
    const policy=entity.policy||policyForType(entity.type);
    const review=entity.review||(policy==='must_redact'?'confirmed':'pending');
    return {...entity, review, policy, offsetValid:valid};
  })};
}

export function reviewStats(entities) {
  const stats={pending:0,confirmed:0,rejected:0,total:entities.length,automatic:0,needsReview:0};
  for(const entity of entities){if(entity.policy==='must_redact')stats.automatic++;if(entity.policy==='manual_review')stats.needsReview++;}
  for(const entity of entities) stats[entity.review] = (stats[entity.review]||0)+1;
  return stats;
}

export function groupedEntities(entities) {
  const groups={must_redact:[],manual_review:[],do_not_redact:[]};
  entities.forEach((entity,index)=>(groups[entity.policy]||(groups.manual_review)).push({...entity,_index:index}));
  return groups;
}

export function overlapsConfirmed(entities,index) {
  const entity=entities[index];
  return entities.some((other,otherIndex)=>otherIndex!==index&&other.review==='confirmed'&&entity.start<other.end&&entity.end>other.start);
}

export function updateEntityValue(text,entity,value) {
  const starts=[];
  for(let index=text.indexOf(value);index>=0;index=text.indexOf(value,index+1)) starts.push(index);
  if(!starts.length) throw new Error('修改后的文本在原文中不存在');
  const start=starts.reduce((best,current)=>Math.abs(current-entity.start)<Math.abs(best-entity.start)?current:best,starts[0]);
  return {...entity,value,start,end:start+value.length,offsetValid:true};
}

export function buildRedaction(text,entities,mode='token') {
  const confirmed=entities.map((entity,index)=>({...entity,_index:index})).filter(entity=>entity.review==='confirmed').sort((a,b)=>a.start-b.start||b.end-a.end);
  let output='',cursor=0;
  const mapping={};
  const counters={};
  const tokens=new Map();
  const replacements=mode==='token'?null:buildReplacementMap(confirmed,mode);
  for(const entity of confirmed) {
    if(entity.start<cursor) continue;
    const identity=`${entity.type}\u0000${entity.value}`;
    let token;
    if(replacements){token=replacements.get(`${canonicalType(entity.type)}\u0000${entity.value}`);}
    else {token=tokens.get(identity);if(!token){counters[entity.type]=(counters[entity.type]||0)+1;token=`<${entity.type}_${String(counters[entity.type]).padStart(3,'0')}>`;tokens.set(identity,token);}}
    output+=text.slice(cursor,entity.start)+token;
    if(!mapping[token])mapping[token]={type:entity.type,value:entity.value,occurrences:[]};
    mapping[token].occurrences.push({start:entity.start,end:entity.end});
    cursor=entity.end;
  }
  output+=text.slice(cursor);
  return {text:output,mapping,count:Object.keys(mapping).length};
}

export function exportReadiness(entities,previewApproved=false) {
  const stats=reviewStats(entities);
  if(stats.pending) return {ready:false,message:`还有 ${stats.pending} 个候选未复核。`};
  if(!previewApproved) return {ready:false,message:'请先核对脱敏预览并勾选确认。'};
  if(!stats.confirmed) return {ready:true,message:'未确认脱敏项，将导出原文副本。'};
  return {ready:true,message:`已确认 ${stats.confirmed} 个实体，可以导出。`};
}
