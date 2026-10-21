"""Smoke-test the deployed MCP runtime over plain JSON-RPC (no MCP client library needed).

AgentCore Runtime with protocol MCP accepts MCP JSON-RPC messages on its invocation endpoint. With IAM
auth we can send them through boto3's invoke_agent_runtime, which signs the request for us.

    AWS_PROFILE=minfy-rnd .venv/bin/python src/tests/smoke_mcp_runtime.py            # tools/list + list_alarm_events
    AWS_PROFILE=minfy-rnd .venv/bin/python src/tests/smoke_mcp_runtime.py --investigate  # also runs the agent on FP-001 (~20 s)
"""
import json
import sys
import time
import uuid
from pathlib import Path

import boto3

STATE = Path(__file__).resolve().parents[2] / "agentcore-deploy/pipelineleakagent/agentcore/.cli/deployed-state.json"


def mcp_runtime_arn() -> str:
    state = json.loads(STATE.read_text())
    for target in state["targets"].values():
        rt = target["resources"]["runtimes"].get("pipeline_leak_mcp")
        if rt:
            return rt["runtimeArn"]
    raise SystemExit("pipeline_leak_mcp not in deployed-state.json; run `agentcore deploy` first")


def rpc(client, arn: str, session: str, method: str, params: dict | None = None, rpc_id: int = 1) -> dict:
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params or {}}
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session,
        contentType="application/json",
        accept="application/json, text/event-stream",
        payload=json.dumps(body).encode(),
    )
    raw = resp["response"].read().decode()
    # streamable-http may answer as a bare JSON object or as SSE "data: {...}" lines
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(raw)


def main(argv: list[str]) -> int:
    arn = mcp_runtime_arn()
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    session = str(uuid.uuid4()) + "-mcp-smoke-xxxxxxxxxx"

    init = rpc(client, arn, session, "initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "smoke", "version": "0"},
    })
    print("initialize ->", init.get("result", init).get("serverInfo", init.get("error")))

    tools = rpc(client, arn, session, "tools/list", rpc_id=2)["result"]["tools"]
    print("tools/list  ->", [t["name"] for t in tools])

    t = time.time()
    out = rpc(client, arn, session, "tools/call", {"name": "list_alarm_events", "arguments": {"kind": "leak"}}, rpc_id=3)
    text = out["result"]["content"][0]["text"]
    print(f"list_alarm_events(leak) in {time.time()-t:.1f}s ->\n" + "\n".join(text.splitlines()[:3]) + "\n  ...")

    if "--investigate" in argv:
        t = time.time()
        out = rpc(client, arn, session, "tools/call", {
            "name": "investigate_pipeline_event",
            "arguments": {"station_id": "ST-01", "start_time": "2025-12-04T13:00:00",
                          "end_time": "2025-12-04T14:30:00", "event_id": "FP-001"},
        }, rpc_id=4)
        text = out["result"]["content"][0]["text"]
        print(f"investigate_pipeline_event(FP-001) in {time.time()-t:.0f}s ->\n" + "\n".join(text.splitlines()[:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
