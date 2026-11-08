#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# ROS2 (system PYTHONPATH) ships a broken pytest11 plugin; disable autoload.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/ "$@"
