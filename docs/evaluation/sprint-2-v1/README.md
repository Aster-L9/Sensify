# Supplied Sprint 2 evaluation snapshot

These files were supplied with the Sprint 2 archive: `metrics.json`, `report.md`, `manifest.json`, and `DATA_CARD.md`. They document the original v1 evaluation and its two missed development targets. They are reference evidence for development evaluation. The runtime model is generated locally; charter acceptance remains tracked separately. A fresh generation/training run during source preparation reproduced the archived metrics and target comparisons exactly.

The generated CSV dataset, serialized model and local database are deliberately excluded. Regenerate and activate a model with the instructions in [SETUP](../../SETUP.md). New metrics are written under the ignored `backend/model_store/vN/` directory. The report-formatting regression test reads this archived metrics snapshot.
