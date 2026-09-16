# Underwriting knowledge scaffolding

Canonical design: `../docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`.

`source_registry.json` records official discovery metadata, including retrieval limitations. All records are pending review and inactive. `retrieved_at` and `checksum` remain null because no original guide bytes were ingested. `checked_at` records research, not ingestion. Do not hash a URL or this JSON and call it a source checksum.

`agency/*/pack.json` establishes five independent coverage packs. `lenders/` and `investor/` keep overlay/product scope separate. No real underwriting formula is shipped. Runtime code and approval enforcement will be delivered in later phases, through Flo-owned Hermes extensions.

