# DEMO TODAY

## One-command startup options

### Windows (local)
1. `.\run.ps1 serve` (web app + API at `http://127.0.0.1:8000`)
2. In a second terminal: `.\run.ps1 worker` (async queue worker)

### Docker (recommended for clean demo)
1. `docker compose up --build`
2. App: `http://127.0.0.1:8000`
3. Worker runs as `worker` service and processes queue jobs continuously.

## 3-5 minute demo script

1. **Open health endpoint**  
   Visit `http://127.0.0.1:8000/api/health` and call out:
   - model artifact readiness
   - queue backlog
   - worker heartbeat

2. **Show synchronous analysis (existing core)**  
   Open dashboard `http://127.0.0.1:8000/#dashboard`, click **Load sample & run**, and show:
   - risk rings
   - summary
   - signal cards

3. **Show asynchronous pipeline (new POC)**  
   In **Batch / Queue demo**:
   - submit a job (title/body or URL)
   - show returned/visible job id
   - refresh/poll status transitioning `pending -> processing -> succeeded`
   - show final summary and top signals in queue list

4. **Show enterprise hooks quickly**  
   - org/tenant id in queue submission
   - request/job lifecycle logging in server output
   - worker heartbeat and backlog in `/api/health`

5. **Close with scale path**  
   Mention this queue model is intentionally minimal and can migrate to Celery + Redis/Kafka without changing client payload shape.

## Investor talking points

- **Problem:** News/editorial teams need faster triage under high content volume without automating final editorial judgment.
- **Differentiation:** One API contract powers both synchronous scoring and asynchronous queue workflows with explainable outputs (summary + signals).
- **Production trajectory:** Tenant-aware job records, lifecycle audit fields, queue health, and worker process pattern provide a clear upgrade path to distributed workers and managed datastores.
