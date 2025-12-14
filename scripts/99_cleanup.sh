#!/usr/bin/env bash
set -euo pipefail
ROOT="$(dirname "$0")/.."

kubectl delete -f "$ROOT/k8s/app-service.yaml" --ignore-not-found
kubectl delete -f "$ROOT/k8s/app-deployment.yaml" --ignore-not-found
