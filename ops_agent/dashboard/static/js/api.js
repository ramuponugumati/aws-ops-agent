/* API client */
const API = {
  async getSkills() {
    return (await fetch('/api/skills')).json();
  },
  async scanSkill(name, regions) {
    return (await fetch(`/api/scan/${name}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({regions:regions||null})})).json();
  },
  async scanAll(regions) {
    return (await fetch('/api/scan-all', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({regions:regions||null})})).json();
  },
  async orgScan(role, skill, regions) {
    return (await fetch('/api/org-scan', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({role, skill:skill||null, regions:regions||null})})).json();
  },
  async getJobStatus(jobId) {
    return (await fetch(`/api/jobs/${jobId}`)).json();
  },
  async getJobResults(jobId) {
    return (await fetch(`/api/jobs/${jobId}/results`)).json();
  },
  async remediate(finding) {
    return (await fetch('/api/remediate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({finding})})).json();
  },
  async chat(message, findings, skillsRun, skillsNotRun) {
    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message, findings:findings||null, skills_run:skillsRun||null, skills_not_run:skillsNotRun||null})});
    if (r.status === 503) { const d = await r.json(); throw new Error(d.detail||'Bedrock unavailable'); }
    if (!r.ok) { const d = await r.json(); throw new Error(d.detail||'Chat error'); }
    return r.json();
  },
  async pollJob(jobId) {
    for (let i = 0; i < 150; i++) {
      const s = await this.getJobStatus(jobId);
      if (s.status === 'completed') return await this.getJobResults(jobId);
      if (s.status === 'failed') throw new Error(s.error || 'Scan failed');
      await new Promise(r => setTimeout(r, 2000));
    }
    throw new Error('Scan timed out');
  }
};
