#!/usr/bin/env bash
set -euo pipefail

# Build the application image into containerd (namespace k8s.io)
cd "$(dirname "$0")/../app"

sudo nerdctl --namespace k8s.io build -t circle-app:1.0 .

echo "Built image: circle-app:1.0"
sudo nerdctl --namespace k8s.io images | grep circle-app || true
