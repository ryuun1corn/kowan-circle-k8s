#!/usr/bin/env bash
set -euo pipefail

# Deploy app to Kubernetes (no ingress). Exposes NodePort 30080.
# Requirements:
# - Image circle-app:1.0 built to containerd (scripts/03_build_image.sh)
# - Adjust env in k8s/app-deployment.yaml (RP_ID, ORIGIN, SESSION_SECRET)
#
# Usage:
#   ./05_deploy.sh

ROOT="$(dirname "$0")/.."

kubectl apply -f "$ROOT/k8s/app-deployment.yaml"
kubectl apply -f "$ROOT/k8s/app-service.yaml"

echo "Waiting for pods..."
kubectl rollout status deploy/circle-app --timeout=120s

echo "Deployed."
kubectl get svc circle-app-svc -o wide
