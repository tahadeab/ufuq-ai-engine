#!/usr/bin/env bash
set -u
set -o pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8016}"
PDF_PATH="${1:-test_artifacts/python-tutorial.pdf}"
UPLOAD_JSON="$(curl -sS --fail --max-time 180 -X POST "$BASE_URL/sources/upload" -F "file=@$PDF_PATH;type=application/pdf")" || { echo 'UPLOAD_FAILED'; exit 2; }
printf '%s\n' "$UPLOAD_JSON" > test_artifacts/pdf_upload_result.json
SOURCE_ID="$(printf '%s' "$UPLOAD_JSON" | jq -r '.source_id')"
[ -n "$SOURCE_ID" ] && [ "$SOURCE_ID" != "null" ] || { echo 'NO_SOURCE_ID'; exit 3; }
JOB_JSON="$(curl -sS --fail --max-time 30 -X POST "$BASE_URL/jobs" -H 'Content-Type: application/json' -d "{\"source_id\":\"$SOURCE_ID\",\"job_type\":\"generate_path\",\"document_title\":\"خارطة تعلم Python\",\"context\":{\"language\":\"ar\",\"output_language\":\"Arabic\"}}")" || { echo 'JOB_CREATE_FAILED'; exit 4; }
printf '%s\n' "$JOB_JSON" > test_artifacts/pdf_job_created.json
JOB_ID="$(printf '%s' "$JOB_JSON" | jq -r '.job_id')"
[ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ] || { echo 'NO_JOB_ID'; exit 5; }
for i in $(seq 1 60); do
  STATUS_JSON="$(curl -sS --fail --max-time 30 "$BASE_URL/jobs/$JOB_ID")" || true
  printf '%s\n' "$STATUS_JSON" > test_artifacts/pdf_job_latest.json
  STATUS="$(printf '%s' "$STATUS_JSON" | jq -r '.status // empty')"
  printf 'poll=%s status=%s\n' "$i" "$STATUS"
  case "$STATUS" in
    review_required|approved|completed) printf '%s\n' "$STATUS_JSON"; exit 0 ;;
    failed) printf '%s\n' "$STATUS_JSON"; exit 6 ;;
  esac
  sleep 5
done
printf '%s\n' "TIMEOUT job=$JOB_ID"; exit 7
