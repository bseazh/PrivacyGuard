from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "test-results/real-annotation-assisted.jsonl"
HOST, PORT = "127.0.0.1", 8765
TYPES = ["PERSON", "ORGANIZATION", "PHONE", "ID_NUMBER", "BANK_CARD", "ADDRESS", "CASE_NUMBER", "CONTRACT_NUMBER", "EMAIL"]
LOCK = threading.Lock()


def load_records() -> list[dict]:
    if not DATA.exists():
        return []
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_records(records: list[dict]) -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    temp = DATA.with_suffix(".tmp")
    temp.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n", encoding="utf-8")
    temp.replace(DATA)


def validate_entity(record: dict, entity: dict) -> dict:
    text = record.get("text", "")
    entity = {"type": str(entity.get("type", "")), "value": str(entity.get("value", "")), "start": int(entity.get("start", -1)), "end": int(entity.get("end", -1)), "review": "confirmed"}
    if entity["type"] not in TYPES:
        raise ValueError("unknown entity type")
    if entity["start"] < 0 or entity["end"] <= entity["start"] or text[entity["start"] : entity["end"]] != entity["value"]:
        raise ValueError("span does not match source text")
    return entity


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PrivacyGuard 标注</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;color:#222;background:#f6f7f9}header{padding:14px 22px;background:#18212f;color:#fff}main{display:grid;grid-template-columns:260px 1fr 390px;gap:14px;padding:14px;height:calc(100vh - 72px);box-sizing:border-box}.panel{background:#fff;border:1px solid #dfe3e8;border-radius:8px;overflow:auto;padding:12px}.doc{padding:10px;border-radius:6px;cursor:pointer;margin-bottom:5px}.doc.active{background:#e8f0ff}.doc small{display:block;color:#687385;margin-top:4px}.text{white-space:pre-wrap;line-height:1.75;font-family:ui-monospace,monospace;font-size:14px}.candidate{border:1px solid #e1e5ea;border-radius:7px;padding:9px;margin:8px 0}.candidate.pending{border-left:4px solid #e0a400}.candidate.confirmed{border-left:4px solid #218739;background:#f3fbf5}.candidate.rejected{opacity:.45;border-left:4px solid #999}.tag{font-size:12px;color:#536071}.value{font-weight:600;margin:4px 0}.row{display:flex;gap:6px;flex-wrap:wrap}button{border:1px solid #bbc4d0;background:#fff;border-radius:5px;padding:6px 9px;cursor:pointer}button:hover{background:#eef3f8}button.primary{background:#1769d2;color:#fff;border-color:#1769d2}select,input{padding:6px;border:1px solid #bbc4d0;border-radius:5px;width:100%;box-sizing:border-box;margin:3px 0 7px}.muted{color:#687385;font-size:13px}.stat{padding:8px;background:#f0f3f7;border-radius:6px;margin:8px 0}h3{margin:8px 0}#toast{position:fixed;right:20px;bottom:20px;background:#17202d;color:#fff;padding:10px 14px;border-radius:6px;display:none}</style></head>
<body><header><b>PrivacyGuard · 本地人工标注</b><span id="summary" style="margin-left:20px;font-size:13px"></span></header><main><section class="panel"><h3>文件</h3><div id="docs"></div></section><section class="panel"><h3 id="title">文本</h3><div class="muted">当前只在本机处理。原文不会发送到网络。</div><hr><div id="text" class="text"></div></section><section class="panel"><h3>候选与 gold</h3><div id="stats" class="stat"></div><div id="candidates"></div><hr><h3>补充实体</h3><label>类型<select id="newType"></select></label><label>原文值<input id="newValue"></label><label>start<input id="newStart" type="number"></label><label>end<input id="newEnd" type="number"></label><button class="primary" onclick="addEntity()">添加到 gold</button><button style="margin-top:8px" onclick="finishDoc()">完成本文件</button></section></main><div id="toast"></div>
<script>
let records=[], current=0;
const types=['PERSON','ORGANIZATION','PHONE','ID_NUMBER','BANK_CARD','ADDRESS','CASE_NUMBER','CONTRACT_NUMBER','EMAIL'];
const $=id=>document.getElementById(id);
function toast(s){$('toast').textContent=s;$('toast').style.display='block';setTimeout(()=>{$('toast').style.display='none'},1800)}
async function load(){records=await (await fetch('/api/records')).json(); types.forEach(t=>$('newType').insertAdjacentHTML('beforeend',`<option>${t}</option>`)); renderDocs(); if(records.length) selectDoc(0)}
function renderDocs(){ $('docs').innerHTML=records.map((r,i)=>`<div class="doc ${i===current?'active':''}" onclick="selectDoc(${i})"><b>${r.id}</b><small>${r.format} · ${r.text.length} 字符 · gold ${r.gold_entities.length}</small></div>`).join(''); let g=records.reduce((n,r)=>n+r.gold_entities.length,0);$('summary').textContent=`${records.length} 份文件 · gold ${g}/100` }
function selectDoc(i){current=i;renderDocs();let r=records[i];$('title').textContent=r.id+' · '+r.format;$('text').textContent=r.text;renderCandidates()}
function renderCandidates(){let r=records[current], list=r.assisted_candidates||[]; $('stats').textContent=`候选 ${list.length} · 已确认 gold ${r.gold_entities.length} · 状态 ${r.review_status}`; $('candidates').innerHTML=list.map((x,i)=>`<div class="candidate ${x.human_status||'pending'}"><div class="tag">${x.type} · ${x.start}:${x.end} · ${x.sources.join('+')}</div><div class="value">${escapeHtml(x.value)}</div><div class="row"><button onclick="confirmCandidate(${i})">确认</button><button onclick="rejectCandidate(${i})">忽略</button><button onclick="editCandidate(${i})">修改</button></div></div>`).join('');}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function save(){let r=records[current];let resp=await fetch('/api/records/'+encodeURIComponent(r.id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(r)});if(!resp.ok){toast(await resp.text());return false}toast('已保存');return true}
async function confirmCandidate(i){let r=records[current],x=r.assisted_candidates[i];let e={type:x.type,value:x.value,start:x.start,end:x.end,review:'confirmed'};if(!r.gold_entities.some(y=>JSON.stringify(y)===JSON.stringify(e)))r.gold_entities.push(e);x.human_status='confirmed';await save();renderCandidates();renderDocs()}
async function rejectCandidate(i){records[current].assisted_candidates[i].human_status='rejected';await save();renderCandidates()}
async function editCandidate(i){let r=records[current],x=r.assisted_candidates[i];let type=prompt('实体类型',x.type),value=prompt('实体值（必须与原文完全一致）',x.value),start=prompt('start',x.start),end=prompt('end',x.end);if(type===null)return;try{let e={type,value,start:Number(start),end:Number(end),review:'confirmed'};if(r.text.slice(e.start,e.end)!==e.value)throw Error('span 与原文不一致');r.gold_entities.push(e);x.human_status='edited';await save();renderCandidates();renderDocs()}catch(e){toast(e.message)}}
async function addEntity(){let r=records[current];try{let e={type:$('newType').value,value:$('newValue').value,start:Number($('newStart').value),end:Number($('newEnd').value),review:'confirmed'};if(r.text.slice(e.start,e.end)!==e.value)throw Error('span 与原文不一致');r.gold_entities.push(e);await save();renderCandidates();renderDocs();$('newValue').value='';$('newStart').value='';$('newEnd').value=''}catch(e){toast(e.message)}}
async function finishDoc(){let r=records[current];let pending=(r.assisted_candidates||[]).filter(x=>!['confirmed','edited','rejected'].includes(x.human_status));if(pending.length){toast('还有候选未确认');return}r.review_status='confirmed';await save();renderCandidates();renderDocs()}
load();
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/records":
            with LOCK: self.send_json(200, load_records())
            return
        data = HTML.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/records/"):
            self.send_json(404, {"error": "not found"}); return
        length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length))
        record_id = path.rsplit("/", 1)[-1]
        try:
            for entity in payload.get("gold_entities", []): validate_entity(payload, entity)
            payload["review_status"] = "confirmed" if payload.get("gold_entities") and payload.get("review_status") == "confirmed" else payload.get("review_status", "pending")
            with LOCK:
                records = load_records(); index = next(i for i, item in enumerate(records) if item["id"] == record_id); records[index] = payload; save_records(records)
            self.send_json(200, {"ok": True})
        except (ValueError, StopIteration, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})

    def log_message(self, *_args) -> None: return


def main() -> None:
    global DATA, PORT
    parser = argparse.ArgumentParser(description="Local-only PrivacyGuard annotation UI")
    parser.add_argument("--data", type=Path, help="Assisted JSONL file to review")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    if args.data:
        DATA = args.data.expanduser().resolve()
    PORT = args.port
    print(f"Local annotation UI: http://{HOST}:{PORT} ({DATA})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__": main()
