#!/bin/bash
# Sets GitHub repository secrets and variables required by ai-teammate.yml
# Usage: ./setup-github.sh [repo] [env-file]
# Example: ./setup-github.sh ai-teammate/mytube dmtools.env

set -e

REPO="${1:-ai-teammate/mytube}"
ENV_FILE="${2:-dmtools.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found"
  exit 1
fi

# Read a value from env file by key (skips commented-out lines)
get() {
  grep -m1 "^${1}=" "$ENV_FILE" | cut -d'=' -f2-
}

set_secret() {
  local name="$1" value="$2"
  if [ -n "$value" ]; then
    echo "  secret: $name"
    gh secret set "$name" --body "$value" --repo "$REPO"
  else
    echo "  skip   $name (not found in $ENV_FILE)"
  fi
}

set_var() {
  local name="$1" value="$2"
  if [ -n "$value" ]; then
    echo "  var:    $name"
    gh variable set "$name" --body "$value" --repo "$REPO"
  else
    echo "  skip   $name (not found in $ENV_FILE)"
  fi
}

echo ""
echo "Repo: $REPO"
echo "Env:  $ENV_FILE"
echo ""

echo "==> Secrets"
set_secret "PAT_TOKEN"         "$(get PAT_TOKEN)"
set_secret "CURSOR_API_KEY"    "$(get CURSOR_API_KEY)"
set_secret "JIRA_EMAIL"        "$(get JIRA_EMAIL)"
set_secret "JIRA_API_TOKEN"    "$(get JIRA_API_TOKEN)"
set_secret "GEMINI_API_KEY"    "$(get GEMINI_API_KEY)"
set_secret "FIGMA_TOKEN"       "$(get FIGMA_TOKEN)"
set_secret "CODEMIE_API_KEY"   "$(get CODEMIE_API_KEY)"

echo ""
echo "==> Variables"
set_var "JIRA_BASE_PATH"                        "$(get JIRA_BASE_PATH)"
set_var "JIRA_AUTH_TYPE"                        "$(get JIRA_AUTH_TYPE)"
set_var "JIRA_TRANSFORM_CUSTOM_FIELDS_TO_NAMES" "$(get JIRA_TRANSFORM_CUSTOM_FIELDS_TO_NAMES)"
set_var "CONFLUENCE_BASE_PATH"                  "$(get CONFLUENCE_BASE_PATH)"
set_var "CONFLUENCE_GRAPHQL_PATH"               "$(get CONFLUENCE_GRAPHQL_PATH)"
set_var "FIGMA_BASE_PATH"                       "$(get FIGMA_BASE_PATH)"
set_var "AI_AGENT_PROVIDER"                     "$(get AI_AGENT_PROVIDER)"
set_var "CODEMIE_BASE_URL"                      "$(get CODEMIE_BASE_URL)"
set_var "CODEMIE_MODEL"                         "$(get CODEMIE_MODEL)"
set_var "CODEMIE_MAX_TURNS"                     "$(get CODEMIE_MAX_TURNS)"

echo ""
echo "Done."
