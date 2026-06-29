"""Vocareum workspace_init — runs once when the workspace is created.

Use this only for shared, workspace-level prep that every lab user reuses:
shared catalog/schema, shared demo assets, common cluster policy.

Portability rule: nothing about a workspace is hardcoded. Read the catalog from
the environment or the current context; discover the warehouse. Do not bake in a
profile, catalog, warehouse id, or Lakebase instance.

For this workshop, the heavy shared setup (coatings tables, document volume,
Genie spaces, vector index) lives in `data/`. If you want it provisioned at
workspace creation rather than per-lab, call the loaders here. Otherwise leave
this as a no-op and provision per lab in `lab_setup.py`.
"""

import os


def main():
    catalog = os.environ.get("AKZO_CATALOG")  # set by the Vocareum workspace config; else discovered at notebook runtime
    print(f"[workspace_init] catalog={catalog or 'unset (discovered per notebook via current_catalog())'}")

    # To provision shared data at workspace creation, uncomment and ensure
    # AKZO_CATALOG is set in the workspace environment:
    #
    #   import subprocess
    #   subprocess.run(["python", "data/generate_finance.py"], check=True)
    #   subprocess.run(["python", "data/generate_scm.py"], check=True)
    #   subprocess.run(["python", "data/generate_commercial.py"], check=True)
    #   subprocess.run(["python", "data/load_to_uc.py", "--catalog", catalog], check=True)
    #   subprocess.run(["python", "data/setup/setup_vector_search.py", "--catalog", catalog], check=True)
    #   subprocess.run(["python", "data/setup/setup_genie_spaces.py", "--catalog", catalog], check=True)

    print("[workspace_init] done (no-op by default — see comments to enable shared provisioning)")


if __name__ == "__main__":
    main()
