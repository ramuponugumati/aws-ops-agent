/* UI components */
const SEVERITY_ORDER = ['critical','high','medium','low','info'];
const SKILL_ICONS = {'cost-anomaly':'💰','zombie-hunter':'🧟','security-posture':'🛡️','capacity-planner':'📊','event-analysis':'🔍','resiliency-gaps':'🏗️','tag-enforcer':'🏷️','lifecycle-tracker':'⏳','health-monitor':'🏥','quota-guardian':'📏','arch-diagram':'🏗️','costopt-intelligence':'img:/static/img/costopt-intelligence.svg'};
function getSkillIcon(skillName){const v=SKILL_ICONS[skillName]||'⚙️';if(v.startsWith('img:'))return '<img src="'+v.slice(4)+'" alt="" style="width:42px;height:42px">';return v;}
const REMEDIATION_PATTERNS = [
  {skill:'zombie-hunter',pattern:/^Unattached EBS:/},{skill:'zombie-hunter',pattern:/^Unused EIP:/},
  {skill:'zombie-hunter',pattern:/^Unused NAT GW:/},{skill:'zombie-hunter',pattern:/^Idle EC2:/},
  {skill:'zombie-hunter',pattern:/^Idle RDS:/},{skill:'security-posture',pattern:/^Open port .+ to 0\.0\.0\.0\/0:/},
  {skill:'security-posture',pattern:/^Public S3 bucket:/},{skill:'security-posture',pattern:/^Old access key:/},
  {skill:'resiliency-gaps',pattern:/^Single-AZ RDS:/},{skill:'resiliency-gaps',pattern:/^No backups: RDS/},
  {skill:'resiliency-gaps',pattern:/^No VPC Flow Logs:/},{skill:'capacity-planner',pattern:/^Underutilized ODCR:/},
  {skill:'tag-enforcer',pattern:/^Untagged EC2:/},{skill:'tag-enforcer',pattern:/^Untagged RDS:/},
  {skill:'tag-enforcer',pattern:/^Untagged S3:/},{skill:'tag-enforcer',pattern:/^Untagged Lambda:/},
  {skill:'lifecycle-tracker',pattern:/^Deprecated runtime:/},
  {skill:'lifecycle-tracker',pattern:/^EOL RDS engine:/},
];
function hasRemediation(f){return REMEDIATION_PATTERNS.some(p=>p.skill===f.skill&&p.pattern.test(f.title));}
function sortBySeverity(arr){return[...arr].sort((a,b)=>SEVERITY_ORDER.indexOf(a.severity)-SEVERITY_ORDER.indexOf(b.severity));}
function computeSummary(arr){return{total:arr.length,critical:arr.filter(f=>f.severity==='critical').length,impact:arr.reduce((s,f)=>s+(f.monthly_impact||0),0)};}

function renderSkillCards(skills, results, onRun, activeJobs, onCardClick) {
  activeJobs = activeJobs || {};
  const grid = document.createElement('div'); grid.className = 'cards-grid';
  for (const skill of skills) {
    const r = results[skill.name];
    const icon = getSkillIcon(skill.name);
    const running = !!activeJobs[skill.name];
    const name = skill.name.split('-').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join('-');
    const card = document.createElement('div'); card.className='card'; card.dataset.skill=skill.name; card.title=skill.description;
    card.innerHTML = `<span class="card-icon">${icon}</span>
      <div class="card-tooltip">${skill.description}</div>
      <div class="card-header"><div class="card-title">${name}</div><button class="btn btn-primary btn-sm run-btn" ${running?'disabled':''}>▶ Run</button></div>
      <div class="card-desc">${skill.description}</div>
      ${r&&r.error?`<div class="card-error">⚠ ${r.error}</div>`:''}
      ${r&&r.findings!==undefined&&!running?`<div class="card-stats"><div class="card-stat"><div class="card-stat-value">${r.findings.length}</div><div class="card-stat-label">Findings</div></div><div class="card-stat"><div class="card-stat-value">${['cost-anomaly','zombie-hunter'].includes(skill.name)?'$'+(r.total_impact||0).toLocaleString(undefined,{maximumFractionDigits:0}):['security-posture','resiliency-gaps','event-analysis','health-monitor'].includes(skill.name)?(r.critical_count||0):['tag-enforcer'].includes(skill.name)?r.findings.filter(f=>!f.resource_id).length||r.findings.length:['arch-diagram'].includes(skill.name)?(r.findings.length>0?Object.keys(r.findings[0].metadata?.resources||{}).length:0):r.findings.length}</div><div class="card-stat-label">${['cost-anomaly','zombie-hunter'].includes(skill.name)?'/month':['security-posture','resiliency-gaps','event-analysis','health-monitor'].includes(skill.name)?'Critical':['tag-enforcer'].includes(skill.name)?'Untagged':['lifecycle-tracker'].includes(skill.name)?'Deprecated':['quota-guardian'].includes(skill.name)?'At Risk':['arch-diagram'].includes(skill.name)?'Services':['capacity-planner'].includes(skill.name)?'Underused':'Issues'}</div></div></div>`:''}
      ${running?'<div class="card-loading"><span class="spinner"></span> Scanning...</div>':''}`;
    card.querySelector('.run-btn').addEventListener('click', async(e)=>{
      e.stopPropagation();
      const b=e.target; b.disabled=true;
      let ld=card.querySelector('.card-loading');
      if(!ld){ld=document.createElement('div');ld.className='card-loading';ld.innerHTML='<span class="spinner"></span> Scanning...';card.appendChild(ld);}
      try{await onRun(skill.name);}catch(e2){b.disabled=false;if(ld)ld.remove();}
    });
    if(onCardClick) card.addEventListener('click', ()=>onCardClick(skill.name));
    card.style.cursor='pointer';
    grid.appendChild(card);
  }
  return grid;
}

function renderSummaryBar(findings) {
  const s = computeSummary(findings);
  const div = document.createElement('div'); div.className='summary-bar';
  div.innerHTML = `<div class="summary-item"><div class="summary-value">${s.total}</div><div class="summary-label">Total Findings</div></div>
    <div class="summary-item"><div class="summary-value critical">${s.critical}</div><div class="summary-label">Critical</div></div>
    <div class="summary-item"><div class="summary-value impact">$${s.impact.toLocaleString(undefined,{maximumFractionDigits:0})}</div><div class="summary-label">Monthly Impact</div></div>`;
  return div;
}

function renderFilters(skills, onFilter) {
  const div = document.createElement('div'); div.className='filters';
  div.innerHTML = `<span class="filter-label">Severity:</span><select class="filter-select" id="sev-filter"><option value="">All</option>${SEVERITY_ORDER.map(s=>`<option value="${s}">${s}</option>`).join('')}</select>
    <span class="filter-label">Skill:</span><select class="filter-select" id="skill-filter"><option value="">All</option>${skills.map(s=>`<option value="${s.name}">${s.name}</option>`).join('')}</select>`;
  div.querySelector('#sev-filter').addEventListener('change',()=>onFilter());
  div.querySelector('#skill-filter').addEventListener('change',()=>onFilter());
  return div;
}
function getActiveFilters(){const s=document.getElementById('sev-filter'),k=document.getElementById('skill-filter');return{severity:s?s.value:'',skill:k?k.value:''};}
function filterFindings(arr,f){let r=arr;if(f.severity)r=r.filter(x=>x.severity===f.severity);if(f.skill)r=r.filter(x=>x.skill===f.skill);return r;}

function renderFindingsTable(findings, onRemediate) {
  if (!findings.length) { const e=document.createElement('div');e.className='empty-state';e.innerHTML='<h3>No findings</h3><p>Run a scan to see results</p>';return e; }
  const sorted = sortBySeverity(findings);
  const table = document.createElement('table'); table.className='findings-table';
  table.innerHTML = '<thead><tr><th>Sev</th><th>Finding</th><th>Region</th><th>Resource</th><th>Impact/mo</th><th>Action</th><th></th></tr></thead>';
  const tbody = document.createElement('tbody');
  for (const f of sorted) {
    const tr = document.createElement('tr');
    const canFix = hasRemediation(f);
    const isCost = f.skill==='cost-anomaly';
    const region = f.region||'';
    const resource = f.resource_id ? `<span class="resource-id" title="Click to copy">${f.resource_id}</span>` : (isCost&&f.description?`<span style="font-size:11px;color:var(--text-dim)">${f.description.substring(0,80)}</span>`:'');
    let action = f.recommended_action||'';
    if (isCost) {
      let svc=(f.metadata&&f.metadata.service)?f.metadata.service:'';
      if(!svc){const m=(f.title||'').match(/^(.+?):\s*\+/);if(m)svc=m[1].trim();}
      if(!svc){const m=(f.title||'').match(/New service detected:\s*(.+)/);if(m)svc=m[1].trim();}
      const ceBase='https://us-east-1.console.aws.amazon.com/costmanagement/home#/cost-explorer';
      let ceUrl=ceBase;
      if(svc){const filter=JSON.stringify([{"dimension":{"id":"Service","displayValue":"Service"},"operator":"INCLUDES","values":[{"value":svc,"displayValue":svc}]}]);ceUrl=`${ceBase}?chartStyle=STACK&costAggregate=unBlendedCost&excludeForecasting=false&filter=${encodeURIComponent(filter)}&granularity=Monthly&groupBy=%5B%22Service%22%5D&historicalRelativeRange=LAST_6_MONTHS&reportMode=STANDARD&showOnlyUncategorized=false&showOnlyUntagged=false&useNormalizedUnits=false`;}
      action = `${f.recommended_action||''} <a href="${ceUrl}" target="_blank" class="ce-link">↗ ${svc||'Cost Explorer'}</a>`;
    }
    if(isCost) tr.className='cost-anomaly-row';
    tr.innerHTML = `<td><span class="sev-badge sev-${f.severity}">${f.severity}</span></td><td>${f.title}</td><td>${region}</td><td>${resource}</td><td>${f.monthly_impact?'$'+f.monthly_impact.toLocaleString(undefined,{maximumFractionDigits:0}):'-'}</td><td>${action}</td><td>${canFix?'<button class="btn btn-danger btn-sm fix-btn">Fix It</button>':''}</td>`;
    const resEl=tr.querySelector('.resource-id');if(resEl)resEl.addEventListener('click',()=>{navigator.clipboard.writeText(f.resource_id);showToast('Copied!','success');});
    const fixBtn=tr.querySelector('.fix-btn');if(fixBtn)fixBtn.addEventListener('click',()=>onRemediate(f));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  // Check for arch-diagram mermaid findings
  for (const f of sorted) {
    if (f.skill === 'arch-diagram' && f.metadata && f.metadata.mermaid) {
      const diagramRow = document.createElement('tr');
      diagramRow.innerHTML = '<td colspan="7" style="padding:20px"><div class="mermaid-container"><pre class="mermaid">' + f.metadata.mermaid + '</pre></div></td>';
      tbody.appendChild(diagramRow);
      setTimeout(() => { try { mermaid.run({nodes: table.querySelectorAll('.mermaid')}); } catch(e) {} }, 100);
      break;
    }
  }
  return table;
}

function showRemediationModal(finding, onConfirm) {
  const overlay=document.getElementById('modal-overlay'); overlay.classList.remove('hidden');
  overlay.innerHTML=`<div class="modal"><div class="modal-title">Confirm Remediation</div><div class="modal-body"><p><strong>${finding.title}</strong></p><p>Resource: <code>${finding.resource_id}</code></p><p>Region: ${finding.region}</p><p>Action: ${finding.recommended_action}</p></div><div class="modal-actions"><button class="btn btn-ghost cancel-btn">Cancel</button><button class="btn btn-danger confirm-btn">Confirm Fix</button></div></div>`;
  overlay.querySelector('.cancel-btn').addEventListener('click',()=>overlay.classList.add('hidden'));
  overlay.querySelector('.confirm-btn').addEventListener('click',async()=>{const b=overlay.querySelector('.confirm-btn');b.disabled=true;b.textContent='Fixing...';try{const r=await onConfirm(finding);overlay.classList.add('hidden');showToast(r.success?r.message:`Failed: ${r.message}`,r.success?'success':'error');}catch(e){overlay.classList.add('hidden');showToast('Error: '+e.message,'error');}});
}
function showToast(msg,type){const t=document.getElementById('toast');t.textContent=msg;t.className=`toast ${type}`;setTimeout(()=>t.classList.add('hidden'),3000);}

function formatChatResponse(text) {
  if(!text)return'';
  let html=text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
  const lines=html.split('\n'); let result=''; let inList=false;
  for(const line of lines){const t=line.trim();if(t.match(/^[-*] /)||t.match(/^\d+\. /)){if(!inList){result+='<ul style="margin:2px 0 2px 18px;padding:0">';inList=true;}result+='<li style="margin:1px 0">'+t.replace(/^[-*] |^\d+\. /,'')+'</li>';}else{if(inList){result+='</ul>';inList=false;}if(t==='')continue;result+='<div style="margin:3px 0">'+t+'</div>';}}
  if(inList)result+='</ul>'; return result;
}

function renderOrgView(orgResults, onStartOrgScan) {
  const div=document.createElement('div');
  if(!orgResults){div.innerHTML=`<div class="empty-state"><h3>Org-Wide Scan</h3><p>Scan all accounts in your AWS Organization</p><button class="btn btn-primary" id="start-org-scan">Start Org Scan</button><div class="loading-overlay hidden" id="org-loading"><span class="spinner"></span> Scanning organization...</div></div>`;div.querySelector('#start-org-scan').addEventListener('click',async()=>{const b=div.querySelector('#start-org-scan'),l=div.querySelector('#org-loading');b.disabled=true;l.classList.remove('hidden');try{await onStartOrgScan();}finally{b.disabled=false;l.classList.add('hidden');}});return div;}
  const allF=[];for(const od of Object.values(orgResults.by_ou))for(const a of Object.values(od.accounts||{}))for(const sd of Object.values(a.skills||{}))allF.push(...(sd.findings||[]));
  div.appendChild(renderSummaryBar(allF));
  const tree=document.createElement('div');tree.className='org-tree';
  for(const[ouName,ouData]of Object.entries(orgResults.by_ou)){const accts=ouData.accounts||{};const oF=Object.values(accts).reduce((s,a)=>s+(a.findings_count||0),0);const oI=Object.values(accts).reduce((s,a)=>s+(a.monthly_impact||0),0);const oC=Object.values(accts).reduce((s,a)=>s+(a.critical_count||0),0);
    const g=document.createElement('div');g.className='ou-group';g.innerHTML=`<div class="ou-header"><span>📁 ${ouName} (${Object.keys(accts).length} accounts)</span><div class="ou-stats"><span>${oF} findings</span><span>${oC} critical</span><span>$${oI.toLocaleString(undefined,{maximumFractionDigits:0})}/mo</span></div></div><div class="ou-accounts hidden"></div>`;
    const hdr=g.querySelector('.ou-header'),ad=g.querySelector('.ou-accounts');hdr.addEventListener('click',()=>ad.classList.toggle('hidden'));
    for(const[aid,acct]of Object.entries(accts)){const sc=acct.error?'error':acct.critical_count>0?'sev-red':acct.findings_count>0?'sev-yellow':'sev-green';const row=document.createElement('div');row.className=`acct-row ${sc}`;row.innerHTML=acct.error?`<span>${acct.name} (${aid})</span><span style="color:var(--danger)">⚠ Role assumption failed</span>`:`<span>${acct.name} (${aid})</span><span>${acct.findings_count} findings | $${(acct.monthly_impact||0).toLocaleString(undefined,{maximumFractionDigits:0})}/mo</span>`;
      if(!acct.error)row.addEventListener('click',()=>{const ex=ad.querySelector(`.acct-findings[data-aid="${aid}"]`);if(ex){ex.remove();return;}const d=document.createElement('div');d.className='acct-findings';d.dataset.aid=aid;const af=[];for(const sd of Object.values(acct.skills||{}))af.push(...(sd.findings||[]));if(af.length)d.appendChild(renderFindingsTable(af,(f)=>showRemediationModal(f,(f)=>API.remediate(f))));else d.textContent='No findings';row.after(d);});
      ad.appendChild(row);}tree.appendChild(g);}
  div.appendChild(tree);return div;
}

function renderChatView(state) {
  const div=document.createElement('div');div.className='chat-container';
  div.innerHTML=`<div class="chat-messages" id="chat-messages"></div><div class="chat-input-bar"><textarea class="chat-input" id="chat-input" rows="1" placeholder="Ask about your findings or AWS environment..."></textarea><button class="btn btn-primary" id="chat-send">Send</button></div>`;
  const msgs=div.querySelector('#chat-messages'),inp=div.querySelector('#chat-input'),btn=div.querySelector('#chat-send');
  for(const msg of(state.chatMessages||[])){const el=document.createElement('div');el.className=`chat-msg ${msg.role}`;if(msg.role==='assistant'){el.innerHTML='<div class="msg-header"><img src="/static/img/ops-agent.svg" alt=""><span>AWS Ops Agent</span></div><div class="msg-body">'+formatChatResponse(msg.content)+'</div>';}else{el.textContent=msg.content;}msgs.appendChild(el);}
  async function send(){
    const text=inp.value.trim();if(!text)return;inp.value='';
    state.chatMessages=state.chatMessages||[];state.chatMessages.push({role:'user',content:text});
    const uel=document.createElement('div');uel.className='chat-msg user';uel.textContent=text;msgs.appendChild(uel);
    const typing=document.createElement('div');typing.className='chat-typing';typing.innerHTML='<span class="thinking-text">Thinking</span>';msgs.appendChild(typing);setTimeout(()=>{msgs.scrollTop=999999;},50);btn.disabled=true;
    try{
      const allF=Object.values(state.resultsBySkill||{}).flatMap(r=>r.findings||[]);
      const sRun=Object.keys(state.resultsBySkill||{});
      const sNot=(state.skills||[]).map(s=>s.name).filter(n=>!sRun.includes(n));
      const resp=await API.chat(text,allF.length?allF:null,sRun,sNot);
      typing.remove();
      let responseText=resp.response;
      if(text.toLowerCase().match(/^(yes|proceed|confirm|go ahead|do it|fix it)/)&&state._pendingFix){
        const fixMsg=document.createElement('div');fixMsg.className='chat-msg assistant';fixMsg.innerHTML='<div class="msg-header"><img src="/static/img/ops-agent.svg" alt=""><span>AWS Ops Agent</span></div><div class="msg-body">⏳ Executing remediation...</div>';msgs.appendChild(fixMsg);
        try{const result=await API.remediate(state._pendingFix);fixMsg.remove();responseText=result.success?'✅ '+result.message+'\\nRemediation successful. Re-run the scan to verify.':'❌ Failed: '+result.message;}catch(e){fixMsg.remove();responseText='❌ Error: '+e.message;}
        state._pendingFix=null;
      }
      const fixMatch=responseText.match(/Would you like me to proceed/i)||responseText.match(/Reply YES/i);
      if(fixMatch&&allF.length){for(const f of allF){if(f.resource_id&&responseText.includes(f.resource_id)){state._pendingFix=f;break;}}}
      state.chatMessages.push({role:'assistant',content:responseText});
      const ael=document.createElement('div');ael.className='chat-msg assistant';ael.innerHTML='<div class="msg-header"><img src="/static/img/ops-agent.svg" alt=""><span>AWS Ops Agent</span></div><div class="msg-body">'+formatChatResponse(responseText)+'</div>';msgs.appendChild(ael);
    }catch(e){typing.remove();const eel=document.createElement('div');eel.className='chat-msg error';eel.textContent='⚠ '+e.message;msgs.appendChild(eel);}
    finally{btn.disabled=false;setTimeout(()=>{msgs.scrollTop=999999;},50);}
  }
  btn.addEventListener('click',send);
  inp.addEventListener('keydown',(e)=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
  return div;
}
