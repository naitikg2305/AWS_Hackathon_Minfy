# Deploying the agent to Amazon Bedrock AgentCore (Minfy R&D account)

Deployed 2026-10-19 by Naitik into the **Minfy R&D** account (AWS CLI profile `minfy-rnd`, region `us-east-1`).
The older ARN in `src/app/adapters/agentcore_agent.py` pointed at the hackathon lab account, which we no longer use.

## What is deployed (and why it is cheap)

| Resource | Purpose | Cost note |
| --- | --- | --- |
| AgentCore Runtime `pipelineleakagent_pipeline_leak_agent` | Runs `agentcore-deploy/pipelineleakagent/app/pipeline_leak_agent/main.py` (Strands agent, 6 tools) | Consumption-based: billed per vCPU-second and GB-second only while a session is active. $0 when idle. |
| IAM execution role + policy | Lets the runtime call Bedrock `InvokeModel` and write logs | Free |
| CDK bootstrap stack `CDKToolkit` | S3 bucket holding the ~75 MB code zip, empty ECR repo, deploy roles | Cents per month for S3 storage |
| Bedrock Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) | The LLM | **This is the real cost.** Pay per token, roughly a few cents per full 3-phase investigation. |

Cost-minimizing choices made in `agentcore/agentcore.json`:

- `build: CodeZip` — no CodeBuild, no ECR image builds, no Docker.
- `networkMode: PUBLIC` — no VPC, NAT gateway, or ENIs.
- `instrumentation.enableOtel: false` — no OpenTelemetry traces shipped to CloudWatch / X-Ray (Transaction Search costs money). Runtime stdout logs still land in CloudWatch Logs.
- `lifecycleConfiguration` — idle session timeout 300 s, max lifetime 1800 s, so the memory-seconds meter stops quickly after a demo.
- No AgentCore Memory, Gateway, Evaluators, Online Evals, or Knowledge Base. The 7 CSVs the tools need are packaged inside the zip, so there is no S3/Athena/DynamoDB read path.
- The Streamlit UI is **not** hosted. Run it locally with `AGENT_MODE=agentcore`; hosting it would be the only always-on cost.

Biggest remaining lever: set the runtime env var `MODEL_ID` to `us.anthropic.claude-haiku-4-5-20251001-v1:0` (about 3x cheaper per token than Sonnet 4.5). The agent was validated 20/20 on Sonnet 4.5, so re-run the labeled events before switching for a demo.

## Redeploying

```bash
# one-time
npm install -g @aws/agentcore          # CLI (v0.31.x used here)
export AWS_PROFILE=minfy-rnd AWS_REGION=us-east-1
aws sts get-caller-identity             # must show the minfytech.com IAM user

cd agentcore-deploy/pipelineleakagent

# aws-targets.json is gitignored (contains the account ID). Recreate it:
ACCT=$(aws sts get-caller-identity --query Account --output text)
printf '[{"name":"default","account":"%s","region":"us-east-1"}]\n' "$ACCT" > agentcore/aws-targets.json

# the data CSVs are gitignored inside the package; copy them in
mkdir -p app/pipeline_leak_agent/data && cp ../../data/*.csv app/pipeline_leak_agent/data/

agentcore validate
agentcore deploy -y
agentcore status
```

## Invoking

```bash
export AWS_PROFILE=minfy-rnd
agentcore invoke "Analyze event FP-001: pressure anomaly at ST-03 around 2026-01-15T06:00:00. Leak or false positive?"
agentcore logs            # CloudWatch logs for the runtime
```

From the Streamlit UI (local):

```bash
export AWS_PROFILE=minfy-rnd AGENT_MODE=agentcore
export AGENTCORE_RUNTIME_ARN=<see below>
streamlit run src/app/streamlit_app.py --server.port 3000
```

## Tearing down

```bash
export AWS_PROFILE=minfy-rnd
cd agentcore-deploy/pipelineleakagent
agentcore remove agent --name pipeline_leak_agent && agentcore deploy -y   # deletes the runtime + role
# optional: aws cloudformation delete-stack --stack-name CDKToolkit (after emptying its S3 bucket)
```

## Public demo URL (Streamlit on one small EC2 box)

Added 2026-10-19. Cheapest AWS-native way to get a shareable link that can call the runtime with an IAM role instead of stored keys. No login for visitors.

| Resource | Cost |
| --- | --- |
| EC2 `t4g.micro` (Graviton, 1 GB RAM + 2 GB swap), Amazon Linux 2023 | ~$0.0084/h, ~$6/mo if left on |
| Public IPv4 (Elastic IP, so the URL survives stop/start) | ~$3.65/mo |
| 8 GB gp3 root volume | ~$0.64/mo |
| IAM role `pipeline-leak-ui-ec2-role` (InvokeAgentRuntime on our one runtime + SSM), security group tcp/80 | free |

```bash
cd agentcore-deploy/ui-ec2
AWS_PROFILE=minfy-rnd ./setup-ui-infra.sh   # one-time: IAM role, instance profile, security group
AWS_PROFILE=minfy-rnd ./deploy-ui.sh        # launches the box, prints http://<ip>/ ; app is up ~4 min later
```

The box clones `main` from GitHub and runs `streamlit run src/app/streamlit_app.py` on port 80 as a systemd service with `AGENT_MODE=agentcore`. Push to `main`, then run `sudo update-ui` on the box (via `aws ssm start-session --target <instance-id>`; there is no SSH port) to pick up changes.

Stop the instance between demo days to stop compute billing; the URL stays the same when you start it again. Optional: set `APP_PASSWORD=...` in `/etc/pipeline-leak-ui.env` and restart the service to put a shared access code in front of it (anyone with the open URL can trigger Bedrock calls).
