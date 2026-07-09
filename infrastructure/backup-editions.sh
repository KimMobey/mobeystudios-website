#!/usr/bin/env bash
# Back up local-only repo data to the private backup bucket.
#
# editions/ (private sales + edition records) and _dev/ (briefs, specs,
# design references) are deliberately gitignored: they must never be
# committed or deployed. That means they exist ONLY on the working machine
# unless this script runs. Run it after any editions change, and always
# before travel or switching machines.
#
# The sync uses --delete (a clean mirror of the local state); the bucket is
# versioned, so accidentally deleted or overwritten files remain recoverable
# for 180 days (see infrastructure/backups.yaml).
#
# Usage:
#   ./infrastructure/backup-editions.sh
#   BACKUP_STACK_NAME=kimmobey-backups ./infrastructure/backup-editions.sh
#
# Prerequisites:
#   - aws CLI v2 configured with credentials for the backup bucket
#   - The stack from ./backups.yaml is already deployed

set -euo pipefail

STACK_NAME="${BACKUP_STACK_NAME:-kimmobey-backups}"
REGION="${AWS_REGION:-eu-west-1}"
BACKUP_DIRS=(editions _dev)

# Run from the repo root so paths behave predictably regardless of cwd.
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "==> Resolving backup bucket from $STACK_NAME ($REGION)"
BUCKET_NAME=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='${STACK_NAME}-BackupBucketName'].Value" \
  --output text)

if [[ -z "$BUCKET_NAME" || "$BUCKET_NAME" == "None" ]]; then
  echo "error: could not resolve BackupBucketName export for stack $STACK_NAME" >&2
  echo "       deploy it first: aws cloudformation deploy \\" >&2
  echo "         --template-file infrastructure/backups.yaml \\" >&2
  echo "         --stack-name $STACK_NAME --region $REGION" >&2
  exit 1
fi
echo "    bucket: $BUCKET_NAME"

for DIR in "${BACKUP_DIRS[@]}"; do
  if [[ ! -d "$DIR" ]]; then
    echo "==> Skipping $DIR/ (not present on this machine)"
    continue
  fi
  echo "==> Backing up $DIR/ to s3://$BUCKET_NAME/$DIR/"
  aws s3 sync "$DIR/" "s3://$BUCKET_NAME/$DIR/" \
    --delete \
    --region "$REGION" \
    --only-show-errors
  COUNT=$(find "$DIR" -type f | wc -l)
  echo "    $COUNT local file(s) mirrored"
done

echo "==> Done. Restore with: aws s3 sync s3://$BUCKET_NAME/<dir>/ <dir>/"
