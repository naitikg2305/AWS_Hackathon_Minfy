# Minfy Energy demo website

Static marketing page for the pipeline leak-detection demo and the Amazon Quick + MCP story, with the five-minute
walkthrough video. Delivered as a handoff package on 2026-10-21; `site/` is its contents, byte-for-byte (checksums
verified against the package).

```
site/
├── index.html                 # the page (noindex,nofollow by design for the standalone release)
├── styles.css
├── app.js                     # menu, video play button, scenario tabs — browser-side only
└── assets/
    ├── pipeline-demo.mp4      # 5:00, H.264 + AAC, 17 MB
    ├── demo-poster.jpg
    └── minfy-logo.avif
```

No build step, no backend, no external scripts. Everything is relative-path, so it works from any web root.

## Hosting

S3 (private bucket, public access blocked) + CloudFront (HTTPS, Origin Access Control, redirect HTTP→HTTPS,
Brotli/gzip for text, byte-range for the video) in the Minfy R&D account, us-east-1.

```bash
AWS_PROFILE=minfy-rnd ./deploy-website.sh            # first run creates everything; later runs sync + invalidate
AWS_PROFILE=minfy-rnd ./deploy-website.sh --status   # URL + distribution status
```

Cost: no fixed charge. ~18 MB of storage and CloudFront egress inside the free tier for any realistic demo traffic.

## Custom Minfy hostnames (DONE 2026-10-22)

Live: **https://pipeline.minfytech.com/** (this site) and **https://pipeline-app.minfytech.com/** (Streamlit app).
One ACM certificate in us-east-1 covers both; IT added the routing CNAMEs and the two ACM validation CNAMEs.
`attach-minfy-hostnames.sh` attaches the cert + alias to CloudFront and the cert + a host-header rule to the shared
ECS Express ALB. **Re-run it after every UI deploy** (Express rolling deploys can swap target groups).

Original steps, for reference:

1. `aws acm request-certificate --region us-east-1 --domain-name <host> --validation-method DNS --profile minfy-rnd`
2. IT adds the ACM validation CNAME, then `CNAME <host> → <distribution>.cloudfront.net`.
3. `HOSTNAME_ALIAS=<host> CERT_ARN=<arn> AWS_PROFILE=minfy-rnd ./deploy-website.sh`

The hostname then shows in the address bar with a valid certificate, as the handoff requires (no redirect to a raw
CloudFront or Netlify URL).

## Updating the page

Edit files in `site/`, run the deploy script. It uploads with explicit content types and invalidates the CloudFront
cache. The internal handoff README is kept out of this public repo on purpose.

## Scope note

This page is the recorded demo and marketing copy only. The live application is the Streamlit UI on ECS Express
and the agent on AgentCore (see `docs/deploy-agentcore.md`). The Quick/MCP connection shown in the video is
illustrative; the MCP server is deployed, Amazon Quick is not connected. Don't change the page's wording on that
until the integration is actually live.
