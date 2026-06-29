"""Vocareum lab_setup — runs on lab creation.

Good uses: create lab-scoped resources, preload shared demo data, attach
session permissions. For this workshop this is the natural place to ensure the
coatings data exists before the learner starts, if it was not provisioned at the
workspace level.

Portability rule: read the catalog from AKZO_CATALOG (set by the Vocareum
config) or let the loaders discover the current catalog. Do not hardcode a
profile, warehouse id, or Lakebase instance — the loaders discover the first SQL
warehouse and use ambient auth inside the workspace.

Anything created here must be removed in lab_end.py.
"""

import os
import subprocess


def main():
    catalog = os.environ.get("AKZO_CATALOG")
    print(f"[lab_setup] catalog={catalog or 'will be discovered by loaders'}")

    # Enable to provision the shared coatings data per lab. Idempotent loaders,
    # safe to re-run. Requires AKZO_CATALOG set in the lab environment.
    provision = os.environ.get("AKZO_PROVISION_ON_LAB", "false").lower() == "true"
    if provision and catalog:
        steps = [
            ["python", "data/generate_finance.py"],
            ["python", "data/generate_scm.py"],
            ["python", "data/generate_commercial.py"],
            ["python", "data/load_to_uc.py", "--catalog", catalog],
            ["python", "data/setup/setup_vector_search.py", "--catalog", catalog],
            ["python", "data/setup/setup_genie_spaces.py", "--catalog", catalog],
        ]
        for cmd in steps:
            print("[lab_setup] run:", " ".join(cmd))
            subprocess.run(cmd, check=True)
        print("[lab_setup] data provisioned")
    else:
        print("[lab_setup] skipping provisioning (set AKZO_PROVISION_ON_LAB=true and AKZO_CATALOG to enable)")


if __name__ == "__main__":
    main()
