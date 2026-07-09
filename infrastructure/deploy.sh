#!/usr/bin/env bash
# Build the Hugo site and deploy it to S3, then invalidate CloudFront.
#
# Single source of truth for deploying. It will:
#   1. Refuse if hugo is missing or older than the minimum the templates need.
#   2. Refuse if there are uncommitted changes in deploy-relevant paths
#      (override with FORCE_DIRTY=1).
#   3. Refuse if local main is out of sync with origin/main — deploying
#      unpushed commits means another machine clones stale content and later
#      overwrites live; deploying while behind reverts live to older content
#      (override with FORCE_SYNC=1).
#   4. Build hugo. If hugo fails, the deploy is aborted — no stale upload.
#   5. Stamp the build with /build-info.json (commit SHA + UTC timestamp) so
#      any machine can ask the live site which commit it was built from.
#   6. Sync ./public to S3 with --delete (orphan files removed).
#   7. Invalidate CloudFront.
#
# Usage:
#   ./infrastructure/deploy.sh
#   STACK_NAME=kimmobey-site ./infrastructure/deploy.sh
#   FORCE_DIRTY=1 ./infrastructure/deploy.sh    # bypass the git-dirty check
#   FORCE_SYNC=1 ./infrastructure/deploy.sh     # bypass the origin-sync check
#   SKIP_BUILD=1 ./infrastructure/deploy.sh     # use existing public/ as-is
#
# Prerequisites:
#   - hugo on PATH, version >= MIN_HUGO_VERSION
#   - aws CLI v2 configured with credentials that can read the stack and
#     write to S3+CloudFront
#   - The CloudFormation stack from ./cloudformation.yaml is already deployed

set -euo pipefail

# Bump this when layouts/shortcodes start using newer hugo features.
# hugo.Data (used in layouts/index.html) requires >= 0.143.
MIN_HUGO_VERSION="0.143.0"

STACK_NAME="${STACK_NAME:-kimmobey-site}"
REGION="${AWS_REGION:-eu-west-1}"
SOURCE_DIR="public"

# Run from the repo root so git + hugo behave predictably regardless of cwd.
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# --- 1. Hugo present and recent enough ---------------------------------------
if ! command -v hugo >/dev/null 2>&1; then
  echo "error: hugo not found on PATH" >&2
  exit 1
fi
INSTALLED_HUGO=$(hugo version | sed -nE 's/.*hugo v([0-9]+\.[0-9]+\.[0-9]+).*/\1/p')
if [[ -z "$INSTALLED_HUGO" ]]; then
  echo "error: could not parse hugo version from: $(hugo version)" >&2
  exit 1
fi
sorted=$(printf '%s\n%s\n' "$MIN_HUGO_VERSION" "$INSTALLED_HUGO" | sort -V)
if [[ "${sorted%%$'\n'*}" != "$MIN_HUGO_VERSION" ]]; then
  echo "error: hugo $INSTALLED_HUGO is older than the required $MIN_HUGO_VERSION" >&2
  echo "       upgrade with the latest .deb from https://github.com/gohugoio/hugo/releases" >&2
  exit 1
fi

# --- 2. Refuse if deploy-relevant paths have uncommitted changes -------------
# Admin code (admin_server.py, admin/, static/admin/) is intentionally excluded
# — it runs locally only and admin-WIP shouldn't block public-content deploys.
DEPLOY_PATHS=(content layouts data assets archetypes hugo.toml)
# static/ minus static/admin/ — easier to glob-include and then filter.
if [[ "${FORCE_DIRTY:-0}" != "1" ]]; then
  DIRTY=$(git status --porcelain -- "${DEPLOY_PATHS[@]}" static/ 2>/dev/null \
          | grep -v ' static/admin/' || true)
  if [[ -n "$DIRTY" ]]; then
    echo "error: uncommitted changes in deploy-relevant paths:" >&2
    echo "$DIRTY" >&2
    echo "       commit (and push) first, or set FORCE_DIRTY=1 to override" >&2
    exit 1
  fi
fi

# --- 3. Refuse if local main is out of sync with origin/main -----------------
# Deploying unpushed commits puts content live that GitHub doesn't have: the
# next machine to clone gets stale content and silently overwrites live on its
# next deploy. Deploying while behind reverts live to older content.
if [[ "${FORCE_SYNC:-0}" != "1" ]]; then
  echo "==> Checking sync with origin/main"
  if ! git fetch origin main --quiet; then
    echo "error: could not fetch origin/main to verify sync" >&2
    echo "       check network/SSH keys, or set FORCE_SYNC=1 to override" >&2
    exit 1
  fi
  AHEAD=$(git rev-list --count origin/main..HEAD)
  BEHIND=$(git rev-list --count HEAD..origin/main)
  if [[ "$AHEAD" -gt 0 ]]; then
    echo "error: local branch is $AHEAD commit(s) ahead of origin/main" >&2
    echo "       push first (git push origin main), or set FORCE_SYNC=1 to override" >&2
    exit 1
  fi
  if [[ "$BEHIND" -gt 0 ]]; then
    echo "error: local branch is $BEHIND commit(s) behind origin/main" >&2
    echo "       deploying now would revert live to older content" >&2
    echo "       pull first (git pull origin main), or set FORCE_SYNC=1 to override" >&2
    exit 1
  fi
fi

# --- 4. Build hugo (clean) ---------------------------------------------------
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "==> Building site (hugo $INSTALLED_HUGO)"
  rm -rf "$SOURCE_DIR"
  hugo
fi
if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "error: $SOURCE_DIR/ does not exist after build" >&2
  exit 1
fi

# --- 5. Stamp the build ------------------------------------------------------
# /build-info.json lets any machine ask the live site which commit it was
# built from (preflight.sh compares it against origin/main). `dirty` records
# whether the tree had uncommitted changes anywhere at build time.
COMMIT_SHA=$(git rev-parse HEAD)
TREE_DIRTY=$([[ -n "$(git status --porcelain 2>/dev/null)" ]] && echo true || echo false)
printf '{"commit":"%s","built_at":"%s","dirty":%s}\n' \
  "$COMMIT_SHA" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TREE_DIRTY" \
  > "$SOURCE_DIR/build-info.json"
echo "==> Stamped build-info.json ($COMMIT_SHA, dirty=$TREE_DIRTY)"

# --- 6. Resolve AWS stack outputs --------------------------------------------
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

# --- 7. Sync + invalidate ----------------------------------------------------
echo "==> Syncing $SOURCE_DIR/ to s3://$BUCKET_NAME/"
# Exclude any `_src/` directory: source files (jpg/png/raw captures) live
# alongside published .webp images for findability but must never be deployed.
# Exclude admin/: the local editing UI (static/admin/) ends up in public/ via
# Hugo's static copy but is local-only tooling — it must not be on the live
# site. (Its /api/ backend only exists on the local admin_server.py anyway.)
aws s3 sync "$SOURCE_DIR/" "s3://$BUCKET_NAME/" \
  --delete \
  --exclude '*/_src/*' \
  --exclude 'admin/*' \
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
