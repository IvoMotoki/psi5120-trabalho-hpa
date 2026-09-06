#!/usr/bin/env bash
# Run one Minikube HPA variant and rename the generated evidence log with a label.
set -euo pipefail

LABEL="${1:?Usage: run_minikube_hpa_variant.sh <label> <hpa-manifest> [context] [load_s] [post_s] [generators]}"
HPA_MANIFEST="${2:?Usage: run_minikube_hpa_variant.sh <label> <hpa-manifest> [context] [load_s] [post_s] [generators]}"
CONTEXT="${3:-hpa-2026}"
LOAD_SECONDS="${4:-240}"
POST_SECONDS="${5:-720}"
GENERATORS="${6:-6}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$DIR/evidencias/minikube"

echo "== Applying HPA variant: $LABEL =="
kubectl --context "$CONTEXT" apply -f "$HPA_MANIFEST"
kubectl --context "$CONTEXT" -n tf-hpa scale deployment/php-apache --replicas=1
kubectl --context "$CONTEXT" -n tf-hpa rollout status deployment/php-apache --timeout=240s

echo "== Waiting briefly for a stable pre-load sample =="
sleep 30

before_list="$(mktemp)"
after_list="$(mktemp)"
find "$EVIDENCE_DIR" -maxdepth 1 -type f -name 'hpa_timeline_*.log' -printf '%f\n' | sort > "$before_list"

"$DIR/scripts/load_test.sh" minikube "$CONTEXT" "$LOAD_SECONDS" "$POST_SECONDS" "$GENERATORS"

find "$EVIDENCE_DIR" -maxdepth 1 -type f -name 'hpa_timeline_*.log' -printf '%f\n' | sort > "$after_list"
new_log="$(comm -13 "$before_list" "$after_list" | tail -n 1)"

rm -f "$before_list" "$after_list"

if [[ -z "$new_log" ]]; then
  echo "Could not identify newly generated log in $EVIDENCE_DIR" >&2
  exit 1
fi

renamed="${new_log%.log}_${LABEL}.log"
mv "$EVIDENCE_DIR/$new_log" "$EVIDENCE_DIR/$renamed"
echo "Renamed evidence log to: $EVIDENCE_DIR/$renamed"
