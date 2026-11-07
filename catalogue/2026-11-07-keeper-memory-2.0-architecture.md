# Keeper Memory 2.0 — the Infinite Memory DTD Family (TODO-70)

Masterpiece architecture, 2026-11-07. Built from the verbatim study of:
- DocBook Definitive Guide (defguide): driver/module pattern, parameter-entity
  flavors, customization layers, architectural forms (arch-letter/arch-payroll)
- JATS DTD Suite (DTD_FAMILY): suite + application customization layer, class
  pools, common-attribute modules, module declaration files
- DAISY: empty extension hooks (externalblock/externalinline/externalFlow)
- MathML: entity-set modules + module switches
- Standalone DTDs (gdb-syscalls, krita): root-element + EMPTY leaf + ATTLIST

## 1. What the canonical families teach (the grammar)

Every serious DTD family is built from the same grammar:

| Pattern | Source | Meaning |
|---|---|---|
| Driver file | docbookx.dtd, JATS-*.dtd | Declares `*.module` PEs, wraps each module in `<![%m.module;[ ... ]]>`, includes module files by PUBLIC+SYSTEM |
| Module files | dbpoolx.mod, JATS-common1.ent | Contain the actual declarations |
| Customization layer | ch05, JATS-journalpubcustom-*.ent | Declares new PE values BEFORE including the base driver |
| Class pools | `*.class`, `*.mix` | Element vocabulary grouped by role |
| Single-element switches | `*.element`, `*.attlist` | Per-element/per-attlist on/off |
| Inclusion/exclusion | `*.inclusion`, `*.exclusion` | Content-model extension |
| Extension hooks | `local.*` (DocBook), `externalblock` (DAISY) | Empty PEs a layer fills |
| Entity sets | `*ent` modules (MathML, DocBook) | Reusable character/notation pools |
| Architectural forms | `ADDRESS` #FIXED attr (arch-letter) | Every element carries a fixed role attribute |

## 2. The Keeper Memory 2.0 family: `rtrre-memory`

The keeper memory becomes its own DTD family — one driver, modules for each
memory kind, architectural attributes on every span. The family is a real
DTD corpus: the engine indexes it with the inventory header, lineage, and
module switches, so memory is searched structurally, not just textually.

### 2.1 The driver — `rtrre-memory.dtd`

```dtd
<!-- RTR-RE:Symbiose keeper memory family — driver v2 -->
<!ENTITY % rtrre.span.module "INCLUDE">
<![%rtrre.span.module;[
<!ENTITY % rtrre.span PUBLIC
"-//RTR-RE//ELEMENTS Keeper Memory Span V2//EN"
"rtrre-span.mod">
%rtrre.span;
]]>

<!ENTITY % rtrre.glossary.module "INCLUDE">
<![%rtrre.glossary.module;[
<!ENTITY % rtrre.glossary PUBLIC
"-//RTR-RE//ELEMENTS Keeper Glossary V2//EN"
"rtrre-glossary.mod">
%rtrre.glossary;
]]>

<!ENTITY % rtrre.summary.module "INCLUDE">
<![%rtrre.summary.module;[
<!ENTITY % rtrre.summary PUBLIC
"-//RTR-RE//ELEMENTS Keeper Paraphrase V2//EN"
"rtrre-summary.mod">
%rtrre.summary;
]]>
```

### 2.2 The span module — `rtrre-span.mod`

Architectural form (arch-letter pattern): every span carries fixed role
attributes; the DTD scanner's inventory header carries them, so structural
queries ("assistant write spans about X") work.

```dtd
<!-- Keeper span: one record per evicted message -->
<!ELEMENT span EMPTY>
<!ATTLIST span
    id ID #REQUIRED
    role (user|assistant|tool) #REQUIRED
    lane (read|write|think|plan|unknown) #IMPLIED
    dtype (CDATA|NDATA) #IMPLIED
    ts CDATA #IMPLIED
    source CDATA #IMPLIED
    session CDATA #IMPLIED>
```

The verbatim content follows the declaration block in the span file (the DTD
chunker keeps raw content after the inventory header). Nothing is lost.

### 2.3 The glossary module — `rtrre-glossary.mod` (operator vision)

The lexikon becomes a DTD corpus member: glossary terms are declarations with
architectural attributes, so terms are retrievable structure-first and the
glossary syncs with the lexikon lane.

```dtd
<!ELEMENT glossaryentry EMPTY>
<!ATTLIST glossaryentry
    term CDATA #REQUIRED
    alias CDATA #IMPLIED
    definition CDATA #IMPLIED
    source CDATA #IMPLIED
    ts CDATA #IMPLIED>
```

### 2.4 The paraphrase module — `rtrre-summary.mod` (operator vision)

When context is bounded, a one-line paraphrase stays in the live window while
the verbatim span goes to memory. The paraphrase is itself a DTD record linked
to the span by id — the visible anchor, the eternal record.

```dtd
<!ELEMENT paraphrase EMPTY>
<!ATTLIST paraphrase
    spanref IDREF #REQUIRED
    text CDATA #REQUIRED
    ts CDATA #IMPLIED>
```

### 2.5 The infinity loop (all pieces proven, now unified)

1. Bounded live window (trigger/target) → evicted spans → memory root as DTD
   records (`<project>/.opencode/memory/`, gitignored).
2. Engine indexes the root (first-class DTD corpus, inventory header).
3. `memory_search` retrieves any span ever evicted (measured 0.9496).
4. Lexikon seeds from evicted vocabulary (proven) → glossary module syncs.
5. Cumulative counter drives recency-aware protection (proven).
6. Paraphrase common line anchors the live window (summary module).
7. Real-time ONNX retrieval on the plugin-side Optimizer: the no-MCP center
   queries memory via the framework for erased pieces — uniform query target.

## 3. Implementation order

1. Sink: write DTD-shaped span files to `<project>/.opencode/memory/`
   (backward compatible: still read .md spans).
2. Discovery: memory root is a first-class root.
3. Engine: inventory header already handles the ATTLIST shape — verify.
4. Glossary + paraphrase modules (operator visions) after the span core.
5. Tests + Engine Beneath sink-case updates.
6. Measure retrieval parity/improvement vs .md spans (expect structural queries
   to win).
7. Document the infinite-memory proof (a span evicted weeks ago retrieves at
   high score).
