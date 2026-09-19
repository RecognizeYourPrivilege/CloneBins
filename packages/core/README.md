# clonebins-core

Shared Python pipeline used by every CloneBins client:

1. Scan image folders
2. Detect / embed faces (and optional body/appearance)
3. Cluster identities
4. Export `subject_XX/` bins

Install from the monorepo root:

```bash
pip install -e packages/core
```

The CLI (`packages/cli`) is the supported interface for now. Import `clonebins_core.pipeline.run_pipeline` if you are wiring another UI.
