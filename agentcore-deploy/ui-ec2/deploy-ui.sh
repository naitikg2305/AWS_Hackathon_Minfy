#!/bin/bash
# Launches the single EC2 host that serves the public Streamlit demo UI and prints its URL.
# Run setup-ui-infra.sh first (IAM role + security group).
# Cost: t4g.micro on-demand ~$0.0084/h (~$6/mo) + public IPv4 ~$3.65/mo + 8 GB gp3 ~$0.64/mo.
# Stop the instance when not demoing: compute stops billing, the Elastic IP keeps the URL.
# Usage: AWS_PROFILE=minfy-rnd ./deploy-ui.sh
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE=minfy-rnd}"
export AWS_REGION=us-east-1
HERE=$(cd "$(dirname "$0")" && pwd)
STATE="$HERE/../pipelineleakagent/agentcore/.cli/deployed-state.json"

echo "identity: $(aws sts get-caller-identity --query Arn --output text)"
RUNTIME_ARN=${AGENTCORE_RUNTIME_ARN:-$(python3 -c "import json;d=json.load(open('$STATE'));print(list(list(d['targets'].values())[0]['resources']['runtimes'].values())[0]['runtimeArn'])")}
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=pipeline-leak-ui-sg --query 'SecurityGroups[0].GroupId' --output text)
SUBNET=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true Name=availability-zone,Values=us-east-1a --query 'Subnets[0].SubnetId' --output text)

EXISTING=$(aws ec2 describe-instances --filters Name=tag:Name,Values=pipeline-leak-ui Name=instance-state-name,Values=pending,running,stopping,stopped \
           --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -n "$EXISTING" ]; then
  echo "instance already exists: $EXISTING (stop/terminate it first, or use 'sudo update-ui' on the box via SSM)"; exit 1
fi

sed -e "s|__RUNTIME_ARN__|$RUNTIME_ARN|" \
    -e "s|__REPO_URL__|https://github.com/naitikg2305/AWS_Hackathon_Minfy.git|" \
    -e "s|__BRANCH__|main|" "$HERE/user-data.sh" > /tmp/pipeline-leak-ui-user-data.sh

ID=$(aws ec2 run-instances \
  --image-id "$AMI" --instance-type t4g.micro \
  --iam-instance-profile Name=pipeline-leak-ui-ec2-profile \
  --security-group-ids "$SG" --subnet-id "$SUBNET" --associate-public-ip-address \
  --metadata-options HttpTokens=required,HttpEndpoint=enabled \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=8,VolumeType=gp3,DeleteOnTermination=true}' \
  --instance-initiated-shutdown-behavior stop \
  --user-data file:///tmp/pipeline-leak-ui-user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=pipeline-leak-ui},{Key=project,Value=pipeline-leak-agent}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "instance: $ID"
aws ec2 wait instance-running --instance-ids "$ID"

# stable public IP (survives stop/start)
EIP=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=pipeline-leak-ui --query 'Addresses[0].AllocationId' --output text 2>/dev/null || true)
if [ -z "$EIP" ] || [ "$EIP" = "None" ]; then
  EIP=$(aws ec2 allocate-address --domain vpc --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=pipeline-leak-ui},{Key=project,Value=pipeline-leak-agent}]' --query AllocationId --output text)
fi
aws ec2 associate-address --instance-id "$ID" --allocation-id "$EIP" >/dev/null
IP=$(aws ec2 describe-addresses --allocation-ids "$EIP" --query 'Addresses[0].PublicIp' --output text)

echo
echo "Public URL: http://$IP/"
echo "Bootstrap takes ~4 min (installs Python deps). Watch with:"
echo "  aws ssm start-session --target $ID   # then: sudo tail -f /var/log/user-data.log"
echo "Stop when idle:  aws ec2 stop-instances --instance-ids $ID"
echo "Start again:     aws ec2 start-instances --instance-ids $ID   (same URL)"
echo "Tear down:       aws ec2 terminate-instances --instance-ids $ID && aws ec2 release-address --allocation-id $EIP"
