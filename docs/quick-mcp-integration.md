# How Amazon Quick would connect to the leak-detection agent over MCP

Written 2026-10-21 (Naitik). **Status: the MCP server IS built and deployed** (runtime `pipeline_leak_mcp`,
IAM auth, see `docs/deploy-agentcore.md` → "MCP server"). **Amazon Quick is NOT connected and not enabled**, by
decision (cost). This doc is the runbook for the day someone wants to connect Quick: everything in Section 2 is
done; Section 3 or 4 is what remains.

## 1. The two sides

```
 Amazon Quick (business user)                         AWS account (ours)
 ┌──────────────────────────────┐                     ┌─────────────────────────────────────────────┐
 │ Chat agent ("Pipeline Ops")  │   MCP over HTTPS    │ MCP endpoint                                │
 │   └─ Action: "Leak Agent"    │ ──────────────────▶ │   tool: investigate_pipeline_event(...)     │
 │        (MCP integration)     │   OAuth 2.0 token   │   → runs the Strands agent → verdict text   │
 └──────────────────────────────┘                     └─────────────────────────────────────────────┘
```

- **Quick side.** Quick ships an MCP *client*. You register an MCP server as an **Action integration**
  (Integrations → Actions → "Model Context Protocol"), then **link that action to a chat agent**. When a user asks
  the chat agent a question, Quick's model reads the tool descriptions and decides whether to call our tool.
  Supported transports: **streamable HTTP** and **SSE**. Supported auth: **3-legged OAuth** (per-user),
  **2-legged OAuth** (service / client-credentials), or **none**; OAuth 2.0 Dynamic Client Registration is also
  supported.
- **Our side.** Something that speaks MCP over streamable HTTP and accepts an OAuth 2.0 bearer token.
  AgentCore gives two ways to get that, below.

The one hard rule: **Quick will not sign requests with AWS SigV4.** Our current runtime uses the `AWS_IAM`
authorizer, so Quick cannot call it. Whatever we expose must be OAuth-protected (or open, which we won't do).

## 2. What we expose: one tool, not six (DONE — `agentcore-deploy/pipelineleakagent/app/pipeline_leak_agent/mcp_server.py`)

Expose the *agent* as a single MCP tool rather than the six raw tools:

```
investigate_pipeline_event(event_id?: str, station_id: str, start_time: str, end_time: str) -> str
  Returns the agent's answer: "CLASSIFICATION: LEAK|FALSE POSITIVE", "SEVERITY: ...", evidence chain,
  response recommendation, compliance status, draft NRC notification.
```

Why: the 20/20 result lives in *our* system prompt. If Quick's chat agent called `query_scada`,
`check_operational_context` etc. directly, Quick's model would be making the leak call with its own prompting,
and we would have to re-validate inside Quick. One tool keeps the validated behavior intact and gives a
business user a one-question answer. (Optionally add a second read-only tool, `list_recent_alarms()`, so a
user can ask "what happened last night?" without knowing station IDs.)

Implementation sketch (new file `agentcore-deploy/pipelineleakagent/app/pipeline_leak_mcp/main.py`):

```python
from mcp.server.fastmcp import FastMCP
from strands import Agent
from model.load import load_model
from tools import (query_scada, check_operational_context, locate_leak,
                   get_segment_risk_profile, lookup_operating_envelope, get_regulatory_guidance)
from prompt import SYSTEM_PROMPT   # move the prompt out of main.py so both entrypoints share it

mcp = FastMCP(host="0.0.0.0", port=8000, stateless_http=True)   # stateless_http is required on AgentCore Runtime

@mcp.tool()
def investigate_pipeline_event(station_id: str, start_time: str, end_time: str, event_id: str = "") -> str:
    """Classify a pipeline pressure/flow anomaly as LEAK or FALSE POSITIVE with cited evidence,
    isolation recommendation and PHMSA/NRC reporting status. Times are ISO-8601, e.g. 2026-01-27T23:40:00."""
    agent = Agent(model=load_model(), system_prompt=SYSTEM_PROMPT, tools=[query_scada, check_operational_context,
                  locate_leak, get_segment_risk_profile, lookup_operating_envelope, get_regulatory_guidance])
    prompt = (f"Analyze event {event_id or 'unlabeled'}: pressure anomaly at station {station_id} between "
              f"{start_time} and {end_time}. Is this a real leak or a false positive? Follow the full 3-phase workflow.")
    return str(agent(prompt))

mcp.run(transport="streamable-http")
```

In `agentcore.json` this is the second runtime `pipeline_leak_mcp`: `"protocol": "MCP"`, same `codeLocation`
and bundled data as the HTTP runtime, same cost knobs (CodeZip, PUBLIC, OTel off, 5/30 min lifecycle). The
system prompt moved to `prompt.py` so both entrypoints share it. Smoke test: `src/tests/smoke_mcp_runtime.py`.

## 3. Path A (cheapest): Runtime with a JWT authorizer, Quick calls it directly — TO DO when Quick is wanted

```
Quick ──(Bearer JWT from Cognito, client-credentials)──▶ AgentCore Runtime [protocol MCP, authorizer CUSTOM_JWT]
```

1. **Cognito user pool** with a *resource server* (identifier e.g. `leak-agent`, custom scope `invoke`) and an
   **app client with a client secret, client-credentials grant** (machine-to-machine). Note client ID, secret,
   and the token URL `https://<pool-domain>.auth.us-east-1.amazoncognito.com/oauth2/token`.
2. **Runtime config** (`agentcore.json` → the MCP runtime):
   `"authorizerType": "CUSTOM_JWT"`, `authorizerConfiguration` with the pool's discovery URL
   (`https://cognito-idp.us-east-1.amazonaws.com/<pool-id>/.well-known/openid-configuration`) and the app
   client ID in `allowedClients`. Deploy with `agentcore deploy -y`.
3. **Endpoint URL** Quick will call:
   `https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<URL-encoded runtime ARN>/invocations?qualifier=DEFAULT`
4. **In Quick:** Integrations → Actions → Model Context Protocol → name, description, that endpoint →
   Authenticate → **Service authentication** (2LO) → client ID, client secret, token URL, scope `leak-agent/invoke`
   → Create and continue. Quick runs `listTools`; wait until the action shows Available.
5. **Attach to a chat agent:** open the chat agent → Actions → Link Actions → pick the integration →
   "Test action APIs" with a known event (e.g. ST-03, 2026-01-27T23:40 to 2026-01-28T00:25) → then ask in chat.

Cost: Cognito is free at this scale; the MCP runtime bills only while a call is running (same as today); the
Bedrock tokens are the same as a UI click. No new always-on cost. This path is the AgentCore-documented way to
put OAuth in front of a runtime, but **I have not tested Quick against a Runtime directly**; AWS's own
walkthrough goes through Gateway (Path B). Try A first, fall back to B.

## 4. Path B (AWS-documented): AgentCore Gateway in front — alternative, TO DO

```
Quick ──(JWT, inbound Cognito pool)──▶ AgentCore Gateway ──(OAuth client via AgentCore Identity, outbound pool)──▶ Runtime (MCP)
```

What Gateway adds: a stable MCP URL independent of the runtime ARN, central tool allow/deny, and the ability to
hang *more* targets (a Lambda, an OpenAPI spec, another runtime) behind the same endpoint later. AWS's blog
"Connect an AgentCore Runtime hosted MCP server to Amazon Quick" is exactly this shape.

Steps, condensed from that post:

1. Deploy the MCP runtime (Section 2) — it can keep `AWS_IAM` auth because only Gateway calls it.
2. **IAM role for the Gateway** (trust `bedrock-agentcore.amazonaws.com`) allowing
   `bedrock-agentcore:InvokeAgentRuntime` on the runtime ARN and its endpoints, plus
   `secretsmanager:GetSecretValue` for the outbound client secret.
3. **Inbound Cognito pool** (Quick → Gateway): resource server with scope `invoke`, app client; record client
   ID, secret, discovery URL.
4. **Outbound Cognito pool** (Gateway → Runtime): same shape; register it as an **OAuth client in AgentCore
   Identity** (discovery URL + client ID + secret).
5. **Create the Gateway** with inbound auth = JWT (inbound discovery URL + allowed client ID), attach the role,
   add a **target** of type MCP server whose endpoint is the runtime invocation URL from Section 3 step 3 and
   whose authorization is "OAuth Client" (the Identity client from step 4). Wait for Gateway and target = Ready.
6. **In Quick:** same as Path A step 4, but the endpoint is the **Gateway resource URL**, and you can choose
   **User authentication** (3LO, each Quick user logs in to Cognito) or **Service authentication** (2LO).
   Cognito token URL format: `https://<pool-id-without-underscore>.auth.<region>.amazoncognito.com/oauth2/token`
   and the matching `/oauth2/authorize`.
7. Link the action to the chat agent, test, ask.

Cost: Gateway bills per API call and per tool-search; at demo volumes that's cents. Cognito free. So B is a
few cents more than A plus about an hour more setup.

## 5. What the user experience looks like

- A manager opens Quick, picks the "Pipeline Ops" chat agent, types "Was the midnight pressure drop at ST-03
  on Jan 27 a leak?" Quick's model maps that to `investigate_pipeline_event(station_id="ST-03", ...)`, calls
  our endpoint, waits ~30 s, and renders the verdict and the NRC draft inline. Because the tool is read-only,
  Quick does not show an "action review" prompt (it does for mutating actions).
- The description string on the tool is what Quick uses to decide when to call it. Write it like a product
  blurb, not a docstring.
- Same latency as the Streamlit UI (~20 s FP, ~30 s leak). Quick shows a working indicator; there is no
  streaming into Quick's chat.

## 6. Prerequisites and gotchas

- Quick must be enabled in the account (or a Free/Plus workspace used; see cost note). The integrating user
  needs an **Author or higher** role; one AWS post says Author Pro.
- MCP endpoint must be **streamable HTTP, stateless** (`stateless_http=True`). AgentCore Runtime expects the
  server on `0.0.0.0:8000/mcp`.
- **No SigV4 from Quick.** OAuth or nothing.
- After creating the integration Quick initially shows only `listTools`; the real tools appear once the action
  is Available (a couple of minutes).
- Cognito token URL: strip the underscore from the pool ID in the hostname.
- If several Quick users share a 2LO integration they all act as the same service identity; use 3LO if you ever
  need per-user audit in CloudWatch.
- Tear-down order: Quick integration → Gateway target → Gateway → Identity client → Cognito pools → runtime.

## 7. Cost note (why we are not doing this right now)

Quick plans tied to an AWS account are Professional ($20/user/mo) or Enterprise ($40/user/mo), **plus a flat
$250/account/month infrastructure fee**. There is a 30-day Enterprise trial (up to 25 users, no card) that
converts to paid Enterprise billing on day 31. Free ($0, 1 user) and Plus ($20–25/user) workspaces exist
without the $250 fee but are email-signup products not tied to an AWS account. Everything on our side of the
diagram is near-zero cost; Quick itself is the expense.

## Sources

- AWS blog: Connect Amazon Quick Suite to enterprise apps and agents with MCP —
  https://aws.amazon.com/blogs/machine-learning/connect-amazon-quick-suite-to-enterprise-apps-and-agents-with-mcp
- AWS blog: Connect an AgentCore Runtime hosted MCP server to Amazon Quick —
  https://aws.amazon.com/blogs/machine-learning/connect-an-agentcore-runtime-hosted-mcp-server-to-amazon-quick/
- Amazon Quick pricing — https://aws.amazon.com/quick/pricing/
