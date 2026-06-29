"""AkzoNobel L300 Multi-domain Supervisor agent server.

The package mixes two import styles on purpose, matching the source apps it composes:
modules reused verbatim from the L200 apps (``databricks_client``, ``lakebase``,
``action_plane``, ``actions_api``) import each other as TOP-LEVEL modules, while the
supervisor-specific code imports them through the ``agent_server`` package. To make both
resolve regardless of the working directory (repo root for Apps/MLflow serving, or inside
``agent_server/`` for local dev), we put this package directory on ``sys.path`` once here.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
