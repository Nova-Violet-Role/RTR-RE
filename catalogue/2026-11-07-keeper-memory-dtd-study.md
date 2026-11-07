# Keeper Memory 2.0 — DTD Architecture Study (TODO-70)

Read verbatim, 2026-11-07. Sources:
- DocBook Definitive Guide (defguide), ch05 "Customizing DocBook" + schema/ modules
  (docbookx.dtd V4.5 driver, dbpoolx.mod, dbhierx.mod, dbnotnx.mod, dbcentx.mod,
  dbgenent.mod) + examples (arch-letter.dtd, arch-payroll.dtd, remv.sect4.dtd,
  add.sect6.dtd)
- C:\DTD_FAMILY (massive family source: JATS module set, DocBook 4.2-5.1,
  DAISY, MathML, OOXML/docx, dtds collection)

## Canonical DTD family architecture (what the keeper span format must follow)

### 1. Driver / module split
The driver file (docbookx.dtd) declares one `*.module` parameter entity per module,
defaulting to `INCLUDE`, wraps each module in a marked section, and includes the
module file via PUBLIC identifier + SYSTEM path:

```dtd
<!ENTITY % dbpool.module "INCLUDE">
<![ %dbpool.module; [
<!ENTITY % dbpool PUBLIC
"-//OASIS//ELEMENTS DocBook Information Pool V4.5//EN"
"dbpoolx.mod">
%dbpool;
]]>
```

A customization layer declares new PE values BEFORE including the base driver, then
includes the whole DTD by parameter entity reference (ch05 "General Structure").

### 2. Parameter-entity flavors (the vocabulary of extensibility)
- `*.class` — element class pools (e.g. `para.class`, `admon.class`)
- `*.mix` — mixture pools
- `*.module` — module switches (IGNORE/INCLUDE)
- `*.element` — single-element switches
- `*.attlist` — attribute-list switches
- `*.inclusion` / `*.exclusion` — content-model inclusion/exclusion
- `local.*` — per-class extension hooks, empty by default, redefined by layers:
  `<!ENTITY % local.para.class "">` then `<!ENTITY % para.class "... %local.para.class;">`

### 3. Architectural forms (the tagging pattern for spans)
The arch-letter/arch-payroll examples tag every element with a `#FIXED` attribute
carrying its semantic role:

```dtd
<!ELEMENT address (name, company? street*, city, state, zip)>
<!ATTLIST address ADDRESS CDATA #FIXED "START">
<!ELEMENT name (#PCDATA)*>
<!ATTLIST name ADDRESS CDATA #FIXED "NAME">
```

This is exactly the structural metadata the keeper spans need: a fixed set of
architectural attributes (role/lane/dtype/ts/source) on the span element, so the
DTD scanner's inventory header carries them and dense retrieval can match
structure, not just text.

### 4. The DTD_FAMILY scale confirms the pattern generalizes
JATS ships the same driver/module shape as `.ent` files (classes/mixes/models/
modules), DocBook versions 4.2-5.1 all follow the driver pattern, DAISY/MathML/
OOXML use the same marked-section + PE conventions.

## Keeper Memory 2.0 span format (design)

One file per session batch in `<project>/.opencode/memory/` (gitignored via
.opencode/). The file is a DTD-shaped structural record:

```dtd
<!-- RTR-RE:Symbiose keeper memory span — v2 (DTD-shaped) -->
<!ENTITY % rtrre.span.module "INCLUDE">
<![%rtrre.span.module;[
<!ELEMENT span EMPTY>
<!ATTLIST span
    id ID #REQUIRED
    role (user|assistant|tool) #REQUIRED
    lane (read|write|think|plan|unknown) #IMPLIED
    dtype (CDATA|NDATA) #IMPLIED
    ts CDATA #IMPLIED
    source CDATA #IMPLIED>
]]>
<!-- verbatim span content follows -->
```

- The DTD scanner builds the inventory header from the ATTLIST → every span is
  searchable by structure (role/lane/dtype/source), not just text.
- The verbatim content follows the declarations → nothing is lost (the infinity
  loop).
- The architectural-form attributes mirror the arch-letter pattern exactly.
- The `*.module` switch mirrors the driver pattern; a future "keeper memory
  family" could expose per-span-type switches.

## The infinity loop (all pieces proven, now unified)
1. Bounded live window (trigger/target) → evicted spans → memory root as DTD
   records.
2. Engine indexes the root (first-class DTD corpus, inventory header).
3. `memory_search` retrieves any span ever evicted (measured 0.9496).
4. Lexikon seeds from evicted vocabulary (proven) → memory makes retrieval
   smarter over time.
5. Cumulative counter drives recency-aware protection (proven).
6. Glossary sync in DTD (operator vision): the lexikon itself becomes a DTD
   corpus member, so glossary terms are retrievable structure-first.
7. Paraphrase common line (operator vision): when context is bounded, a
   one-line paraphrase stays in the live window while the verbatim span goes to
   memory — the compressor's payload already carries summaries; the "common
   line" is the visible anchor, the DTD span the eternal record.
8. Real-time ONNX retrieval on the plugin-side Optimizer (operator vision): the
   no-MCP center queries memory via the framework for erased pieces — the
   framework's search bridge already exists; the memory root makes the query
   target uniform.

## Implementation order
1. Sink: write DTD-shaped spans to `<project>/.opencode/memory/` (backward
   compatible: still read .md spans).
2. Discovery: the memory root is a first-class root (extra-root semantics).
3. Engine: inventory header already handles the ATTLIST shape — verify.
4. Tests + Engine Beneath sink-case updates.
5. Measure retrieval parity/improvement vs .md spans (expect structural queries
   to win).
6. Document the infinite-memory proof.
