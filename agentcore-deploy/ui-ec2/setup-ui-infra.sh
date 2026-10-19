#!/bin/bash
# One-time setup for the public Streamlit demo host (Minfy R&D account).
# Creates:
#   - IAM role pipeline-leak-ui-ec2-role: lets the EC2 box call the AgentCore runtime
#     (bedrock-agentcore:InvokeAgentRuntime on our one runtime) and be managed via SSM
#     Session Manager (no SSH key pair, no port 22). This is the SERVER's identity only;
#     visitors to the URL need nothing.
#   - Instance profile pipeline-leak-ui-ec2-profile wrapping that role
#   - Security group pipeline-leak-ui-sg in the default VPC: inbound tcp/80 from anywhere
# Idempotent: re-running skips things that already exist.
# Usage: AWS_PROFILE=minfy-rnd ./setup-ui-infra.sh
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE=minfy-rnd}"
export AWS_REGION=us-east-1
HERE=$(cd "$(dirname "$0")" && pwd)
STATE="$HERE/../pipelineleakagent/agentcore/.cli/deployed-state.json"

echo "identity: $(aws sts get-caller-identity --query Arn --output text)"
case "$(aws sts get-caller-identity --query Arn --output text)" in
  *minfytech.com*) ;;
  *) echo "refusing: not the Minfy R&D identity"; exit 1 ;;
esac

RUNTIME_ARN=${AGENTCORE_RUNTIME_ARN:-$(python3 -c "import json;d=json.load(open('$STATE'));print(list(list(d['targets'].values())[0]['resources']['runtimes'].values())[0]['runtimeArn'])")}
echo "runtime: ${RUNTIME_ARN##*/}"

ROLE=pipeline-leak-ui-ec2-role
PROFILE=pipeline-leak-ui-ec2-profile
SG_NAME=pipeline-leak-ui-sg

if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" \
    --description "EC2 host for the pipeline leak Streamlit demo UI: invoke AgentCore runtime + SSM" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --tags Key=project,Value=pipeline-leak-agent >/dev/null
  echo "created role $ROLE"
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name invoke-agentcore --policy-document "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"bedrock-agentcore:InvokeAgentRuntime\"],
                 \"Resource\":[\"$RUNTIME_ARN\",\"$RUNTIME_ARN/runtime-endpoint/*\"]}]}"
aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
echo "role policies ok"

if ! aws iam get-instance-profile --instance-profile-name "$PROFILE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$PROFILE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE" --role-name "$ROLE"
  echo "created instance profile $PROFILE"
  sleep 10   # IAM propagation before run-instances can use it
fi

VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [ -z "$SG" ] || [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "Pipeline leak demo UI: HTTP in only" --vpc-id "$VPC" \
        --tag-specifications 'ResourceType=security-group,Tags=[{Key=project,Value=pipeline-leak-agent},{Key=Name,Value=pipeline-leak-ui-sg}]' \
        --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG" \
        --ip-permissions 'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=public http}]' >/dev/null
  echo "created security group $SG (tcp/80 open)"
fi
echo "setup complete. Next: AWS_PROFILE=minfy-rnd ./deploy-ui.sh"
