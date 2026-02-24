/* Main app — routing, state management */
const state = {
  skills: [],
  resultsBySkill: {},
  orgResults: null,
  chatMessages: [],
  activeJobs: {},
  scanAllJobId: null,
  _pendingFix: null,
  selectedSkill: null
};

const COST_SKILLS = ['cost-anomaly', 'zombie-hunter', 'costopt-intelligence'];

async function startBackgroundPoll(jobId, skillNames, isScanAll) {
  for (let i = 0; i < 150; i++) {
    try {
      const status = await API.getJobStatus(jobId);
      if (status.status === 'completed') {
        const results = await API.getJobResults(jobId);
        if (Array.isArray(results)) { for (const r of results) state.resultsBySkill[r.skill_name] = r; }
        if (isScanAll) state.scanAllJobId = null;
        for (const n of skillNames) delete state.activeJobs[n];
        if (!isScanAll && skillNames.length === 1) state.selectedSkill = skillNames[0];
        const h = location.hash || '#/';
        if (h === '#/' || h === '') renderSkillsPage(document.getElementById('app'));
        return;
      }
      if (status.status === 'failed') {
        if (isScanAll) state.scanAllJobId = null;
        for (const n of skillNames) delete state.activeJobs[n];
        showToast('Scan failed: ' + (status.error||'Unknown'), 'error');
        return;
      }
    } catch(e) {}
    await new Promise(r => setTimeout(r, 2000));
  }
}

async function init() {
  state.skills = await API.getSkills();
  window.addEventListener('hashchange', route);
  route();
}

function route() {
  const hash = location.hash || '#/';
  document.querySelectorAll('.nav-link').forEach(l => l.classList.toggle('active', l.getAttribute('href') === hash));
  const app = document.getElementById('app');
  app.innerHTML = '';
  if (hash === '#/org') renderOrgPage(app);
  else if (hash === '#/chat') renderChatPage(app);
  else renderSkillsPage(app);
}

function renderSkillsPage(app) {
  app.innerHTML = '';
  // Run All button
  const btn = document.createElement('button');
  btn.className = 'btn btn-primary btn-run-all';
  btn.textContent = state.scanAllJobId ? '\u23f3 Scanning...' : '\u25b6 Run All Skills';
  btn.disabled = !!state.scanAllJobId;
  btn.addEventListener('click', async () => {
    btn.disabled = true; btn.textContent = '\u23f3 Scanning...';
    try {
      const job = await API.scanAll();
      state.scanAllJobId = job.job_id;
      const names = state.skills.map(s => s.name);
      for (const n of names) state.activeJobs[n] = job.job_id;
      app.querySelectorAll('.card').forEach(c => {
        const b = c.querySelector('.run-btn'); if(b) b.disabled = true;
        let ld = c.querySelector('.card-loading');
        if(!ld){ld=document.createElement('div');ld.className='card-loading';ld.innerHTML='<span class="spinner"></span> Scanning...';c.appendChild(ld);}
      });
      startBackgroundPoll(job.job_id, names, true);
    } catch(e) { showToast('Failed: '+e.message,'error'); btn.disabled=false; btn.textContent='\u25b6 Run All Skills'; }
  });
  app.appendChild(btn);

  // Skill cards — clicking shows that skill's results
  app.appendChild(renderSkillCards(state.skills, state.resultsBySkill, async (name) => {
    try {
      const job = await API.scanSkill(name);
      state.activeJobs[name] = job.job_id;
      const card = app.querySelector('.card[data-skill="'+name+'"]');
      if(card){const b=card.querySelector('.run-btn');if(b)b.disabled=true;let ld=card.querySelector('.card-loading');if(!ld){ld=document.createElement('div');ld.className='card-loading';ld.innerHTML='<span class="spinner"></span> Scanning...';card.appendChild(ld);}}
      startBackgroundPoll(job.job_id, [name], false);
    } catch(e) { showToast('Failed: '+e.message,'error'); }
  }, state.activeJobs, function(skillName) {
    // Card click handler — show this skill's results
    state.selectedSkill = skillName;
    showSkillResults(app, skillName);
  }));

  // Results area
  const resultsDiv = document.createElement('div');
  resultsDiv.id = 'skill-results';
  app.appendChild(resultsDiv);

  // If a skill was previously selected, show its results
  if (state.selectedSkill) {
    showSkillResults(app, state.selectedSkill);
  }
}

function showSkillResults(app, skillName) {
  const resultsDiv = document.getElementById('skill-results');
  if (!resultsDiv) return;
  resultsDiv.innerHTML = '';

  const r = state.resultsBySkill[skillName];
  if (!r) {
    resultsDiv.innerHTML = '<div class="empty-state"><h3>' + skillName + '</h3><p>This skill has not been run yet. Click Run to scan.</p></div>';
    return;
  }

  // Skill header
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px';
  const displayName = skillName.split('-').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join('-');
  header.innerHTML = '<h3 style="font-size:18px;font-weight:700;color:var(--text-bright)">' + displayName + ' Results</h3>';
  resultsDiv.appendChild(header);

  const findings = r.findings || [];
  if (!findings.length) {
    resultsDiv.innerHTML += '<div class="empty-state"><h3>No findings</h3><p>All clear for ' + displayName + '</p></div>';
    return;
  }

  // Summary — only show cost for cost-related skills
  const showCost = COST_SKILLS.includes(skillName);
  const summary = computeSummary(findings);
  const sumDiv = document.createElement('div');
  sumDiv.className = 'summary-bar';
  sumDiv.innerHTML = '<div class="summary-item"><div class="summary-value">' + summary.total + '</div><div class="summary-label">Findings</div></div>' +
    '<div class="summary-item"><div class="summary-value critical">' + summary.critical + '</div><div class="summary-label">Critical</div></div>' +
    (showCost ? '<div class="summary-item"><div class="summary-value impact">$' + summary.impact.toLocaleString(undefined,{maximumFractionDigits:0}) + '</div><div class="summary-label">Monthly Impact</div></div>' : '');
  resultsDiv.appendChild(sumDiv);

  // Findings table
  resultsDiv.appendChild(renderFindingsTable(findings, function(f) {
    showRemediationModal(f, function(finding) { return API.remediate(finding); });
  }));
}

function renderOrgPage(app) {
  app.appendChild(renderOrgView(state.orgResults, async () => {
    const job = await API.orgScan('OrganizationAccountAccessRole');
    const results = await API.pollJob(job.job_id);
    state.orgResults = results;
    const a = document.getElementById('app');
    a.innerHTML = '';
    renderOrgPage(a);
  }));
}

function renderChatPage(app) {
  app.appendChild(renderChatView(state));
}

init();
