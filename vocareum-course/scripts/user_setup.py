"""Vocareum user_setup — runs when a lab user is created.

Good uses: create user-specific folders, grant user-specific permissions, seed
small personalized resources. Keep it light — heavy/shared resources belong in
workspace_init.py or lab_setup.py.

Portability rule: do not hardcode catalog, profile, warehouse, or Lakebase
instance. Read them from the environment provided by the Vocareum config.

Anything created here must be removed in lab_end.py.
"""

import os


def main():
    user = os.environ.get("VOCAREUM_USER") or os.environ.get("USER") or "unknown"
    catalog = os.environ.get("AKZO_CATALOG")
    print(f"[user_setup] user={user} catalog={catalog or 'discovered at runtime'}")

    # Example (enable if your design needs per-user isolation):
    #   - create a personal schema:  CREATE SCHEMA IF NOT EXISTS {catalog}.user_{safe_user}
    #   - grant the user read on the shared coatings schemas
    # Whatever you create here, delete it in lab_end.py.

    print("[user_setup] done (no-op by default)")


if __name__ == "__main__":
    main()
