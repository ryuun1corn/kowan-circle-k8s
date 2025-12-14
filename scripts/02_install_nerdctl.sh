#!/usr/bin/env bash
set -euo pipefail

# Install nerdctl (Docker CLI compatible) to build images for containerd.
# This is the simplest way to build a local image used by kubelet with containerd.

VERSION="1.7.6"
ARCH="amd64"
OS="linux"

tmp="$(mktemp -d)"
cd "$tmp"

curl -L -o nerdctl.tgz "https://github.com/containerd/nerdctl/releases/download/v${VERSION}/nerdctl-${VERSION}-${OS}-${ARCH}.tar.gz"
sudo tar -C /usr/local/bin -xzf nerdctl.tgz nerdctl

# Install buildkitd (for nerdctl build)
BK_VERSION="0.13.2"
curl -L -o buildkit.tgz "https://github.com/moby/buildkit/releases/download/v${BK_VERSION}/buildkit-v${BK_VERSION}.${OS}-${ARCH}.tar.gz"
sudo tar -C /usr/local/bin -xzf buildkit.tgz buildctl buildkitd

# systemd unit for buildkitd
cat <<'EOF' | sudo tee /etc/systemd/system/buildkit.service
[Unit]
Description=BuildKit daemon
After=network.target containerd.service
Requires=containerd.service

[Service]
ExecStart=/usr/local/bin/buildkitd --addr unix:///run/buildkit/buildkitd.sock
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now buildkit

echo "nerdctl and buildkitd installed."
