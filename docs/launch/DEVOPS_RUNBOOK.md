# DevOps Runbook & Incident Response

## 1. System Architecture Overview
The SageMaster Telegram Signal Copier uses a hybrid serverless architecture. It consists of a FastAPI backend and a persistent Telegram Listener worker hosted on **Railway**, a Serverless PostgreSQL database on **Neon**, and event-driven workflows managed by **Upstash QStash** and **Upstash Workflow**. The system connects to the Telegram MTProto API via the Telethon library.

## 2. Monitoring & Alerting

### 2.1 Key Metrics to Monitor (Datadog/Prometheus)
- **Telegram Connection Status**: Number of active MTProto sessions vs. total configured users. A sudden drop indicates a potential Telegram API ban or network issue.
- **Parsing Latency**: The time taken by the OpenAI API to return a parsed signal. Alert if the 95th percentile exceeds 3 seconds.
- **Webhook Delivery Success Rate**: The percentage of HTTP 200 responses from the SageMaster API. Alert if the success rate drops below 95% over a 5-minute window.
- **Queue Depth**: The number of pending messages in Upstash QStash. Alert if the queue depth exceeds 500.

### 2.2 Alert Thresholds
- **Warning**: Parsing latency > 3s OR Webhook success rate < 95%. (Action: Investigate during business hours).
- **Critical**: Webhook success rate < 80% OR QStash DLQ (Dead Letter Queue) > 100 OR Database compute > 90%. (Action: Page on-call engineer immediately).

## 3. Incident Response Procedures

### Incident: High Webhook Failure Rate (SageMaster API Errors)
**Symptoms**: Alerts firing for webhook success rate < 80%. Logs show HTTP 5xx errors from `api.sagemaster.io`.
**Action Plan**:
1. Check the SageMaster core platform status page.
2. Upstash Workflow will automatically retry failed webhook dispatches with exponential backoff.
3. If the core platform is down for an extended period, messages will eventually move to the QStash Dead Letter Queue (DLQ).
4. Once the core platform recovers, manually replay the messages from the QStash DLQ via the Upstash Console.

### Incident: Telegram IP Block on Railway
**Symptoms**: The Telegram Listener worker logs show continuous connection timeouts or `ConnectionError` when attempting to connect to Telegram MTProto.
**Action Plan**:
1. This is a known issue where Telegram blocks shared PaaS IP ranges.
2. Deploy the Railway Cloudflare Worker Proxy workaround.
3. Update the `TELEGRAM_PROXY_URL` environment variable in Railway to route MTProto traffic through the Cloudflare proxy.
4. Restart the Telegram Listener worker.

### Incident: OpenAI API Rate Limits or Outage
**Symptoms**: Parsing latency spikes, or logs show `429 Too Many Requests` or `500 Internal Server Error` from OpenAI.
**Action Plan**:
1. Check the OpenAI status page.
2. If it's a rate limit issue, verify the current tier limits and request an increase if necessary.
3. If it's an outage, the system will automatically fall back to the regex parser (if implemented) or mark signals as `failed`. Communicate the degraded service to users via an in-app banner.

### Incident: Telegram API Flood Wait Errors
**Symptoms**: Logs show `FloodWaitError` from Telethon during user authentication or channel monitoring.
**Action Plan**:
1. This occurs when the system makes too many requests to Telegram too quickly.
2. The Telethon client should automatically handle `FloodWaitError` by sleeping for the required duration.
3. If the wait time is excessive (e.g., > 24 hours), it may indicate the application's API ID is being throttled. Contact Telegram support. Ensure the system is strictly using event listeners (`@client.on`) and not polling.

## 4. Database Maintenance
- **Log Rotation**: The `signal_logs` table will grow rapidly. Implement a cron job to archive logs older than 30 days to cold storage (e.g., AWS S3) and delete them from the active database to maintain query performance.
