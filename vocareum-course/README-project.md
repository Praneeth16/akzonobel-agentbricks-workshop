# Vocareum course package (additive layer)

This folder packages the workshop for delivery on **Vocareum** without changing
the repo's L100/L200/L300 ladder or the hackathon kit. The ladder notebooks stay
single-source in their tier folders; the build script assembles them into a
Vocareum bundle.

## Layout

```
vocareum-course/
├── README-project.md          # this file (for the workshop host, not learners)
├── course-image/              # 810x520 course tile (add the PNG before going public)
├── courseware/                # authored wrapper notebooks
│   ├── _AGENDA/00 - Start Here.ipynb
│   ├── 01 - Setup Check.ipynb
│   └── 99 - Wrap Up.ipynb
├── docs/README.md             # learner-facing right-pane README (-> /voc/docs)
├── scripts/                   # Vocareum lifecycle + the bundle builder
│   ├── build_bundle.py
│   ├── workspace_init.py
│   ├── user_setup.py
│   ├── lab_setup.py
│   └── lab_end.py
├── vocareum/akzonobel-agent-bricks.cfg   # course config (-> /voc/private/courseware)
└── dist/                      # built bundle zip (gitignored)
```

## Build the bundle

```bash
python vocareum-course/scripts/build_bundle.py
```

This stages, in order: the agenda + setup check, every L100 notebook (renamed
`1x - L100 - …`), L200/L300 (real notebooks when present, otherwise a
`coming soon` placeholder so the full structure is testable now), an optional
hackathon-kit pointer, and the wrap up. Output: `dist/akzonobel-agent-bricks-bundle.zip`.

The bundle keeps `.ipynb` format — Databricks imports it directly. Re-run after
L200/L300 are built and they are picked up automatically.

## Upload mapping (in Vocareum)

| Local file | Vocareum location |
|---|---|
| `dist/akzonobel-agent-bricks-bundle.zip` | `/voc/private/courseware` |
| `vocareum/akzonobel-agent-bricks.cfg` | `/voc/private/courseware` |
| `docs/README.md` | `/voc/docs` |
| `scripts/*.py` lifecycle scripts | course script area (workspace config) |

`cfg` entry path is `_AGENDA/00 - Start Here` — it must match the path inside the zip.

## Still done manually in Vocareum

Clone a template course (Clone by Copy) · set name/image/dates · Lab Type =
Databricks · session 240 min, end behavior = terminate · enable Timer + Readme
Button · upload bundle/cfg/README · test via Student View · make public + create
one access code (limit ~30) if direct enrollment.

## Notes

- **Portability:** notebooks default `catalog` to `current_catalog()`; lifecycle
  scripts read `AKZO_CATALOG` from the environment. Nothing hardcodes a
  workspace, profile, warehouse, or Lakebase instance.
- **Serverless (no classic cluster):** the cfg intentionally omits
  `cluster_config`, so no classic cluster is provisioned. The whole workshop is
  serverless: notebooks attach to **Serverless** notebook compute, SQL AI
  Functions run on a **Serverless SQL warehouse**, Agent Bricks / Genie /
  Knowledge Assistant are managed services, and short-term memory uses Lakebase
  (serverless Postgres). Nothing needs an `i3.xlarge`.
  - **Verify in Vocareum (unconfirmed against the official guideline — Confluence
    was unreachable when this was written):** in the cloned template, set the
    lab's default compute to **Serverless** and confirm a **Serverless SQL
    warehouse** exists for the SQL AI Functions notebook. If your Vocareum
    template *requires* a `cluster_config` block to launch, add a minimal
    serverless-mode cluster back; otherwise omitting it is correct.
- **Setup scripts:** `lab_setup.py` can provision the shared coatings data per
  lab (`AKZO_PROVISION_ON_LAB=true` + `AKZO_CATALOG`). Anything setup creates,
  `lab_end.py` must reap.
