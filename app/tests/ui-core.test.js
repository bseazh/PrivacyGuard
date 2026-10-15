import test from 'node:test';
import assert from 'node:assert/strict';
import {buildRedaction,buildReplacementMap,exportReadiness,groupedEntities,normalizeResult,overlapsConfirmed,policyForType,updateEntityValue} from '../src/ui-core.js';

const entities=[
  {type:'PERSON',value:'张伟',start:2,end:4,policy:'must_redact',review:'confirmed'},
  {type:'ORGANIZATION',value:'华星公司',start:6,end:10,policy:'manual_review',review:'rejected'}
];

test('automatically confirms mandatory redaction and validates offsets',()=>{const entity=normalizeResult({text:'张伟',entities:[{type:'PERSON',value:'张伟',start:0,end:2}]}).entities[0];assert.equal(entity.review,'confirmed');assert.equal(entity.offsetValid,true);});
test('keeps semantic entities in review state',()=>{const entity=normalizeResult({text:'星斗计划',entities:[{type:'PROJECT',value:'星斗计划',start:0,end:4}]}).entities[0];assert.equal(entity.review,'pending');assert.equal(entity.policy,'manual_review');});
test('flags an entity whose offsets do not match source text',()=>assert.equal(normalizeResult({text:'张伟',entities:[{type:'PERSON',value:'李娜',start:0,end:2}]}).entities[0].offsetValid,false));
test('groups candidates by policy',()=>assert.equal(groupedEntities(entities).must_redact.length,1));
test('creates separate tokens and mapping',()=>{const out=buildRedaction('原告张伟诉华星公司',entities);assert.match(out.text,/<PERSON_001>/);assert.equal(out.mapping['<PERSON_001>'].value,'张伟');});
test('reuses one token for repeated occurrences',()=>{const repeated=[{...entities[0],start:0,end:2},{...entities[0],start:3,end:5}];const out=buildRedaction('张伟和张伟',repeated);assert.equal(out.text,'<PERSON_001>和<PERSON_001>');assert.equal(out.mapping['<PERSON_001>'].occurrences.length,2);});
test('reuses one semantic pseudonym for repeated occurrences',()=>{const repeated=[{...entities[0],start:0,end:2},{...entities[0],start:3,end:5}];assert.equal(buildRedaction('张伟和张伟',repeated,'semantic').text,'人员A和人员A');});
test('keeps person role aliases in one pseudonym namespace',()=>{const map=buildReplacementMap([{type:'PLAINTIFF',value:'张伟',review:'confirmed'},{type:'PERSON',value:'张伟',review:'confirmed'},{type:'DEFENDANT',value:'李娜',review:'confirmed'}]);assert.deepEqual([...map.values()],['人员A','人员B']);});
test('blocks export until review and preview approval',()=>{assert.equal(exportReadiness([{...entities[0],review:'pending'}],true).ready,false);assert.equal(exportReadiness(entities,false).ready,false);assert.equal(exportReadiness(entities,true).ready,true);});
test('allows approved zero-entity export',()=>assert.equal(exportReadiness([],true).ready,true));
test('maps entity types to policy',()=>{assert.equal(policyForType('PERSON'),'must_redact');assert.equal(policyForType('COURT'),'manual_review');assert.equal(policyForType('CASE_NUMBER'),'do_not_redact');});
test('detects confirmed overlap',()=>assert.equal(overlapsConfirmed([{...entities[0]},{...entities[0],start:3,end:5}],1),true));
test('moves edited value to the nearest source occurrence',()=>assert.equal(updateEntityValue('张伟与李娜，张伟代理',entities[0],'张伟').start,0));
