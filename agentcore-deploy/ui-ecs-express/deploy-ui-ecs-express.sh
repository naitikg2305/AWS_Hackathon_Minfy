#!/bin/bash
# Build, push and deploy the Streamlit UI to Amazon ECS Express Mode (Fargate + ALB + HTTPS URL).
#
# Prereqs in the Minfy R&D account (already present 2026-10-21):
#   - ECR repo pipeline-leak-ui
#   - infrastructure role pipeline-leak-ui-express-infra-role (trust ecs.amazonaws.com + aws:SourceAccount,
#     policy arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices)
#   - execution role ecsTaskExecutionRole (AmazonECSTaskExecutionRolePolicy)
#   - task role pipeline-leak-ui-task-role (bedrock-agentcore:InvokeAgentRuntime on our runtime only)
# Local: podman (or docker; set CONTAINER_TOOL=docker).
#
# Usage:
#   AWS_PROFILE=minfy-rnd APP_PASSWORD='<demo code>' ./deploy-ui-ecs-express.sh          # create or update
#   AWS_PROFILE=minfy-rnd ./deploy-ui-ecs-express.sh --no-build                           # redeploy existing image
#
# Cost (us-east-1, running 24/7): Fargate 0.5 vCPU / 1 GB ≈ $18/mo, ALB ≈ $16/mo + LCU, so ≈ $35/mo.
# Scale to zero between demos:  aws ecs update-express-gateway-service --service-arn <arn> --scaling-target minTaskCount=0,maxTaskCount=1
# (the ALB keeps billing while the service exists; delete the service to stop that).
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE=minfy-rnd}"
export AWS_REGION=us-east-1
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
STATE="$ROOT/agentcore-deploy/pipelineleakagent/agentcore/.cli/deployed-state.json"
TOOL=${CONTAINER_TOOL:-podman}
SERVICE=${SERVICE_NAME:-pipeline-leak-ui}
INFRA_ROLE=${INFRA_ROLE:-pipeline-leak-ui-express-infra-role}
EXEC_ROLE=${EXEC_ROLE:-ecsTaskExecutionRole}
TASK_ROLE=${TASK_ROLE:-pipeline-leak-ui-task-role}

ACCT=$(aws sts get-caller-identity --query Account --output text)
echo "identity: $(aws sts get-caller-identity --query Arn --output text)"
REPO="$ACCT.dkr.ecr.us-east-1.amazonaws.com/pipeline-leak-ui"
RUNTIME_ARN=${AGENTCORE_RUNTIME_ARN:-$(python3 -c "import json;d=json.load(open('$STATE'));print(list(d['targets'].values())[0]['resources']['runtimes']['pipeline_leak_agent']['runtimeArn'])")}

if [ "${1:-}" != "--no-build" ]; then
  echo "building image..."
  $TOOL build -q -f "$HERE/Dockerfile" -t pipeline-leak-ui:latest "$ROOT"
  aws ecr get-login-password | $TOOL login --username AWS --password-stdin "$ACCT.dkr.ecr.us-east-1.amazonaws.com" >/dev/null
  $TOOL tag pipeline-leak-ui:latest "$REPO:latest"
  $TOOL push -q "$REPO:latest"
fi
DIGEST=$(aws ecr describe-images --repository-name pipeline-leak-ui --image-ids imageTag=latest --query 'imageDetails[0].imageDigest' --output text)
IMAGE="$REPO@$DIGEST"      # pin by digest so each deploy is a real new revision
echo "image: $IMAGE"

ENV_JSON="[{\"name\":\"AGENTCORE_RUNTIME_ARN\",\"value\":\"$RUNTIME_ARN\"},{\"name\":\"AGENT_MODE\",\"value\":\"agentcore\"},{\"name\":\"AWS_REGION\",\"value\":\"us-east-1\"}"
if [ -n "${APP_PASSWORD:-}" ]; then ENV_JSON="$ENV_JSON,{\"name\":\"APP_PASSWORD\",\"value\":\"$APP_PASSWORD\"}"; fi
ENV_JSON="$ENV_JSON]"

CONTAINER=$(cat <<JSON
{"image":"$IMAGE","containerPort":8080,
 "awsLogsConfiguration":{"logGroup":"/ecs/pipeline-leak-ui","logStreamPrefix":"ui"},
 "environment":$ENV_JSON}
JSON
)

EXISTING=$(aws ecs list-services --cluster default --query "serviceArns[?contains(@,'/$SERVICE')]|[0]" --output text 2>/dev/null || true)
if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "updating existing service $EXISTING"
  aws ecs update-express-gateway-service --service-arn "$EXISTING" --primary-container "$CONTAINER" >/dev/null
  ARN="$EXISTING"
else
  echo "creating service $SERVICE"
  ARN=$(aws ecs create-express-gateway-service \
    --service-name "$SERVICE" --cluster default \
    --infrastructure-role-arn "arn:aws:iam::$ACCT:role/$INFRA_ROLE" \
    --execution-role-arn "arn:aws:iam::$ACCT:role/$EXEC_ROLE" \
    --task-role-arn "arn:aws:iam::$ACCT:role/$TASK_ROLE" \
    --health-check-path /_stcore/health \
    --primary-container "$CONTAINER" \
    --cpu 512 --memory 1024 \
    --scaling-target minTaskCount=1,maxTaskCount=1,autoScalingMetric=AVERAGE_CPU,autoScalingTargetValue=70 \
    --tags key=project,value=pipeline-leak-agent \
    --query 'service.serviceArn' --output text)
fi
echo "service: $ARN"
echo "waiting for the service to settle (ALB + cert provisioning, usually 3-6 min)..."
for i in $(seq 1 60); do
  OUT=$(aws ecs describe-express-gateway-service --service-arn "$ARN" --output json)
  STATUS=$(echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin)['service'];print(d.get('status',{}).get('statusCode') if isinstance(d.get('status'),dict) else d.get('status'))")
  URL=$(echo "$OUT" | python3 -c "
import json,sys
d=json.load(sys.stdin)['service']
def find(o):
    if isinstance(o,dict):
        if isinstance(o.get('endpoint'),str) and o['endpoint'].startswith('http'): return o['endpoint']
        for v in o.values():
            r=find(v)
            if r: return r
    if isinstance(o,list):
        for v in o:
            r=find(v)
            if r: return r
print(find(d) or '')" 2>/dev/null || true)
  echo "  $STATUS ${URL}"
  case "$STATUS" in ACTIVE|RUNNING|STEADY_STATE) break;; FAILED*|*FAIL*) echo "$OUT" | head -60; exit 1;; esac
  sleep 10
done
echo
echo "Public HTTPS URL: $URL"
echo "Logs:            aws logs tail /ecs/pipeline-leak-ui --follow"
echo "Scale to zero:   aws ecs update-express-gateway-service --service-arn $ARN --scaling-target minTaskCount=0,maxTaskCount=1,autoScalingMetric=AVERAGE_CPU,autoScalingTargetValue=70"
echo "Delete:          aws ecs delete-express-gateway-service --service-arn $ARN"
