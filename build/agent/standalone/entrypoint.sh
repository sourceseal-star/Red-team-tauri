#!/bin/sh
# Wrapper para correr el agente en cron / sin docker
set -e
cd "$(dirname "$0")/../.."
exec python3 runner/orchestrator.py "$@"
