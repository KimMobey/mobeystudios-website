#!/usr/bin/env bash
# Deploy the built Hugo site to the S3 bucket created by the CloudFormation stack,
# then invalidate the CloudFront distribution so changes are visible immediately.
#
# Usage:
#   ./infrastructure/deploy.sh              # uses default stack name and ./public
#   STACK_NAME=kimmobey-site ./infrastructure/deploy.sh
#   ./infrastructure/deploy.sh path/to/public
#
# Prerequisites:
#   - aws CLI v2 configured with credentials that can read the stack and write to S3+CloudFront.
#   - The CloudFormation stack from ./cloudformation.yaml is already deployed.
#   - Hugo has been built (`hugo`) so ./public exists.

set -euo pipefail

STACK_NAME="${STACK_NAME:-kimmobey-site}"
REGION="${AWS_REGION:-eu-west-1}"
SOURCE_DIR="${1:-public}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "error: source directory '$SOURCE_DIR' does not exist. Run 'hugo' first." >&2
  exit 1
fi

echo "==> Resolving stack outputs from $STACK_NAME ($REGION)"

BUCKET_NAME=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='${STACK_NAME}-SiteBucketName'].Value" \
  --output text)

DISTRIBUTION_ID=$(aws cloudformation list-exports \
  --region "$REGION" \
  --query "Exports[?Name=='${STACK_NAME}-DistributionId'].Value" \
  --output text)

if [[ -z "$BUCKET_NAME" || "$BUCKET_NAME" == "None" ]]; then
  echo "error: could not resolve SiteBucketName export for stack $STACK_NAME" >&2
  exit 1
fi

echo "    bucket:       $BUCKET_NAME"
echo "    distribution: ${DISTRIBUTION_ID:-<none>}"

echo "==> Syncing $SOURCE_DIR/ to s3://$BUCKET_NAME/"
aws s3 sync "$SOURCE_DIR/" "s3://$BUCKET_NAME/" \
  --delete \
  --region "$REGION"

if [[ -n "$DISTRIBUTION_ID" && "$DISTRIBUTION_ID" != "None" ]]; then
  echo "==> Creating CloudFront invalidation for /*"
  aws cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths '/*' \
    --query 'Invalidation.Id' \
    --output text
fi

echo "==> Done."
