'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1);
let state = null, selected = null, submitting = false, requestSignature = '', renderedChat = null;
const nodes = new Map(), drafts = new Map(), pendingDrafts = new Map();
async function api(path, data) {
  const response = await fetch('/api/' + path, {method:data ? 'POST':'GET', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token}, body:data ? JSON.stringify(data):undefined, cache:'no-store'});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function error(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
function el(tag, text, className) { const node=document.createElement(tag); if(text) node.textContent=text; if(className) node.className=className; return node; }
function pick(id) {
  if(selected) drafts.set(selected,$('input').value);
  selected=id; $('input').value=drafts.get(id)||'';
  render(); $('input').focus();
}
function current() { return state?.chats.find(c=>c.id===selected); }
function render() {
  if(!state)return;
  if(!selected && state.chats.length)selected=state.chats[state.chats.length-1].id;
  const chat=current();
  const pending=pendingDrafts.get(selected);
  if(pending && (chat?.status==='failed'||(chat?.status==='idle'&&chat.cancelled)) && chat.human_turns===pending.turns && !$('input').value){
    $('input').value=pending.raw;pendingDrafts.delete(selected);
  } else if(pending && chat?.human_turns>pending.turns){pendingDrafts.delete(selected);}
  $('account').textContent=state.account;
  $('connection').textContent=state.connected?'●  Codex connected':'Disconnected';
  $('chats').replaceChildren(...[...state.chats].reverse().map(c=>{const b=el('button',c.title,c.id===selected?'active':'');b.onclick=()=>pick(c.id);b.title=c.cwd;return b;}));
  $('title').textContent=chat?.title||'A clearer starting point';
  $('context').textContent=chat ? chat.cwd+'  ·  '+(chat.model||'Default model')+'  ·  '+(chat.sandbox==='read-only'?'Read only':'Workspace access') : 'A separate client powered by Codex app-server';
  $('welcome').hidden=!!chat?.messages.length;
  if(renderedChat!==selected){$('messages').replaceChildren();nodes.clear();requestSignature='';renderedChat=selected;}
  const nearBottom=$('conversation').scrollHeight-$('conversation').scrollTop-$('conversation').clientHeight<120;
  for(const message of chat?.messages||[]){
    let record=nodes.get(message.id);
    if(!record){
      const wrapper=el('article',null,'message '+message.role);
      wrapper.append(el('div',message.role==='assistant'?'Codex':message.role==='tool'?'Activity':'Sent to worker','label'));
      let content;
      if(message.role==='user'&&message.decision==='forged'){
        const details=el('details');details.append(el('summary','Forged brief · '+message.reason));content=el('pre');details.append(content);wrapper.append(details);
      }else if(message.role==='tool'){
        const details=el('details');const summary=el('summary');content=el('pre');details.append(summary,content);wrapper.append(details);record={summary};
      }else{content=el('div',null,'body');wrapper.append(content);if(message.role==='user')wrapper.append(el('small',message.reason,'subtle'));}
      record={...record,wrapper,content};nodes.set(message.id,record);$('messages').append(wrapper);
    }
    const text=message.role==='tool'?(message.detail||message.text):message.text;
    if(record.content.textContent!==text)record.content.textContent=text;
    if(record.summary)record.summary.textContent=message.text+' · '+(message.status||'');
  }
  if(nearBottom)$('conversation').scrollTop=$('conversation').scrollHeight;
  const busy=chat&&!['idle','failed'].includes(chat.status);
  $('send').disabled=submitting||!!busy||!state.connected;
  $('stop').hidden=!busy;
  $('recover').hidden=chat?.status!=='uncertain';
  const messages={forging:'Forging privately… the working agent has not received your request.',starting:'Forge complete. Starting the working turn…',working:'Codex is working from the submitted prompt.',idle:'Ready · every message passes through the preprocessing gate',failed:'Submission stopped. You can edit and retry.',uncertain:'Turn status is uncertain. Restart the client before continuing.'};
  $('progress').textContent=chat?(messages[chat.status]||chat.status):'Ready for a new idea';
  if(chat?.error)error(chat.error);
  renderRequests(chat);
}
function renderRequests(chat){
  const signature=JSON.stringify((chat?.requests||[]).map(r=>r.id));
  if(signature===requestSignature)return;
  requestSignature=signature;$('requests').replaceChildren();
  for(const r of chat?.requests||[]){
    const card=el('div',null,'request');card.append(el('h3',r.method.includes('requestUserInput')?'Codex has a question':'Your approval is needed'));
    const answer=async data=>{try{await api('answer',{id:chat.id,request_id:r.id,...data});await refresh();}catch(e){error(e.message);}};
    if(r.method==='item/tool/requestUserInput'){
      const fields=[];
      for(const q of r.params.questions||[]){
        card.append(el('label',q.question));
        if(q.options?.length)card.append(el('p',q.options.map(o=>o.label+(o.description?' — '+o.description:'')).join('\n'),'subtle'));
        const field=el('input');field.placeholder='Your answer';field.setAttribute('aria-label',q.question);card.append(field);fields.push([q.id,field]);
      }
      const send=el('button','Send answers');send.onclick=()=>answer({answers:Object.fromEntries(fields.map(([id,field])=>[id,{answers:[field.value]}]))});card.append(send);
    }else{
      card.append(el('pre',JSON.stringify(r.params,null,2)));
      const supported=['item/commandExecution/requestApproval','item/fileChange/requestApproval','item/permissions/requestApproval'].includes(r.method);
      if(supported){const accept=el('button','Allow once');accept.onclick=()=>answer({decision:'accept'});card.append(accept);}
      const decline=el('button',supported?'Decline':'Decline unsupported request','secondary');decline.onclick=()=>answer({decision:'decline'});card.append(decline);
    }
    $('requests').append(card);
  }
}
async function refresh(){try{state=await api('state');render();}catch(e){error(e.message);$('connection').textContent='Disconnected';}}
$('new').onclick=()=>{
  $('folder').value=current()?.cwd||state?.default_cwd||'';
  $('model').replaceChildren(el('option','Your configured Codex default'));
  $('model').firstChild.value='';
  for(const model of state?.models||[]){const o=el('option',model.displayName||model.model||model.id);o.value=model.model||model.id;$('model').append(o);}
  $('setup').showModal();
};
$('cancel-setup').onclick=()=>$('setup').close();
$('setup-form').onsubmit=async e=>{e.preventDefault();const initialDraft=selected?null:$('input').value;try{const result=await api('new',{cwd:$('folder').value,model:$('model').value,sandbox:$('sandbox').value});$('setup').close();await refresh();pick(result.id);if(initialDraft!==null)$('input').value=initialDraft;error('');}catch(e){error(e.message);}};
$('compose').onsubmit=async e=>{
  e.preventDefault();if(submitting||$('send').disabled||!$('input').value.trim())return;
  if(!selected){$('new').click();return;}
  submitting=true;error('');render();
  const raw=$('input').value;
  try{pendingDrafts.set(selected,{raw,turns:current().human_turns});await api('send',{id:selected,text:raw,request_id:crypto.randomUUID()});drafts.set(selected,'');$('input').value='';await refresh();}
  catch(e){error(e.message);}
  finally{submitting=false;render();}
};
$('input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('compose').requestSubmit();}});
$('stop').onclick=async()=>{try{await api('stop',{id:selected});await refresh();}catch(e){error(e.message);}};
$('recover').onclick=async()=>{try{await api('recover',{id:selected});error('');await refresh();}catch(e){error(e.message);}};
refresh();setInterval(refresh,900);
