#!/bin/bash
# Host website/site/ (static marketing page + 5-min MP4) on S3 + CloudFront with HTTPS, in the Minfy R&D account.
# Idempotent: creates the bucket, Origin Access Control and distribution on first run; later runs just sync + invalidate.
#
#   AWS_PROFILE=minfy-rnd ./deploy-website.sh                 # deploy / update
#   AWS_PROFILE=minfy-rnd ./deploy-website.sh --status        # print URL + distribution state
#
# Cost: S3 storage for 18 MB ≈ $0; CloudFront first 1 TB/month of egress is free tier, then ~$0.085/GB
# (a full 17 MB video view ≈ $0.0015). No fixed monthly charge.
#
# Custom hostname (later, when IT provides e.g. energy-demo.minfytech.com):
#   1. aws acm request-certificate --region us-east-1 --domain-name <host> --validation-method DNS
#   2. IT adds the ACM validation CNAME, then a CNAME <host> -> <distribution>.cloudfront.net
#   3. HOSTNAME_ALIAS=<host> CERT_ARN=<acm arn> ./deploy-website.sh   (adds the alias + cert to the distribution)
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE=minfy-rnd}"
export AWS_REGION=us-east-1 AWS_PAGER=""
HERE=$(cd "$(dirname "$0")" && pwd)
SITE="$HERE/site"
ACCT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=${BUCKET:-minfy-energy-demo-website-$ACCT}
OAC_NAME=minfy-energy-demo-website-oac
COMMENT="Minfy Energy demo website (pipeline leak agent + Amazon Quick), static S3 origin"
echo "identity: $(aws sts get-caller-identity --query Arn --output text)"

dist_id() { aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='$COMMENT'].Id | [0]" --output text 2>/dev/null | grep -v None || true; }

if [ "${1:-}" = "--status" ]; then
  ID=$(dist_id); [ -z "$ID" ] && { echo "not deployed"; exit 0; }
  aws cloudfront get-distribution --id "$ID" --query "Distribution.{status:Status,url:DomainName,aliases:DistributionConfig.Aliases.Items}" --output json
  exit 0
fi

# --- S3 bucket: private, versioned off, public access blocked; CloudFront reads it via OAC -----------------------
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" --region us-east-1 >/dev/null
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging 'TagSet=[{Key=project,Value=pipeline-leak-agent},{Key=purpose,Value=energy-demo-website}]'
  echo "created bucket $BUCKET"
fi

# --- upload with explicit content types (S3 guesses .avif and .mp4 poorly); long cache for assets, short for html ---
aws s3 sync "$SITE" "s3://$BUCKET" --delete --exclude "*" --include "*.html" \
  --content-type "text/html; charset=utf-8" --cache-control "public, max-age=300" >/dev/null
aws s3 sync "$SITE" "s3://$BUCKET" --exclude "*" --include "*.css" \
  --content-type "text/css; charset=utf-8" --cache-control "public, max-age=3600" >/dev/null
aws s3 sync "$SITE" "s3://$BUCKET" --exclude "*" --include "*.js" \
  --content-type "application/javascript; charset=utf-8" --cache-control "public, max-age=3600" >/dev/null
aws s3 sync "$SITE" "s3://$BUCKET" --exclude "*" --include "*.mp4" \
  --content-type "video/mp4" --content-disposition "inline" --cache-control "public, max-age=86400" >/dev/null
aws s3 sync "$SITE" "s3://$BUCKET" --exclude "*" --include "*.jpg" \
  --content-type "image/jpeg" --cache-control "public, max-age=86400" >/dev/null
aws s3 sync "$SITE" "s3://$BUCKET" --exclude "*" --include "*.avif" \
  --content-type "image/avif" --cache-control "public, max-age=86400" >/dev/null
echo "uploaded $(aws s3 ls "s3://$BUCKET" --recursive | wc -l) objects"

# --- Origin Access Control (lets only this distribution read the private bucket) --------------------------------
OAC_ID=$(aws cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text | grep -v None || true)
if [ -z "$OAC_ID" ]; then
  OAC_ID=$(aws cloudfront create-origin-access-control --origin-access-control-config \
    "Name=$OAC_NAME,Description=S3 OAC for the Minfy energy demo website,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query OriginAccessControl.Id --output text)
  echo "created OAC $OAC_ID"
fi

# --- distribution --------------------------------------------------------------------------------------------------
ID=$(dist_id)
ALIASES='{"Quantity":0}'; VIEWER_CERT='{"CloudFrontDefaultCertificate":true,"MinimumProtocolVersion":"TLSv1.2_2021"}'
if [ -n "${HOSTNAME_ALIAS:-}" ] && [ -n "${CERT_ARN:-}" ]; then
  H=$HOSTNAME_ALIAS
  ALIASES="{\"Quantity\":1,\"Items\":[\"$H\"]}"
  VIEWER_CERT="{\"ACMCertificateArn\":\"$CERT_ARN\",\"SSLSupportMethod\":\"sni-only\",\"MinimumProtocolVersion\":\"TLSv1.2_2021\"}"
fi
CFG=$(cat <<JSON
{
  "CallerReference": "minfy-energy-demo-website-$(date +%s)",
  "Comment": "$COMMENT",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "PriceClass": "PriceClass_All",
  "HttpVersion": "http2and3",
  "IsIPV6Enabled": true,
  "Aliases": $ALIASES,
  "ViewerCertificate": $VIEWER_CERT,
  "Origins": {"Quantity": 1, "Items": [{
    "Id": "s3-site", "DomainName": "$BUCKET.s3.us-east-1.amazonaws.com",
    "OriginAccessControlId": "$OAC_ID",
    "S3OriginConfig": {"OriginAccessIdentity": ""}
  }]},
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-site",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {"Quantity": 2, "Items": ["GET","HEAD"], "CachedMethods": {"Quantity": 2, "Items": ["GET","HEAD"]}},
    "Compress": true,
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "ResponseHeadersPolicyId": "67f7725c-6f97-4210-82d7-5512b31e9d03"
  },
  "CustomErrorResponses": {"Quantity": 1, "Items": [
    {"ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "404", "ErrorCachingMinTTL": 60}
  ]}
}
JSON
)
# CachePolicyId = AWS managed "CachingOptimized"; ResponseHeadersPolicyId = AWS managed "SecurityHeadersPolicy".
if [ -z "$ID" ]; then
  OUT=$(aws cloudfront create-distribution --distribution-config "$CFG" --output json)
  ID=$(echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)['Distribution']['Id'])")
  echo "created distribution $ID"
else
  ETAG=$(aws cloudfront get-distribution-config --id "$ID" --query ETag --output text)
  CUR=$(aws cloudfront get-distribution-config --id "$ID" --query DistributionConfig --output json)
  # UpdateDistribution needs the FULL current config (Logging, Restrictions, WebACLId, ...). Start from it and
  # patch only what we own: origin/OAC, cache behavior, error pages, and (if given) the alias + certificate.
  NEW=$(python3 -c "
import json,sys
cur=json.loads(sys.argv[1]); new=json.loads(sys.argv[2])
# origins/behaviors were set at create time and carry service-filled sub-fields; leave them untouched on update
for k in ('Comment','Enabled','DefaultRootObject','PriceClass','HttpVersion','IsIPV6Enabled'):
    cur[k]=new[k]
if new['Aliases']['Quantity']:
    cur['Aliases']=new['Aliases']; cur['ViewerCertificate']=new['ViewerCertificate']
print(json.dumps(cur))" "$CUR" "$CFG")
  aws cloudfront update-distribution --id "$ID" --if-match "$ETAG" --distribution-config "$NEW" >/dev/null
  echo "updated distribution $ID"
fi
DIST_ARN="arn:aws:cloudfront::$ACCT:distribution/$ID"
DOMAIN=$(aws cloudfront get-distribution --id "$ID" --query Distribution.DomainName --output text)

# --- bucket policy: only this distribution may read ---------------------------------------------------------------
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{\"Sid\":\"AllowCloudFrontOAC\",\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"cloudfront.amazonaws.com\"},
    \"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/*\",
    \"Condition\":{\"StringEquals\":{\"AWS:SourceArn\":\"$DIST_ARN\"}}}]}"

aws cloudfront create-invalidation --distribution-id "$ID" --paths "/*" --query Invalidation.Id --output text >/dev/null
echo
echo "URL:    https://$DOMAIN/"
echo "status: $(aws cloudfront get-distribution --id "$ID" --query Distribution.Status --output text)  (InProgress → Deployed takes ~5 min on first create)"
