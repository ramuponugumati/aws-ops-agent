#!/bin/bash
set -euo pipefail

# ============================================================
# AWS Ops Agent — Deploy to Bedrock AgentCore
# ============================================================
# Prerequisites:
#   pip install bedrock-agentcore-starter-toolkit
#
# Usage:
#   cd deploy/agentcore
#   ./deploy.sh
#   ./deploy.sh --local    (test locally first)
#   ./deploy.sh --invoke "Scan my account for zombie resources"
# ============================================================

ACTION="${1:-deploy}"

case "$ACTION" in
  --local)
    echo "🧪 Testing locally..."
    agentcore configure --entrypoint agent.py
    agentcore launch --local
    ;;
  --invoke)
    PROMPT="${2:-What skills do you have?}"
    echo "💬 Invoking agent: $PROMPT"
    agentcore invoke "{\"prompt\": \"$PROMPT\"}"
    ;;
  --destroy)
    echo "🗑  Destroying agent..."
    agentcore destroy
    ;;
  *)
    echo "🚀 Deploying to AgentCore..."
    echo ""
    echo "Step 1: Configure"
    agentcore configure --entrypoint agent.py
    echo ""
    echo "Step 2: Deploy"
    agentcore launch
    echo ""
    echo "✅ Deployed! Test with:"
    echo "  agentcore invoke '{\"prompt\": \"What skills do you have?\"}'"
    echo "  agentcore invoke '{\"prompt\": \"Scan my account for security issues\"}'"
    echo "  agentcore invoke '{\"prompt\": \"Run all skills and summarize findings\"}'"
    ;;
esac
