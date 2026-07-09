#!/usr/bin/env bash
# Session-start status check: is this machine safe to work from, and do git,
# GitHub, and the live site all agree?
#
# Run this before starting work — especially on a machine you haven't used
# recently, or after someone else (or another laptop) may have deployed.
#
# Four surfaces, in order:
#   1. Working tree vs last commit    (uncommitted / untracked work)
#   2. Local main vs origin/main      (fetches, then reports ahead/behind)
#   3. Live site vs origin/main       (via /build-info.json build stamp)
#   4. Environment + doc claims       (hugo, aws credentials, CloudFront
#                                      serving kimmobey.com, pricelist gate)
#
# Exit code: 0 if everything is green (warnings allowed), 1 if anything is red.
#
# Usage:
#   ./infrastructure/preflight.sh

set -uo pipefail   # deliberately NOT -e: run every check, report at the end

DOMAIN="https://kimmobey.com"
# Keep in step with deploy.sh.
MIN_HUGO_VERSION="0.143.0"

FAILURES=0
WARNINGS=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

# Run from the repo root so git behaves predictably regardless of cwd.
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# --- 1. Working tree ----------------------------------------------------------
echo "==> Working tree"
PORCELAIN=$(git status --porcelain 2>/dev/null)
if [[ -z "$PORCELAIN" ]]; then
  ok "clean — no uncommitted or untracked files"
else
  COUNT=$(printf '%s\n' "$PORCELAIN" | wc -l)
  warn "$COUNT uncommitted/untracked file(s) — work exists ONLY on this machine:"
  printf '%s\n' "$PORCELAIN" | sed 's/^/      /'
fi

# --- 2. Sync with origin/main ---------------------------------------------------
echo "==> GitHub (origin/main)"
if git fetch origin main --quiet 2>/dev/null; then
  AHEAD=$(git rev-list --count origin/main..HEAD)
  BEHIND=$(git rev-list --count HEAD..origin/main)
  if [[ "$AHEAD" -eq 0 && "$BEHIND" -eq 0 ]]; then
    ok "in sync with origin/main ($(git rev-parse --short HEAD))"
  else
    [[ "$AHEAD"  -gt 0 ]] && fail "$AHEAD commit(s) NOT on GitHub — push before deploying or switching machines"
    [[ "$BEHIND" -gt 0 ]] && fail "$BEHIND commit(s) behind GitHub — pull before editing or deploying"
  fi
else
  fail "could not fetch origin — check network or SSH keys (git fetch origin main)"
fi

# --- 3. Live site vs GitHub -----------------------------------------------------
echo "==> Live site ($DOMAIN)"
STAMP=$(curl -sf --max-time 15 "$DOMAIN/build-info.json" 2>/dev/null)
if [[ -z "$STAMP" ]]; then
  fail "no /build-info.json on the live site — deployed before build stamps existed, or site unreachable; redeploy to stamp it"
else
  LIVE_COMMIT=$(printf '%s' "$STAMP" | sed -nE 's/.*"commit":"([0-9a-f]+)".*/\1/p')
  LIVE_AT=$(printf '%s' "$STAMP" | sed -nE 's/.*"built_at":"([^"]+)".*/\1/p')
  LIVE_DIRTY=$(printf '%s' "$STAMP" | sed -nE 's/.*"dirty":(true|false).*/\1/p')
  ORIGIN_COMMIT=$(git rev-parse origin/main 2>/dev/null)
  if [[ -z "$LIVE_COMMIT" ]]; then
    fail "build-info.json present but unparseable: $STAMP"
  elif [[ "$LIVE_COMMIT" == "$ORIGIN_COMMIT" ]]; then
    ok "live site matches origin/main (${LIVE_COMMIT:0:7}, built $LIVE_AT)"
  elif git merge-base --is-ancestor "$LIVE_COMMIT" "$ORIGIN_COMMIT" 2>/dev/null; then
    warn "live site is BEHIND GitHub (live ${LIVE_COMMIT:0:7}, origin $(git rev-parse --short origin/main)) — pushed work not yet deployed"
  else
    fail "live commit ${LIVE_COMMIT:0:7} is NOT an ancestor of origin/main — live was deployed from unpushed or unknown work"
  fi
  [[ "$LIVE_DIRTY" == "true" ]] && warn "live build was stamped from a DIRTY tree — live may contain uncommitted changes"
fi

# --- 4. Environment + doc claims ------------------------------------------------
echo "==> Environment"
if command -v hugo >/dev/null 2>&1; then
  INSTALLED_HUGO=$(hugo version | sed -nE 's/.*hugo v([0-9]+\.[0-9]+\.[0-9]+).*/\1/p')
  sorted=$(printf '%s\n%s\n' "$MIN_HUGO_VERSION" "$INSTALLED_HUGO" | sort -V)
  if [[ "${sorted%%$'\n'*}" == "$MIN_HUGO_VERSION" ]]; then
    ok "hugo $INSTALLED_HUGO (>= $MIN_HUGO_VERSION)"
  else
    fail "hugo $INSTALLED_HUGO is older than required $MIN_HUGO_VERSION"
  fi
else
  fail "hugo not found on PATH — install it before editing (see CLAUDE.md)"
fi

if command -v aws >/dev/null 2>&1 && aws sts get-caller-identity >/dev/null 2>&1; then
  ok "aws CLI configured — deploying is possible from this machine"
else
  warn "aws CLI missing or unconfigured — you can edit and push, but NOT deploy from this machine"
fi

# Match with [[ == * ]] rather than piping to grep -q: under pipefail,
# grep -q exits at the first match, the writer catches SIGPIPE on any body
# larger than the pipe buffer, and the check false-fails.
HOME_HEADERS=$(curl -sfI --max-time 15 "$DOMAIN/" 2>/dev/null)
if [[ "${HOME_HEADERS,,}" == *"via:"*"cloudfront"* ]]; then
  ok "kimmobey.com is served by CloudFront (docs claim holds)"
else
  fail "kimmobey.com is NOT serving via CloudFront — production-status docs are stale, re-verify before trusting them"
fi

PRICELIST_BODY=$(curl -sf --max-time 15 "$DOMAIN/good-things-happen/" 2>/dev/null)
if [[ "$PRICELIST_BODY" == *"pricelist-gate"* ]]; then
  ok "pricelist gate reachable at /good-things-happen/"
else
  fail "pricelist page missing or gate absent at /good-things-happen/"
fi

# --- Summary --------------------------------------------------------------------
echo
if [[ "$FAILURES" -gt 0 ]]; then
  printf '\033[31m==> %d problem(s), %d warning(s) — fix the red items before working.\033[0m\n' "$FAILURES" "$WARNINGS"
  exit 1
elif [[ "$WARNINGS" -gt 0 ]]; then
  printf '\033[33m==> All critical checks passed, %d warning(s) above.\033[0m\n' "$WARNINGS"
else
  echo "==> All green. git, GitHub, and the live site agree."
fi
