'use strict';
const $ = id => document.getElementById(id);
const KEY = 'wenjian-v1';
const freshDraft = () => ({id:crypto.randomUUID(), title:'未命名文章', body:''});
let state = {papers:[], drafts:[freshDraft()]};
function valid(data) {
  return data && Array.isArray(data.papers) && Array.isArray(data.drafts) && data.drafts.length > 0 &&
    data.papers.every(p => p && ['id','title','author','year','url','notes'].every(k => typeof p[k] === 'string') && Array.isArray(p.tags) && p.tags.every(t => typeof t === 'string')) &&
    data.drafts.every(d => d && ['id','title','body'].every(k => typeof d[k] === 'string')) &&
    new Set(data.papers.map(p=>p.id)).size === data.papers.length && new Set(data.drafts.map(d=>d.id)).size === data.drafts.length;
}
function notify(message){$('status').textContent=message;}
try { const saved=localStorage.getItem(KEY); if(saved){const parsed=JSON.parse(saved);if(!valid(parsed))throw Error();state=parsed;} } catch {notify('无法读取已有数据；请先备份或恢复有效备份，保存可能不可用。');}
let active=state.drafts[0].id;
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));notify('已保存到当前浏览器');}catch{notify('保存失败：浏览器存储不可用或已满，请立即导出备份。');}}
function element(tag,text,className){const node=document.createElement(tag);node.textContent=text;if(className)node.className=className;return node;}
function action(text,fn){const b=element('button',text);b.type='button';b.onclick=fn;return b;}
function draft(){return state.drafts.find(d=>d.id===active);}
function renderPapers(){
 const q=$('search').value.toLowerCase();$('papers').replaceChildren();$('count').textContent=`${state.papers.length} 篇`;
 const list=state.papers.filter(p=>[p.title,p.author,p.year,p.notes,...p.tags].join(' ').toLowerCase().includes(q));
 if(!list.length)$('papers').append(element('p',q?'未找到匹配文献':'还没有文献，添加第一篇开始整理。','hint'));
 for(const p of list){const card=element('article','');card.append(element('h3',p.title),element('p',[p.author,p.year].filter(Boolean).join(' · ')));
 for(const t of p.tags)card.append(element('span',t,'tag'));
 if(p.notes)card.append(element('p',p.notes));
 const actions=element('div','','actions');
 if(p.url){let url=p.url.trim();if(url.startsWith('10.'))url='https://doi.org/'+url;try{const parsed=new URL(url);if(['http:','https:'].includes(parsed.protocol)){const a=element('a','原文');a.href=parsed.href;a.target='_blank';a.rel='noopener noreferrer';actions.append(a);}}catch{}}
 actions.append(action('引用',()=>{const e=$('editor');const cite=`（${p.author||'佚名'}，${p.year||'年份未知'}）[^${p.id}]`;e.setRangeText(cite,e.selectionStart,e.selectionEnd,'end');draft().body=e.value;save();updateWords();e.focus();}),action('删除',()=>{if(confirm('删除此文献？已有正文引用将保留。')){state.papers=state.papers.filter(x=>x.id!==p.id);save();renderPapers();}}));card.append(actions);$('papers').append(card);}
}
function updateWords(){$('words').textContent=`${Array.from($('editor').value.replace(/\s/g,'')).length} 字符`;}
function renderDrafts(){$('drafts').replaceChildren(...state.drafts.map(d=>{const o=element('option',d.title||'未命名文章');o.value=d.id;return o;}));$('drafts').value=active;$('draft-title').value=draft().title;$('editor').value=draft().body;updateWords();}
$('paper-form').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);const title=f.get('title').trim();if(!title)return;const p={id:crypto.randomUUID(),title};for(const k of ['author','year','url','notes'])p[k]=f.get(k).trim();p.tags=f.get('tags').split(/[,，]/).map(t=>t.trim()).filter(Boolean);state.papers.unshift(p);save();renderPapers();e.target.reset();};
$('search').oninput=renderPapers;
$('drafts').onchange=e=>{active=e.target.value;renderDrafts();};
$('new-draft').onclick=()=>{const d=freshDraft();state.drafts.push(d);active=d.id;save();renderDrafts();};
$('draft-title').oninput=e=>{draft().title=e.target.value;const option=$('drafts').selectedOptions[0];option.textContent=e.target.value||'未命名文章';save();};
$('editor').oninput=e=>{draft().body=e.target.value;save();updateWords();};
$('delete-draft').onclick=()=>{if(!confirm('确定删除当前文章？此操作无法撤销。'))return;state.drafts=state.drafts.filter(d=>d.id!==active);if(!state.drafts.length)state.drafts.push(freshDraft());active=state.drafts[0].id;save();renderDrafts();};
function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('backup').onclick=()=>download('文笺备份.json',JSON.stringify(state,null,2),'application/json');
$('restore').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const data=JSON.parse(await file.text());if(!valid(data))throw Error();if(!confirm('恢复备份会替换当前全部数据。建议先备份，是否继续？'))return;state=data;active=state.drafts[0].id;save();renderPapers();renderDrafts();}catch{notify('恢复失败：请选择格式有效的文笺 JSON 备份。');}finally{e.target.value='';}};
$('export').onclick=()=>{const d=draft();const refs=state.papers.filter(p=>d.body.includes(`[^${p.id}]`)).map(p=>`[^${p.id}]: ${[p.author,p.year,p.title,p.url].filter(Boolean).join('. ')}`).join('\n');download((d.title||'未命名文章').replace(/[\\/:*?"<>|]/g,'_')+'.md',`# ${d.title}\n\n${d.body}\n\n${refs}\n`,'text/markdown;charset=utf-8');};
renderPapers();renderDrafts();

async function askAI(mode){
 const text=$('ai-input').value.trim() || (mode==='write' ? $('editor').value.trim() : '');
 if(!text){$('ai-status').textContent='请先输入需要处理的内容。';return;}
 $('ai-summary').disabled=$('ai-write').disabled=true;$('ai-status').textContent='正在生成……';
 try{const response=await fetch('/api/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,text})});const result=await response.json();if(!response.ok)throw Error(result.error || '请求失败');$('ai-output').value=result.text;$('ai-status').textContent='生成完成，请核对后插入正文。';}
 catch(error){$('ai-status').textContent=error.message;}
 finally{$('ai-summary').disabled=$('ai-write').disabled=false;}
}
$('ai-summary').onclick=()=>askAI('summary');$('ai-write').onclick=()=>askAI('write');
$('ai-insert').onclick=()=>{const text=$('ai-output').value;if(!text)return;draft().body += '\n\n'+text;$('editor').value=draft().body;save();updateWords();};
