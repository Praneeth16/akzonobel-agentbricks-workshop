"""Vocareum lab_end — runs when the learner ends the lab or the session expires
(only when end behavior is set to terminate resources, which the FE guide
recommends).

This is the cleanup script. Delete or reap anything the setup scripts created.
The Vocareum guidance is explicit: anything created in workspace_init / user_setup
/ lab_setup must be cleaned up here.

Portability rule: read the catalog from the environment; do not hardcode a
profile, warehouse, or Lakebase instance.

By default this is a no-op because the shared coatings data is typically reused
across labs. Only enable teardown for resources that were created per-lab or
per-user.
"""

import os


def main():
    catalog = os.environ.get("AKZO_CATALOG")
    user = os.environ.get("VOCAREUM_USER") or os.environ.get("USER") or "unknown"
    print(f"[lab_end] cleanup for user={user} catalog={catalog or 'n/a'}")

    # Mirror whatever you created in setup. Examples:
    #   - DROP SCHEMA IF EXISTS {catalog}.user_{safe_user} CASCADE   (if user_setup created it)
    #   - delete per-lab Genie spaces / vector indexes (only if lab_setup created them per-lab)
    # Do NOT drop the shared coatings schemas if they are reused across labs.

    print("[lab_end] done (no-op by default — enable teardown only for per-lab/per-user resources)")


if __name__ == "__main__":
    main()
