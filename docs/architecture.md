# Architecture

The application follows ports-and-adapters boundaries. Typer, FastAPI, and React call the same `ExpertSystemService`. Ingestion converts local UTF-8 Markdown, text, JSON, and YAML into hashed source sections. Providers may only return the versioned Pydantic knowledge IR. Deterministic renderers produce Prolog, CLIPS, SMT-LIB, and ASP artifacts.

SQLite stores version state, activation pointers, source metadata, and audit events. The registry API stops modifying artifact directories after finalization, but filesystem permissions do not yet enforce immutability and artifact checksums are not reverified before every execution. Activation follows an ordered state machine; current checks cover typed IR/evidence parsing and deterministic rendering, not full native syntax and semantic certification. The previous version is superseded rather than deleted and remains eligible for rollback.

The deterministic routing policy maps relational work to Prolog, forward chaining to CLIPS, constraint and optimization capability labels to Z3, and planning/non-monotonic labels to Clingo. Optimization objectives and typed cross-engine dataflow are not implemented; callers should use one supported capability per query. An LLM proposal may suggest a typed DAG, but host policy rejects unknown engines, capability mismatches, missing dependencies, cycles, and unavailable runtimes.

The reference to Karpathy's “LLM wiki” is interpreted as iterative source ingestion, structured synthesis, provenance-aware generation, and incremental regeneration. No canonical repository explicitly named “LLM wiki” was identified, and this project does not claim compatibility with one.
