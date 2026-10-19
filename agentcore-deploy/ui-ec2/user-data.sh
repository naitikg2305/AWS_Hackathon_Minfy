#!/bin/bash
# Bootstraps an Amazon Linux 2023 (arm64) host to serve the Streamlit operator UI on port 80.
# Placeholders __RUNTIME_ARN__ / __REPO_URL__ / __BRANCH__ are filled in by deploy-ui.sh.
# The app talks to the AgentCore runtime using the instance role; no AWS keys on disk.
set -euxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1

RUNTIME_ARN="__RUNTIME_ARN__"
REPO_URL="__REPO_URL__"
BRANCH="__BRANCH__"
APP_DIR=/opt/pipeline-leak-agent

# 1 GB RAM on t4g.micro: add swap so pandas + plotly imports never OOM
if ! swapon --show | grep -q swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

dnf -y install git python3.11 python3.11-pip
id app >/dev/null 2>&1 || useradd --system --create-home --shell /sbin/nologin app

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
fi
chown -R app:app "$APP_DIR"
sudo -u app bash -c "cd $APP_DIR && python3.11 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt"

TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)

install -o app -g app -m 600 /dev/null /etc/pipeline-leak-ui.env
cat > /etc/pipeline-leak-ui.env <<ENV
AGENT_MODE=agentcore
AWS_DEFAULT_REGION=$REGION
AWS_REGION=$REGION
AGENTCORE_RUNTIME_ARN=$RUNTIME_ARN
ENV
# To gate the demo behind a shared code later, append APP_PASSWORD=... to that file and restart.

cat > /etc/systemd/system/pipeline-leak-ui.service <<'UNIT'
[Unit]
Description=Pipeline Leak Detection Agent - Streamlit UI
After=network-online.target
Wants=network-online.target

[Service]
User=app
Group=app
WorkingDirectory=/opt/pipeline-leak-agent
EnvironmentFile=/etc/pipeline-leak-ui.env
ExecStart=/opt/pipeline-leak-agent/.venv/bin/streamlit run src/app/streamlit_app.py --server.port 80 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# helper: pull latest code and restart (run via SSM Session Manager: sudo update-ui)
cat > /usr/local/bin/update-ui <<'HELPER'
#!/bin/bash
set -e
cd /opt/pipeline-leak-agent
sudo -u app git pull --ff-only
sudo -u app .venv/bin/pip install -q -r requirements.txt
systemctl restart pipeline-leak-ui
systemctl --no-pager status pipeline-leak-ui | head -5
HELPER
chmod +x /usr/local/bin/update-ui

systemctl daemon-reload
systemctl enable --now pipeline-leak-ui
echo "user-data done"
