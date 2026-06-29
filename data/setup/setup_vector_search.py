#!/usr/bin/env python3
"""Ensure the Vector Search endpoint + delta sync index that backs the Knowledge
Assistant, FROM CODE. Idempotent: creates the endpoint and index if missing,
otherwise reports their status. Run after the documents are chunked and embedded
into <catalog>.akzo_docs.chunks_embedded.

Usage:
  python3 data/setup/setup_vector_search.py --catalog <your-catalog>
  # add --profile <profile> only when running from a laptop against a remote workspace
"""
from __future__ import annotations

import argparse
import os
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingVectorColumn,
    PipelineType,
    VectorIndexType,
)


def _resolve_catalog() -> str:
    """Catalog from --catalog / --catalog=x / AKZO_CATALOG. No workspace-specific
    default. Validated as a plain identifier since it is interpolated into names."""
    import re as _re
    cat = None
    for i, a in enumerate(sys.argv):
        if a == "--catalog" and i + 1 < len(sys.argv):
            cat = sys.argv[i + 1]; break
        if a.startswith("--catalog="):
            cat = a.split("=", 1)[1]; break
    cat = cat or os.environ.get("AKZO_CATALOG")
    if not cat:
        sys.exit("Set --catalog <name> or AKZO_CATALOG (your Unity Catalog, e.g. your lab catalog).")
    if not _re.fullmatch(r"[A-Za-z0-9_]+", cat):
        sys.exit(f"Unsafe catalog name: {cat!r}. Use only letters, digits, and underscore.")
    return cat


CAT = _resolve_catalog()
DOCS = f"{CAT}.akzo_docs"
VS_ENDPOINT = os.environ.get("AKZO_VS_ENDPOINT", "akzo_workshop_vs")
VS_INDEX = f"{DOCS}.chunks_idx"
SOURCE_TABLE = f"{DOCS}.chunks_embedded"
EMBED_DIM = int(os.environ.get("AKZO_EMBED_DIM", "1024"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
    ap.add_argument("--catalog", default=os.environ.get("AKZO_CATALOG"))  # already resolved into CAT
    args = ap.parse_args()
    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()

    # 1. Endpoint
    endpoints = {e.name for e in w.vector_search_endpoints.list_endpoints()}
    if VS_ENDPOINT in endpoints:
        print(f"[endpoint] {VS_ENDPOINT} already exists")
    else:
        print(f"[endpoint] creating {VS_ENDPOINT} ...")
        w.vector_search_endpoints.create_endpoint_and_wait(name=VS_ENDPOINT, endpoint_type="STANDARD")

    # 2. Index
    try:
        idx = w.vector_search_indexes.get_index(index_name=VS_INDEX)
        print(f"[index] {VS_INDEX} already exists")
    except NotFound:
        print(f"[index] creating {VS_INDEX} from {SOURCE_TABLE} ...")
        w.vector_search_indexes.create_index(
            name=VS_INDEX,
            endpoint_name=VS_ENDPOINT,
            primary_key="chunk_id",
            index_type=VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=SOURCE_TABLE,
                pipeline_type=PipelineType.TRIGGERED,
                embedding_vector_columns=[
                    EmbeddingVectorColumn(name="embedding", embedding_dimension=EMBED_DIM)
                ],
            ),
        )
        idx = w.vector_search_indexes.get_index(index_name=VS_INDEX)

    # 3. Report readiness
    status = idx.status
    ready = getattr(status, "ready", None)
    print(f"[index] detailed_state={getattr(status, 'detailed_state', None)} "
          f"ready={ready} "
          f"indexed_rows={getattr(status, 'indexed_row_count', None)}")
    if ready:
        print("\nKnowledge Assistant backbone is ready. Point a Knowledge Assistant at:")
    else:
        print("\nIndex is still building. It will be queryable once ready. Backbone target:")
    print(f"  endpoint: {VS_ENDPOINT}")
    print(f"  index:    {VS_INDEX}")


if __name__ == "__main__":
    main()
