# MolCrafts CI Infrastructure Specification

**Status:** Draft
**Scope:** `molcrafts-ci`, `molcrafts-bench`, `molcrafts-molrec`
**Purpose:** Define a shared GitHub-native infrastructure for collecting, validating, tracking, publishing, and presenting developer-facing engineering data across the MolCrafts ecosystem.

**Naming note:** These are standalone developer-facing repositories (MolCrafts is not a monorepo). GitHub names use the `molcrafts-` prefix: `molcrafts-ci`, `molcrafts-bench`, `molcrafts-molrec` (`MolCrafts/molcrafts-ci`, etc.). Distribution/package names MAY match the repository names.

---

## 1. Motivation

MolCrafts contains multiple repositories such as `molpy`, `molrs`, `molvis`, and related developer tooling. These projects increasingly need to produce structured engineering results during CI, including benchmark measurements, format/schema validation, compatibility information, API surfaces, package metadata, numerical regression data, and capability information.

These concerns share the same infrastructure pattern:

```text
Producer
   │
   ▼
Snapshot
   │
   ├── Gate
   │
   └── Persist
          │
          ▼
        Index
          │
          ▼
       Publish
```

The actual domain semantics are different. A benchmark result is not an atomistic record schema, and neither should inherit from a universal scientific record abstraction.

The shared infrastructure therefore belongs in a separate repository:

```text
molcrafts-ci
```

Domain-specific logic remains in:

```text
molcrafts-bench
molcrafts-molrec
```

The objective is to reuse CI infrastructure without coupling unrelated domain models.

---

# 2. Repository responsibilities

## 2.1 `molcrafts-ci`

`molcrafts-ci` is the shared CI infrastructure repository for the MolCrafts organization (`MolCrafts/molcrafts-ci`).

It is responsible for:

* common CI contracts;
* snapshot metadata;
* source provenance;
* validation result representation;
* history tracking;
* index organization;
* artifact ingestion;
* GitHub authentication and cross-repository communication;
* static-site publication infrastructure;
* reusable GitHub Actions and workflows where justified.

It MUST NOT define:

* benchmark algorithms;
* benchmark statistical models;
* atomistic record semantics;
* MolRec schema;
* scientific data representations;
* domain-specific compatibility rules.

`molcrafts-ci` deals with engineering infrastructure, not scientific semantics.

---

## 2.2 `molcrafts-bench`

`molcrafts-bench` defines the benchmark domain (`MolCrafts/molcrafts-bench`).

It is responsible for:

```text
BenchmarkResult
BenchmarkMetric
BenchmarkEnvironment
BenchmarkPolicy
BenchmarkGate
BenchmarkAdapter
```

It does not implement a new benchmarking framework.

Existing frameworks remain responsible for measurement, for example:

```text
pytest-benchmark
Criterion / cargo-criterion
other language-specific benchmark frameworks
```

`molcrafts-bench` normalizes those outputs and integrates them with `molcrafts-ci`.

Conceptually:

```text
pytest-benchmark
       │
       ▼
BenchmarkAdapter
       │
       ▼
BenchmarkResult
       │
       ├── BenchmarkGate
       │
       └── Snapshot
                │
                ▼
         molcrafts-ci
```

---

## 2.3 `molcrafts-molrec`

The repository previously referred to as `molrec` SHALL be named:

```text
molcrafts-molrec
```

(`MolCrafts/molcrafts-molrec`). The name reflects that it is developer infrastructure belonging to the MolCrafts ecosystem rather than a standalone end-user application. MolCrafts is not a monorepo; the `molcrafts-` prefix on these developer-facing repositories makes organizational ownership explicit.

`molcrafts-molrec` is responsible for the atomistic record specification and its developer tooling.

Its responsibilities include concepts such as:

```text
schema
serialization
validation
conformance
compatibility
format adapters
reference examples
```

Its CI integration follows the same infrastructure pattern:

```text
Atomistic representation
        │
        ▼
MolRec Adapter
        │
        ▼
MolRec representation
        │
        ├── Validation
        ├── Compatibility Gate
        │
        └── Snapshot
                 │
                 ▼
          molcrafts-ci
```

`molcrafts-molrec` MUST NOT depend on GitHub infrastructure at runtime.

Using MolRec as a library must never implicitly introduce dependencies on:

```text
GitHub API
GitHub Actions
Cloudflare Pages
CI authentication
index storage
```

The two systems meet only during development, CI, validation, and publication.

---

# 3. Architecture boundary

The dependency structure SHALL be:

```text
                        MolCrafts/molcrafts-ci
                       /            \
                      /              \
                     /                \
           CI integration          CI integration
                  /                    \
                 ▼                      ▼
           MolCrafts/molcrafts-bench         MolCrafts/molcrafts-molrec
              ▲                       ▲
              │                       │
        benchmark users        MolRec consumers
              │                       │
         molpy / molrs       molpy / molvis / ...
```

The shared layer MUST NOT introduce a universal scientific base class such as:

```text
BaseRecord
DomainRecord
UniversalRecord
```

Instead, domains expose independent payloads wrapped by common CI metadata.

---

# 4. Core terminology

All shared names SHALL follow conventional software-engineering terminology.

| Name          | Meaning                                                                  |
| ------------- | ------------------------------------------------------------------------ |
| `Snapshot`    | Immutable representation of one CI-observed engineering state            |
| `Manifest`    | Metadata describing a snapshot                                           |
| `Payload`     | Domain-specific normalized content                                       |
| `Adapter`     | Converts external/provider output into a domain representation           |
| `Gate`        | Evaluates a snapshot or current state against a policy (not a GitHub Check Run) |
| `GateResult`  | Structured result produced by a gate                                     |
| `Policy`      | Configuration controlling a gate                                         |
| `Index`       | Persistent index of tracked snapshots (`SnapshotIndex` when disambiguating) |
| `Artifact`    | File produced by a CI run                                                |
| `Provider`    | External system that originally generates data                           |
| `Profile`     | Execution/environment identity relevant to comparability                 |
| `Publisher`   | Produces static web-facing data or site output                           |
| `Ingester`    | Receives and validates submitted snapshots                               |
| `Tracking`    | Controls whether snapshots become persistent project history             |
| `Generation`  | Compatibility boundary within tracked history                            |

Terms such as `Ledger`, `Frame`, `Bundle`, `Vault`, `Catalog` (for this subsystem), or similarly metaphorical / org-colliding names SHALL NOT be used for generic CI infrastructure unless they represent an existing domain concept outside this subsystem.

`Catalog` is reserved elsewhere in MolCrafts (e.g. molhub dataset catalog, harness catalog). This subsystem uses `Index`.

`Gate` is intentional: it avoids collision with the GitHub Checks API / check runs. A `Gate` may still *report into* a GitHub Check Run as a presentation channel.

Names should reveal engineering responsibility directly.

---

# 5. Snapshot model

`Snapshot` is the central infrastructure abstraction.

A snapshot represents:

> The normalized engineering state observed by CI at one specific source revision and execution context.

A snapshot consists conceptually of:

```text
Snapshot
│
├── Manifest
│   ├── schema version
│   ├── record
│   ├── source
│   ├── producer
│   ├── profile
│   ├── tracking generation
│   └── provenance
│
└── Payload
```

The infrastructure understands the `Manifest`.

The domain implementation understands the `Payload`.

For example:

```text
record = benchmark
Payload = BenchmarkResult
```

while:

```text
record = molrec
Payload = MolRec schema/conformance state
```

`molcrafts-ci` MUST NOT interpret domain payload fields.

---

# 6. Snapshot properties

Snapshots SHOULD be:

* immutable;
* deterministic where practical;
* machine-readable;
* human-inspectable;
* schema-versioned;
* provenance-aware;
* independent of frontend presentation.

A snapshot MUST identify its source sufficiently to trace it back to the CI execution that generated it.

Typical source metadata includes:

```text
repository
commit
ref
workflow run
run attempt
producer version
profile
timestamp
```

These fields belong to infrastructure metadata rather than the domain payload.

---

# 7. Tracking lifecycle

Not every project is stable enough to maintain compatibility history from the beginning.

The shared configuration therefore SHALL expose:

```text
tracking.enabled
```

with two states.

## 7.1 Tracking disabled

```text
tracking.enabled = false
```

means:

```text
Produce
   │
   ▼
Validate
   │
   ▼
Gate
   │
   ▼
CI result
```

The snapshot MAY exist temporarily as a workflow artifact for inspection or debugging, but it SHALL NOT become part of persistent MolCrafts history.

When tracking is disabled:

* no persistent history is created;
* no index entry is required;
* backward compatibility is not enforced;
* no historical baseline is implied;
* schema and representation may change freely;
* current-state validation may still run;
* current-state gates may still fail CI.

This is the default mode for an experimental developer interface.

GitHub workflow artifacts are appropriate for these transient outputs because GitHub supports configurable artifact retention rather than treating workflow artifacts as permanent storage.

---

## 7.2 Tracking enabled

```text
tracking.enabled = true
```

changes the lifecycle to:

```text
Produce
   │
   ▼
Validate
   │
   ▼
Gate
   │
   ▼
Persist Snapshot
   │
   ▼
Update Index
   │
   ▼
Publish
```

Enabling tracking establishes the first persistent compatibility history for that domain.

From this point forward, gates MAY use historical snapshots for:

```text
backward compatibility
benchmark baselines
API compatibility
schema compatibility
regression detection
trend analysis
```

Turning tracking on is therefore a deliberate project-lifecycle decision.

It SHALL NOT happen automatically merely because CI has run successfully.

---

# 8. Tracking generations

Persistent history occasionally needs an intentional compatibility reset.

For that purpose, the architecture defines:

```text
tracking.generation
```

For example:

```text
generation = 1
```

followed later by:

```text
generation = 2
```

A generation defines an independent compatibility domain.

Snapshots from different generations remain historically visible but SHALL NOT be considered backward-compatible by default.

Conceptually:

```text
Generation 1
A ─ B ─ C ─ D

Generation 2
            E ─ F ─ G
```

Frontend tools may compare `D` and `E`, but compatibility gates SHALL NOT interpret this comparison as a regression unless explicitly configured.

Initial implementations MAY omit generation-reset functionality while retaining the field in the data model.

---

# 9. Gates and persisted data

A strict distinction SHALL exist between:

```text
state
```

and:

```text
interpretation
```

Snapshots store state.

Gates evaluate state.

The index stores snapshots.

The frontend interprets relationships between snapshots.

Therefore `molcrafts-ci` MUST NOT persist derived pairwise diffs such as:

```text
A → B diff
A → C diff
B → C diff
```

This produces quadratic derived data and couples storage to a particular interpretation.

Instead:

```text
A
B
C
```

are persisted independently.

The frontend requests:

```text
A + B
```

and derives the desired comparison.

---

# 10. CI gates versus frontend diff

The frontend owns exploratory and presentation-oriented diffing.

Examples include:

```text
relative benchmark change
absolute benchmark change
schema field additions
API additions/removals
dependency changes
capability changes
```

A CI `Gate` MAY internally compare the current snapshot against a reference snapshot when required to evaluate a `Policy`.

For example:

```text
current benchmark
       +
baseline benchmark
       │
       ▼
BenchmarkGate
       │
       ▼
GateResult
```

However, that comparison is ephemeral.

The canonical stored objects remain:

```text
current Snapshot
reference Snapshot
GateResult
```

not a persistent diff object.

This preserves the principle:

> Store observations, not presentation-specific interpretations.

---

# 11. GateResult

All domains SHALL expose gates through a common infrastructure-level `GateResult`.

Conceptually:

```text
GateResult

status
gate
summary
details
references
```

Supported status semantics SHOULD remain minimal:

```text
pass
warning
fail
```

Examples:

Benchmark:

```text
performance-regression
fail
```

MolRec:

```text
schema-conformance
pass
```

or:

```text
backward-compatibility
fail
```

The common infrastructure only interprets the status.

Domain-specific reasoning remains inside `details`.

---

# 12. Policy ownership

Policies MUST remain domain-specific.

For example:

```text
BenchmarkPolicy
```

may define:

```text
acceptable regression
metric direction
baseline selection
environment matching
```

while:

```text
MolRecCompatibilityPolicy
```

may define:

```text
allowed additions
breaking field changes
serialization guarantees
schema version rules
```

There SHALL NOT be a generic policy language in the initial architecture.

Introducing a universal rule engine would increase complexity while providing little benefit at the current scale.

---

# 13. Git-friendly persistent storage

Persistent CI history SHALL prioritize:

```text
Git readability
deterministic serialization
frontend accessibility
simple static hosting
long-term inspectability
```

The canonical small-data format SHOULD therefore be JSON.

Configuration intended primarily for humans MAY use YAML or TOML.

Schemas SHOULD use JSON Schema where applicable.

---

# 14. Snapshot storage layout

A conceptual storage layout is:

```text
data/
├── snapshots/
│   ├── <project>/
│   │   ├── <record>/
│   │   │   ├── <generation>/
│   │   │   │   └── <snapshot>.json
│
├── index/
│   ├── <project>/
│   │   └── <record>.jsonl
│
└── schemas/
    └── ...
```

Individual snapshots SHALL be immutable files.

Index files SHOULD use append-friendly representations such as JSON Lines where appropriate.

JSON serialization SHOULD be deterministic:

```text
UTF-8
stable property ordering
stable numeric representation
consistent indentation
no presentation-only values
```

This keeps repository-level Git diffs understandable even without the MolCrafts frontend.

---

# 15. Large artifacts

Git SHALL NOT be used as arbitrary binary artifact storage.

Large outputs such as:

```text
raw benchmark samples
large trajectories
binary molecular data
debug archives
compiled packages
visual regression images
```

SHOULD remain GitHub workflow artifacts or another appropriate artifact store.

The persistent Snapshot stores only:

```text
normalized state
metadata
summary
digest
artifact reference
```

where required.

GitHub Actions artifacts expose a SHA-256 digest when uploaded and validate that digest on download, making them appropriate for referenced CI outputs.

This separation gives:

```text
Git
  = durable, readable engineering state

Artifacts
  = potentially large raw CI output
```

---

# 16. Index

`Index` (full name `SnapshotIndex` when disambiguating) is the persistent index over tracked snapshots.

It answers questions such as:

```text
Which snapshots exist?

Which snapshot corresponds to a commit?

Which profile produced it?

Which generation does it belong to?

Which snapshot is associated with the default branch?

Which snapshots are eligible as references?
```

The Index SHALL NOT contain frontend-generated diff results.

The Index SHALL NOT contain domain-specific decision logic.

---

# 17. Frontend architecture

The website is a consumer of published indexes and snapshots.

The product shell lives under `site/` and is built with the **molcrafts-ui**
shadcn registry (components are copied into the product; there is no shared
runtime `@molcrafts/ui` dependency).

Layout:

```text
┌─────────────┬──────────────────────────────┐
│  Projects   │  Plugin tabs                 │
│  (index)    │  tests | coverage | benchmark│
│             │  | regression | molrec | …   │
└─────────────┴──────────────────────────────┘
```

Each right-hand tab is a **RecordTabPlugin**:

```text
id, label, order, available(project) → bool, Component
```

Builtin plugins register at load time. Additional domains register by importing
a module that calls `registerPlugin` — the shell does not hard-code tab lists.

A tab is shown only when `available(project)` is true for the selected project
(typically when the project's index lists a matching snapshot `record`).

Conceptual data flow:

```text
Index
   │
   ▼
Project list ──► available plugins ──► active tab Component
                      │
                      ▼
                 Snapshot entries / Domain Diff
```

Each domain owns its frontend comparison semantics inside its plugin.

For example:

```text
BenchmarkDiff
MolRecDiff
ApiDiff
CliDiff
```

There SHALL NOT initially be a universal `Diff` schema.

Shared frontend infrastructure may provide:

```text
navigation
project selection
tab chrome
commit links
profile selection
layout
loading
error handling
```

but not domain semantics.

---

# 18. Site publication

The published site SHOULD be a static application.

This avoids introducing:

```text
database servers
long-running backend services
API deployment infrastructure
server authentication
runtime operational maintenance
```

Cloudflare Pages is connected to the repository and builds it: root directory `site`, `npm run build`, output `dist`. No deploy workflow and no API token live here. `sync-ui` finds no sibling molcrafts-ui checkout on the builder and falls back to the vendored sources under `site/src`, which is why they are committed.

The index is **not** bundled into that build. It lives on the `data` branch, as the diagram below has always said, and the browser reads it at runtime from `raw.githubusercontent.com`, which serves it with `Access-Control-Allow-Origin: *` and a five-minute cache. Two properties follow, and both were faults before:

* a snapshot published between deploys appears without a rebuild — bundling meant the dashboard showed whatever was true at the last commit to `master`;
* the deployment stops growing with history — bundling carried every snapshot ever published into every deploy.

Keeping the data off `master` is also what keeps ingest commits out of the code history. `molci ingest` maintains `index-listing.json` at the data root, because HTTP offers nothing to enumerate and a reader has to be told which index files exist.

The intended architecture is therefore:

```text
data branch / index
       │
       ▼
site build
       │
       ▼
static assets
       │
       ▼
Cloudflare Pages
```

The frontend performs snapshot comparison client-side.

---

# 19. GitHub Actions strategy

GitHub Actions SHALL be introduced only where they establish a reusable CI boundary or encapsulate GitHub-specific behavior.

Actions MUST NOT become the architecture itself.

Core libraries and domain logic must remain executable outside GitHub Actions.

The intended layering is:

```text
Domain library
      │
      ▼
CLI / stable interface
      │
      ▼
optional GitHub Action
      │
      ▼
GitHub workflow
```

This ensures local reproducibility and avoids locking business logic inside workflow YAML.

---

# 20. Composite Actions versus reusable workflows

Two GitHub reuse mechanisms have different responsibilities.

A **composite Action** SHOULD be used when a repeated operation belongs inside an existing job.

Examples:

```text
normalize snapshot
submit snapshot
publish gate summary
initialize CI metadata
```

A **reusable workflow** SHOULD be used when the reusable unit requires one or more complete jobs.

Examples:

```text
central ingestion
scheduled reconciliation
site build and deployment
organization-wide validation workflow
```

GitHub itself distinguishes composite Actions as reusable step groups and reusable workflows as reusable job/workflow structures.

---

# 21. Initial GitHub Actions

The project SHALL NOT create an Action for every conceptual component.

Actions are introduced only when at least one of the following applies:

1. several MolCrafts repositories repeat the same GitHub-specific integration;
2. authentication or artifact handling should be centralized;
3. a stable CI interface is desirable independently of implementation details.

The initial architecture MAY therefore expose only a very small set.

### `MolCrafts/molcrafts-ci/submit`

Purpose:

```text
validate Manifest
package Snapshot
upload CI artifact
ingest into the index and push, when tracking is enabled
```

This is the strongest candidate for a shared infrastructure Action, and it is
the only one a producer has to call: one step carries a snapshot from the run
that measured it to the published site.

The Action runs the ingest **inside the producer's own workflow run**, against a
shallow clone of the index repository. A rejected push means another producer
committed first, so the Action re-runs the ingest on the branch as it now stands
and pushes again. The ingest is idempotent — a snapshot id is derived from its
source, the stored file is immutable, and an index entry is appended only when
that id is absent — so a retry, a re-run and a lost race all converge instead of
duplicating or clobbering history.

`molcrafts-ci` SHALL be its own first producer. Its CI publishes its own `tests`
and `coverage` records through this Action, so the publish path is exercised on
every push to the default branch rather than only when a domain repository
adopts it. The self-hosted case is the one where `GITHUB_TOKEN` suffices (§23),
because the write is to the repository the workflow already runs in; it is also
loop-free, because GitHub does not start a workflow from a `GITHUB_TOKEN` push,
while the Cloudflare Pages webhook is not subject to that rule and still
redeploys.

### Domain-specific gate Actions

If repeated integration warrants them:

```text
MolCrafts/molcrafts-bench/gate
MolCrafts/molcrafts-molrec/gate
```

These actions remain owned by their corresponding domain repositories.

They invoke domain libraries and emit `GateResult`.

They MAY call the shared `MolCrafts/molcrafts-ci/submit` integration afterward.

No other Action should be created until repeated usage demonstrates a need.

---

# 22. Reusable workflows

`molcrafts-ci` MAY provide reusable workflows for infrastructure-owned multi-job processes.

None are currently justified.

### Ingest

Ingestion is **not** a reusable workflow and not a workflow in the index
repository at all. It is a step of the `submit` Action, so it runs in the
producer's own workflow run.

A reusable workflow was tried and removed. It failed in two ways that are worth
recording, because both are invisible until a real producer calls it:

* a called workflow runs with the **caller's** `GITHUB_TOKEN`, which cannot push
  to the index repository (§23), so the credential problem is not solved by
  moving the job;
* a workflow in the index repository cannot read an artifact belonging to a run
  in another repository without that same cross-repository credential, so the
  artifact hand-off buys nothing over ingesting the file that is already on disk
  in the producer's workspace.

Running the ingest in the producer's run also puts the failure where the
engineer who caused it is already looking: the run that measured the data turns
red, rather than a separate run in a repository they may not watch.

The component that performs this work is the `Ingester`.

### Reconcile

A periodic sweep that verifies tracked artifacts have index entries.

This was specified to recover from a failed notification. With ingestion inside
the producer's run there is no notification to lose: the ingest either succeeds
before the producer's job goes green, or the job fails and the operator re-runs
it. Re-running is safe because the ingest is idempotent.

Reconcile therefore remains unimplemented, and SHOULD stay that way unless an
asynchronous transport is reintroduced.

### Publish

Cloudflare Pages builds and deploys from its own Git integration (§18), so no
publish workflow exists here. The ingest push **is** the deploy trigger.

---

# 23. Cross-repository communication

Normal repository CI SHOULD use the built-in `GITHUB_TOKEN` whenever possible.

Cross-repository operations SHOULD use a MolCrafts GitHub App rather than a long-lived personal access token.

GitHub documents that the workflow `GITHUB_TOKEN` is scoped to the repository containing the workflow, while GitHub App installation tokens can be used when access to other repositories or organization resources is required.

Therefore the intended authentication hierarchy is:

```text
same repository
    ↓
GITHUB_TOKEN

cross repository
    ↓
MolCrafts GitHub App
```

The GitHub App SHALL receive only the minimum required repository permissions.

---

# 24. Event transport

Cross-repository notification SHOULD transport metadata, not large payloads.

For example:

```text
repository
workflow run
artifact
snapshot record
profile
commit
```

The actual snapshot should be retrieved from the workflow artifact.

GitHub's `repository_dispatch` mechanism MAY be used for such custom repository-level events.

The event is a notification:

```text
"new artifact is available"
```

not the artifact itself.

This transport is **not** currently used. `repository_dispatch` needs the same
cross-repository credential as a direct push (§23), and it is fire-and-forget:
the producer's job goes green whether or not the ingest that follows succeeds,
which is the failure mode `reconcile` existed to repair. Ingesting synchronously
in the producer's run removes the event, the transport and the repair job at
once. This section stands as the design to return to if ingestion ever has to
become asynchronous — a rate limit on the index repository would be the reason.

---

# 25. Raw artifact lifecycle

Workflow artifacts serve as transient or source artifacts.

Persistent snapshots serve as long-term engineering history.

Therefore:

```text
workflow artifact
      │
      ├── debugging
      ├── raw provider output
      └── ingestion source

persistent snapshot
      │
      ├── normalized
      ├── Git-friendly
      ├── tracked
      └── frontend source
```

Artifact retention SHOULD be independent from persistent snapshot retention.

---

# 26. `molcrafts-bench` integration

A typical benchmark lifecycle becomes:

```text
Benchmark Provider
       │
       ▼
Benchmark Adapter
       │
       ▼
BenchmarkResult
       │
       ├───────────────┐
       ▼               ▼
BenchmarkGate       Snapshot
       │               │
       ▼               │
 GateResult            │
       │                │
       └──────┬─────────┘
              ▼
       molcrafts-ci
```

If tracking is disabled:

```text
GateResult → CI
```

and the result is not added to persistent benchmark history.

If tracking is enabled:

```text
BenchmarkResult
     ↓
Snapshot
     ↓
Index
     ↓
Frontend
```

The frontend calculates historical benchmark differences and trends.

---

# 27. `molcrafts-molrec` integration

A typical MolRec development lifecycle becomes:

```text
Schema / Adapter / Example
          │
          ▼
    MolRec Validation
          │
          ├───────────────┐
          ▼               ▼
  Compatibility Gate    Snapshot
          │               │
          ▼               │
      GateResult           │
          │                │
          └──────┬─────────┘
                 ▼
          molcrafts-ci
```

During early development:

```text
tracking.enabled = false
```

so developers may freely restructure the specification.

Once the project intentionally establishes compatibility guarantees:

```text
tracking.enabled = true
tracking.generation = 1
```

from which point persistent compatibility history begins.

---

# 28. Extensible snapshot records

The architecture SHOULD support future engineering domains without changing the infrastructure contract.

Potential records include:

```text
benchmark
molrec
api
cli
capability
dependency
package
numerical
```

These correspond to possible future features such as:

### API surface tracking

Store the normalized public API surface.

Frontend can derive:

```text
added symbols
removed symbols
signature changes
deprecations
```

### CLI contract tracking

Store:

```text
commands
subcommands
arguments
options
defaults
```

Frontend can derive command-line compatibility changes.

### Capability tracking

Store supported:

```text
formats
platforms
backends
features
optional integrations
```

The frontend can generate ecosystem compatibility matrices.

### Dependency tracking

Store normalized direct dependency information.

Frontend can show dependency changes between revisions.

### Package metadata

Track engineering metrics such as:

```text
wheel size
binary size
bundle size
WASM size
```

### Numerical regression

Track normalized scientific reference outputs such as:

```text
energy
forces
stress
numerical error summaries
```

This allows inspection of numerical drift rather than only binary pass/fail testing.

These capabilities SHALL be added as independent domains or snapshot records, not as fields in an ever-growing universal snapshot payload.

---

# 29. Project structure

A conceptual `molcrafts-ci` repository organization is:

```text
molcrafts-ci/
│
├── schemas/
│   ├── manifest/
│   ├── snapshot/
│   └── gate-result/
│
├── actions/
│   └── submit/
│
├── workflows/
│   ├── ingest
│   ├── reconcile
│   └── publish
│
├── data/
│   ├── snapshots/
│   └── index/
│
├── site/
│   ├── shell
│   ├── routing
│   └── shared-ui
│
└── docs/
    └── specification
```

The exact source-language package layout is intentionally outside this specification.

---

# 30. Naming conventions

These repositories are **developer-facing** and **standalone** (MolCrafts is not a monorepo). They SHALL use the `molcrafts-` prefix so ownership is visible outside any monorepo context.

Repository names:

```text
molcrafts-ci
molcrafts-bench
molcrafts-molrec
```

Distribution / package names SHOULD match the repository names when published:

```text
molcrafts-ci
molcrafts-bench
molcrafts-molrec
```

Action references:

```text
MolCrafts/molcrafts-ci/submit
MolCrafts/molcrafts-bench/gate
MolCrafts/molcrafts-molrec/gate
```

Infrastructure types:

```text
Snapshot
Manifest
Payload
Gate
GateResult
Policy
Index
Adapter
Provider
Profile
Ingester
Publisher
Artifact
```

Lifecycle configuration:

```text
tracking.enabled
tracking.generation
```

Domain-specific types SHOULD use explicit prefixes where ambiguity exists:

```text
BenchmarkResult
BenchmarkPolicy
BenchmarkGate

MolRecSchema
MolRecGate
MolRecCompatibilityPolicy
```

Generic names SHOULD only be used for genuinely generic concepts.

Snapshot `record` values remain short discriminators (`benchmark`, `molrec`, …) and are not repository names.


---

# 31. Design principles

The architecture SHALL follow these principles:

1. **Domain separation**
   Shared infrastructure must not imply shared scientific semantics.

2. **Immutable observations**
   Persistent snapshots represent observed states and are not modified after publication.

3. **Diff at presentation time**
   Persistent storage contains snapshots rather than pairwise diffs.

4. **Explicit stability**
   Historical compatibility begins only when `tracking.enabled` is intentionally enabled.

5. **Git-friendly state**
   Small canonical states are stored as deterministic plaintext formats.

6. **Artifacts for large data**
   Git is not a replacement for binary artifact storage.

7. **GitHub-native but GitHub-independent core**
   GitHub integrates the system but does not contain its domain logic.

8. **Actions only when justified**
   Reusable Actions are integration boundaries, not arbitrary wrappers around every command.

9. **Static publication by default**
   The web layer should remain build-time/static unless a server becomes demonstrably necessary.

10. **No premature universal abstractions**
    Different domain payloads and policies remain separate until repeated implementations establish a genuine common interface.

---

# 32. Initial implementation scope

The first implementation SHOULD remain deliberately small.

### `molcrafts-ci`

Implement:

```text
Manifest
Snapshot envelope
GateResult
tracking.enabled
tracking.generation
Index
Git-friendly persistence
submit integration
ingest workflow
publish workflow
minimal static site shell
```

### `molcrafts-bench`

Implement:

```text
pytest-benchmark adapter
Criterion adapter
BenchmarkResult
BenchmarkGate
BenchmarkPolicy
benchmark snapshot frontend
```

### `molcrafts-molrec`

Implement:

```text
MolRec schema snapshot
schema validation
tracking-disabled development mode
compatibility gate after tracking is enabled
MolRec snapshot frontend
```

The following SHOULD NOT be part of the first milestone:

```text
database service
custom benchmark runner
general rules engine
universal diff schema
universal domain model
dynamic backend API
distributed scheduler
custom artifact storage
organization-wide developer portal
```

---

# 33. Target architecture

The resulting system should converge on:

```text
                        GitHub repositories
                 molpy / molrs / molvis / ...
                            │
                         Produce
                            │
                            ▼
                     Domain Adapter
                            │
                            ▼
                         Snapshot
                            │
                   ┌────────┴────────┐
                   │                 │
                   ▼                 ▼
                 Gate         tracking.enabled?
                   │                 │
                   ▼                yes
             GateResult              │
                   │                 ▼
                   │              Submit
                   │                 │
                   ▼                 ▼
                  CI             Ingester
                                     │
                                     ▼
                                   Index
                                     │
                                     ▼
                                  Publish
                                     │
                                     ▼
                               Static Website
                                     │
                         ┌───────────┴───────────┐
                         ▼                       ▼
                    Snapshot A              Snapshot B
                         └───────────┬───────────┘
                                     ▼
                               Frontend Diff
```

The essential contract is therefore:

> **Domains produce immutable snapshots. Gates determine whether the current state is acceptable. Tracking determines whether that state becomes history. The index indexes persistent snapshots. The frontend compares and interprets snapshots. GitHub Actions provide integration only where platform-specific automation is required.**

This contract should remain stable even if the underlying website, storage mechanism, benchmark framework, or individual MolCrafts projects change in the future.
