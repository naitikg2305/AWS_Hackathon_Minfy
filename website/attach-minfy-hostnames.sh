#!/bin/bash
# Attach the Minfy hostnames to both public endpoints once the ACM certificate is ISSUED.
#
#   pipeline.minfytech.com      -> CloudFront (demo website)        : add alias + cert to the distribution
#   pipeline-app.minfytech.com  -> ECS Express ALB (Streamlit app)  : add cert to the :443 listener (SNI) +
#                                                                      a host-header rule forwarding to our target group
#
# ECS Express Mode has no custom-domain setting of its own; its ALB is shared by every Express service in the
# account and routes by Host header, so we add our own rule. Express rolling deployments can swap target groups,
# so this script is idempotent and re-points the rule at whatever target group the Express-managed rule for our
# *.ecs.us-east-1.on.aws hostname currently forwards to. Re-run it after every UI deploy.
#
#   AWS_PROFILE=minfy-rnd ./attach-minfy-hostnames.sh            # does everything, safe to re-run
#   AWS_PROFILE=minfy-rnd ./attach-minfy-hostnames.sh --check    # just report cert + DNS + endpoint status
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE=minfy-rnd}"
export AWS_REGION=us-east-1 AWS_PAGER=""
HERE=$(cd "$(dirname "$0")" && pwd)
SITE_HOST=${SITE_HOST:-pipeline.minfytech.com}
APP_HOST=${APP_HOST:-pipeline-app.minfytech.com}
CERT_ARN=${CERT_ARN:-$(aws acm list-certificates --query "CertificateSummaryList[?DomainName=='$SITE_HOST'].CertificateArn | [0]" --output text)}
EXPRESS_HOST=${EXPRESS_HOST:-pi-e4a940f7de9544eab171713c4ca21dfd.ecs.us-east-1.on.aws}
ALB_NAME=${ALB_NAME:-ecs-express-gateway-alb-bfeb2b96}
RULE_PRIORITY=${RULE_PRIORITY:-44991}

echo "identity: $(aws sts get-caller-identity --query Arn --output text)"
STATUS=$(aws acm describe-certificate --certificate-arn "$CERT_ARN" --query Certificate.Status --output text)
echo "certificate: $STATUS  ($CERT_ARN)"

resolve() { python3 -c "import socket,sys
try: print(socket.gethostbyname(sys.argv[1]))
except Exception as e: print('unresolved')" "$1"; }

if [ "$STATUS" != "ISSUED" ]; then
  echo
  echo "Not issued yet. DNS records IT must add (CNAME, host part shown first, then the full name):"
  aws acm describe-certificate --certificate-arn "$CERT_ARN" \
    --query "Certificate.DomainValidationOptions[].[DomainName,ValidationStatus,ResourceRecord.Name,ResourceRecord.Value]" --output text \
    | while read -r d st name value; do printf "  %-28s %-18s\n     name:  %s\n     value: %s\n" "$d" "$st" "$name" "$value"; done
  echo "Current resolution: $SITE_HOST -> $(resolve "$SITE_HOST"), $APP_HOST -> $(resolve "$APP_HOST")"
  exit 2
fi
[ "${1:-}" = "--check" ] && { for h in "$SITE_HOST" "$APP_HOST"; do printf "%-28s -> %s  HTTP %s\n" "$h" "$(resolve "$h")" "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "https://$h/" || echo err)"; done; exit 0; }

# --- 1. CloudFront: alias + certificate for the website -----------------------------------------------------------
echo "--- CloudFront"
HOSTNAME_ALIAS="$SITE_HOST" CERT_ARN="$CERT_ARN" AWS_PROFILE="$AWS_PROFILE" "$HERE/deploy-website.sh" | tail -3

# --- 2. ALB: certificate (SNI) + host rule for the app -------------------------------------------------------------
echo "--- ALB"
ALB=$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --query "LoadBalancers[0].LoadBalancerArn" --output text)
L443=$(aws elbv2 describe-listeners --load-balancer-arn "$ALB" --query "Listeners[?Port==\`443\`].ListenerArn | [0]" --output text)
if ! aws elbv2 describe-listener-certificates --listener-arn "$L443" --query "Certificates[].CertificateArn" --output text | grep -q "$CERT_ARN"; then
  aws elbv2 add-listener-certificates --listener-arn "$L443" --certificates "CertificateArn=$CERT_ARN" >/dev/null
  echo "added certificate to :443 listener (SNI)"
fi
# target group = whatever the Express-managed rule for our *.on.aws host forwards to right now
TG=$(aws elbv2 describe-rules --listener-arn "$L443" --output json | python3 -c "
import json,sys
for r in json.load(sys.stdin)['Rules']:
    hosts=[v for c in r.get('Conditions',[]) for v in (c.get('HostHeaderConfig',{}).get('Values') or c.get('Values') or [])]
    if '$EXPRESS_HOST' in hosts:
        a=r['Actions'][0]
        tgs=a.get('ForwardConfig',{}).get('TargetGroups') or [{'TargetGroupArn':a.get('TargetGroupArn')}]
        print(max(tgs,key=lambda t:t.get('Weight',1))['TargetGroupArn']); break")
[ -n "$TG" ] || { echo "could not find the Express rule for $EXPRESS_HOST"; exit 1; }
echo "target group now: ${TG##*/}"
EXISTING=$(aws elbv2 describe-rules --listener-arn "$L443" --query "Rules[?Priority=='$RULE_PRIORITY'].RuleArn | [0]" --output text | grep -v None || true)
if [ -z "$EXISTING" ]; then
  aws elbv2 create-rule --listener-arn "$L443" --priority "$RULE_PRIORITY" \
    --conditions "Field=host-header,HostHeaderConfig={Values=[$APP_HOST]}" \
    --actions "Type=forward,TargetGroupArn=$TG" --tags Key=project,Value=pipeline-leak-agent >/dev/null
  echo "created host rule $APP_HOST -> ${TG##*/} (priority $RULE_PRIORITY)"
else
  aws elbv2 modify-rule --rule-arn "$EXISTING" --actions "Type=forward,TargetGroupArn=$TG" >/dev/null
  echo "updated host rule $APP_HOST -> ${TG##*/}"
fi

echo
for h in "$SITE_HOST" "$APP_HOST"; do
  printf "%-28s -> %-15s HTTPS %s\n" "$h" "$(resolve "$h")" "$(curl -s -o /dev/null -m 15 -w '%{http_code} (tls verify %{ssl_verify_result})' "https://$h/" || echo err)"
done
echo "CloudFront alias changes take ~5 min to propagate; re-run with --check."
