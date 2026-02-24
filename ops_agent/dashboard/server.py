"""FastAPI server for the Ops Agent Dashboard."""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, validator

from ops_agent.core import SkillRegistry
from ops_agent.aws_client import get_regions, get_account_id, build_org_tree, assume_role_session
from ops_agent.dashboard.jobs import JobStore, ScanJobStatus
from ops_agent.dashboard.remediation import has_remediation, execute_remediation
from ops_agent.dashboard.chat import handle_chat, BedrockUnavailableError
from ops_agent.dashboard.security import (
    APIKeyMiddleware, RateLimiter, RateLimitMiddleware,
    SecurityHeadersMiddleware, AuditLogger,
    sanitize_chat_message, validate_findings_payload,
    MAX_CHAT_MESSAGE_LENGTH, MAX_FINDINGS_COUNT,
)
import ops_agent.skills  # auto-register skills

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class ScanRequest(BaseModel):
    regions: Optional[List[str]] = None
    profile: Optional[str] = None


class OrgScanRequest(BaseModel):
    role: str = "OrganizationAccountAccessRole"
    skill: Optional[str] = None
    regions: Optional[List[str]] = None
    profile: Optional[str] = None


class ScanJobResponse(BaseModel):
    job_id: str
    status: str


class SkillInfo(BaseModel):
    name: str
    description: str
    version: str


class RemediateRequest(BaseModel):
    finding: dict
    profile: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    findings: Optional[List[dict]] = None
    skills_run: Optional[List[str]] = None
    skills_not_run: Optional[List[str]] = None


def create_app(profile: Optional[str] = None, api_key: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="AWS Ops Agent Dashboard", version="0.3.0")
    job_store = JobStore()
    app.state.profile = profile
    app.state.job_store = job_store

    # --- Security: API key from param, env var, or disabled ---
    effective_api_key = api_key or os.environ.get("OPS_AGENT_API_KEY")

    # --- Security: Audit logger ---
    audit = AuditLogger()

    # --- Middleware stack (order matters: last added = first executed) ---

    # 1. CORS — restricted origins
    allowed_origins = os.environ.get("OPS_AGENT_CORS_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    # 2. Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Rate limiting
    rate_limiter = RateLimiter(
        requests_per_minute=int(os.environ.get("OPS_AGENT_RATE_LIMIT", "60")),
        burst=int(os.environ.get("OPS_AGENT_RATE_BURST", "15")),
    )
    app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)

    # 4. API key auth
    app.add_middleware(APIKeyMiddleware, api_key=effective_api_key)

    # --- Static files ---
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # --- Health check ---
    @app.get("/api/health")
    async def health():
        return {"status": "healthy", "version": "0.3.0", "skills": len(SkillRegistry.all())}

    @app.get("/", response_class=HTMLResponse)
    async def root():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return HTMLResponse(content=index.read_text())
        return HTMLResponse(content="<h1>Ops Agent Dashboard</h1>")

    @app.get("/api/skills")
    async def list_skills():
        return [
            {"name": s.name, "description": s.description, "version": s.version}
            for s in SkillRegistry.all().values()
        ]

    @app.post("/api/scan/{skill_name}")
    async def scan_skill(skill_name: str, req: ScanRequest = ScanRequest()):
        skill = SkillRegistry.get(skill_name)
        if not skill:
            valid = ", ".join(SkillRegistry.names())
            raise HTTPException(status_code=400, detail=f"Unknown skill: {skill_name}. Valid: [{valid}]")
        p = req.profile or app.state.profile
        regions = req.regions or get_regions(profile=p)
        job = job_store.create([skill_name])

        async def _run():
            job_store.update(job.id, status=ScanJobStatus.RUNNING)
            try:
                result = await asyncio.to_thread(skill.scan, regions, p)
                job_store.update(job.id, status=ScanJobStatus.COMPLETED, results=[result])
            except Exception as e:
                job_store.update(job.id, status=ScanJobStatus.FAILED, error=str(e))

        asyncio.create_task(_run())
        return {"job_id": job.id, "status": job.status.value}

    @app.post("/api/scan-all")
    async def scan_all(req: ScanRequest = ScanRequest()):
        skills = list(SkillRegistry.all().values())
        p = req.profile or app.state.profile
        regions = req.regions or get_regions(profile=p)
        job = job_store.create([s.name for s in skills])

        async def _run():
            job_store.update(job.id, status=ScanJobStatus.RUNNING)
            try:
                import concurrent.futures
                results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(skills)) as pool:
                    futures = {pool.submit(s.scan, regions, p): s.name for s in skills}
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            results.append(future.result())
                        except Exception as e:
                            from ops_agent.core import SkillResult
                            results.append(SkillResult(
                                skill_name=futures[future],
                                errors=[str(e)],
                            ))
                job_store.update(job.id, status=ScanJobStatus.COMPLETED, results=results)
            except Exception as e:
                job_store.update(job.id, status=ScanJobStatus.FAILED, error=str(e))

        asyncio.create_task(_run())
        return {"job_id": job.id, "status": job.status.value}

    @app.post("/api/org-scan")
    async def org_scan(req: OrgScanRequest = OrgScanRequest()):
        p = req.profile or app.state.profile

        if req.skill:
            skill = SkillRegistry.get(req.skill)
            if not skill:
                valid = ", ".join(SkillRegistry.names())
                raise HTTPException(status_code=400, detail=f"Unknown skill: {req.skill}. Valid: [{valid}]")

        skills_to_run = (
            [SkillRegistry.get(req.skill)] if req.skill
            else list(SkillRegistry.all().values())
        )
        skill_names = [s.name for s in skills_to_run]
        job = job_store.create(skill_names)

        async def _run():
            job_store.update(job.id, status=ScanJobStatus.RUNNING)
            try:
                org_tree = await asyncio.to_thread(build_org_tree, p)
                regions = req.regions or await asyncio.to_thread(get_regions, None, p)
                mgmt_id = await asyncio.to_thread(get_account_id, p)

                ou_results = {}

                for ou_name, ou_info in org_tree.items():
                    ou_accounts = {}
                    for acct in ou_info["accounts"]:
                        aid = acct["id"]
                        aname = acct["name"]
                        acct_data = {
                            "name": aname, "findings_count": 0,
                            "critical_count": 0, "monthly_impact": 0.0,
                            "skills": {}, "error": None,
                        }
                        try:
                            creds = await asyncio.to_thread(
                                assume_role_session, aid, req.role, p
                            )
                            # Use boto3 session with temp creds instead of env vars
                            import boto3
                            member_session = boto3.Session(
                                aws_access_key_id=creds["AccessKeyId"],
                                aws_secret_access_key=creds["SecretAccessKey"],
                                aws_session_token=creds["SessionToken"],
                            )

                            for s in skills_to_run:
                                # Pass profile=None so skills use default session
                                # We need to temporarily set env for boto3 default session
                                # TODO: Refactor skills to accept a session object
                                import os
                                old_env = {}
                                env_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]
                                for k in env_keys:
                                    old_env[k] = os.environ.get(k)
                                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                                os.environ["AWS_SESSION_TOKEN"] = creds["SessionToken"]
                                try:
                                    result = await asyncio.to_thread(
                                        s.scan, regions, None, aid
                                    )
                                finally:
                                    for k in env_keys:
                                        if old_env[k] is None:
                                            os.environ.pop(k, None)
                                        else:
                                            os.environ[k] = old_env[k]

                                for f in result.findings:
                                    f.account_id = aid
                                acct_data["skills"][s.name] = {
                                    "findings_count": len(result.findings),
                                    "monthly_impact": result.total_impact,
                                    "findings": [f.to_dict() for f in result.findings],
                                }
                                acct_data["findings_count"] += len(result.findings)
                                acct_data["critical_count"] += result.critical_count
                                acct_data["monthly_impact"] += result.total_impact

                        except Exception as e:
                            acct_data["error"] = f"Failed to assume role {req.role} in {aid}: {str(e)}"

                        ou_accounts[aid] = acct_data
                    ou_results[ou_name] = {"accounts": ou_accounts}

                # Scan management account
                mgmt_data = {
                    "name": "Management Account", "findings_count": 0,
                    "critical_count": 0, "monthly_impact": 0.0,
                    "skills": {}, "error": None,
                }
                for s in skills_to_run:
                    result = await asyncio.to_thread(s.scan, regions, p, mgmt_id)
                    for f in result.findings:
                        f.account_id = mgmt_id
                    mgmt_data["skills"][s.name] = {
                        "findings_count": len(result.findings),
                        "monthly_impact": result.total_impact,
                        "findings": [f.to_dict() for f in result.findings],
                    }
                    mgmt_data["findings_count"] += len(result.findings)
                    mgmt_data["critical_count"] += result.critical_count
                    mgmt_data["monthly_impact"] += result.total_impact

                ou_results.setdefault("Management", {"accounts": {}})
                ou_results["Management"]["accounts"][mgmt_id] = mgmt_data

                total_findings = 0
                total_impact = 0.0
                total_critical = 0
                for ou_data in ou_results.values():
                    for acct_data in ou_data["accounts"].values():
                        total_findings += acct_data["findings_count"]
                        total_impact += acct_data["monthly_impact"]
                        total_critical += acct_data["critical_count"]

                org_result = {
                    "by_ou": ou_results,
                    "summary": {
                        "total_findings": total_findings,
                        "total_monthly_impact": round(total_impact, 2),
                        "total_critical": total_critical,
                    },
                }
                job_store.update(job.id, status=ScanJobStatus.COMPLETED, org_results=org_result)

            except Exception as e:
                job_store.update(job.id, status=ScanJobStatus.FAILED, error=str(e))

        asyncio.create_task(_run())
        return {"job_id": job.id, "status": job.status.value}

    @app.post("/api/remediate")
    async def remediate(req: RemediateRequest, request: Request):
        p = req.profile or app.state.profile
        if not has_remediation(req.finding):
            raise HTTPException(status_code=400, detail="No remediation available for this finding type")
        client_ip = request.client.host if request.client else "unknown"
        result = await asyncio.to_thread(execute_remediation, req.finding, p)
        # Audit log every remediation attempt
        audit.log_remediation(
            action=result.action,
            resource_id=result.finding_id,
            region=req.finding.get("region", "unknown"),
            skill=req.finding.get("skill", "unknown"),
            success=result.success,
            message=result.message,
            client_ip=client_ip,
        )
        return {
            "success": result.success,
            "finding_id": result.finding_id,
            "action": result.action,
            "message": result.message,
            "timestamp": result.timestamp,
        }

    @app.post("/api/chat")
    async def chat(req: ChatRequest, request: Request):
        p = app.state.profile
        client_ip = request.client.host if request.client else "unknown"
        # Validate and sanitize input
        try:
            clean_message = sanitize_chat_message(req.message)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        clean_findings = validate_findings_payload(req.findings)
        audit.log_chat(client_ip, len(clean_message))
        try:
            response = await asyncio.to_thread(
                handle_chat, clean_message, clean_findings, p,
                req.skills_run, req.skills_not_run,
            )
            return {"response": response}
        except BedrockUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return {
            "job_id": job.id, "status": job.status.value,
            "skill_names": job.skill_names,
            "created_at": job.created_at, "completed_at": job.completed_at,
            "error": job.error,
        }

    @app.get("/api/jobs/{job_id}/results")
    async def get_job_results(job_id: str):
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        if job.status != ScanJobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Job not completed. Status: {job.status.value}")
        if job.org_results:
            return job.org_results
        if job.results:
            return [_serialize_result(r) for r in job.results]
        return []

    def _serialize_result(result):
        return {
            "skill_name": result.skill_name,
            "findings": [f.to_dict() for f in result.findings],
            "duration_seconds": result.duration_seconds,
            "accounts_scanned": result.accounts_scanned,
            "regions_scanned": result.regions_scanned,
            "errors": result.errors,
            "total_impact": result.total_impact,
            "critical_count": result.critical_count,
        }

    return app
