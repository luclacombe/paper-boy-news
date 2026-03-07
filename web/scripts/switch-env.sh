#!/usr/bin/env bash
# Switch between local Supabase and cloud Supabase environments.
#
# Usage:
#   pnpm env:local   — switch to local Supabase (supabase start)
#   pnpm env:cloud   — switch back to cloud Supabase (production/staging)
#
# This copies the appropriate .env file to .env.local and restarts Next.js dev server.

set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  local)
    if [ ! -f .env.local.dev ]; then
      echo "Error: .env.local.dev not found."
      echo "Run: cp .env.local.example .env.local.dev"
      echo "Then fill in any local overrides."
      exit 1
    fi
    cp .env.local.dev .env.local
    echo "Switched to LOCAL Supabase (127.0.0.1:54321)"
    echo "Make sure 'supabase start' is running in the project root."
    ;;
  cloud)
    if [ ! -f .env.local.cloud ]; then
      echo "Error: .env.local.cloud not found."
      echo "Save your cloud .env.local as .env.local.cloud first."
      exit 1
    fi
    cp .env.local.cloud .env.local
    echo "Switched to CLOUD Supabase"
    ;;
  *)
    echo "Usage: $0 <local|cloud>"
    echo ""
    echo "  local  — Use local Supabase (supabase start)"
    echo "  cloud  — Use cloud Supabase (production/staging)"
    exit 1
    ;;
esac

echo "Restart your dev server (pnpm dev) for changes to take effect."
