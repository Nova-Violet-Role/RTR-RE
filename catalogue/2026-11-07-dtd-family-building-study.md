# DTD family-building study — 2026-11-07 (assimilation source)

Study of the two DTD family-building sources for assimilation into RTR-RE's
DTD extractor and taxonomy (T7–T10). Every pattern below is read from the
cited file, not from memory.

Sources:

- **DocBook Definitive Guide** (defguide), `C:\Microsoft Skill OPT and Skill
  LENS install via UV\dtd\defguide\en` — the canonical teaching source for
  building DTD families from zero. 12 top-level dirs; the book itself under
  `defguide/` (34 files: ch00–ch05, appa–appi, schema, examples, refpages).
- **DTD_FAMILY examples**, `C:\DTD_FAMILY\.dtd-file-examples` — 27 entries:
  JATS, DocBook (4.2–5.1), DITA v1.2/v1.3 (+xdita), TEI, MathML, SVG,
  XHTML (xhtml/xhtml11), Office, daisy, plus standalone DTDs (XMLSchema,
  datatypes, edoc, krita, language, gdb-syscalls, WMSDKNS, ModularMonet).

---

## 1. The family-creation patterns (measured from the sources)

### 1.1 Driver/module split (DocBook 4.5, `docbook/4.5/dtd/`)

A family is a **driver** plus **modules**:

- Driver: `docbookx.dtd` (the root/entry file).
- Modules: `dbpoolx.mod` (element pool), `dbhierx.mod` (hierarchy),
  `dbcentx.mod` (character entities), `dbnotnx.mod` (notations),
  `dbgenent.mod` (general entities), `calstblx.dtd`, `htmltblx.mod`,
  `soextblx.dtd` (table modules).
- Catalogs: `catalog.xml`, `docbook.cat` (entity resolution maps).

The driver includes modules via parameter-entity references; the `.mod` files
carry the actual declarations. This is the "family from modules" architecture
the defguide teaches.

### 1.2 Customization via module switches (defguide `examples/remv.sect4.dtd`)

The canonical customization recipe:

```dtd
<!ENTITY % sect3.module "IGNORE">
<!ENTITY % sect4.module "IGNORE">
<!ENTITY % sect5.module "IGNORE">
<!ENTITY % DocBookDTD PUBLIC "-//OASIS//DTD DocBook V3.1//EN">
%DocBookDTD;
<!ENTITY % local.sect3.attrib "">
<!ENTITY % sect3.role.attrib "%role.attrib;">
<!ELEMENT Sect3 - O (...)>
<!ATTLIST Sect3 ... %local.sect3.attrib; ...>
```

Patterns:

- **Module switches**: `%xxx.module "IGNORE"` / `"INCLUDE"` parameter entities
  toggle whole modules on/off before inclusion. This is the family's
  off-switch — the same idea as RTR-RE's band/domain switches.
- **Lineage**: `<!ENTITY % DocBookDTD PUBLIC "-//OASIS//DTD DocBook V3.1//EN">`
  — the PUBLIC identifier carries the owner, family, and version. This is a
  strong, explicit family signature.
- **Extension hooks**: `%local.sect3.attrib` empty pools that a customizer
  fills — the family's declared extension points.
- **Redeclaration**: after inclusion, elements are redeclared to override the
  base definition (the customization layer).

### 1.3 Minimal family from scratch (defguide `examples/arch-letter.dtd`)

A standalone minimal DTD: `<!ELEMENT address (name, company? street*, city,
state, zip)>` with per-element `#FIXED` attribute constants
(`ADDRESS CDATA #FIXED "START"` — the SGML architectural-forms pattern).
This is the "family from zero" shape: a root element with a content model and
a per-element attribute convention. The defguide's `arch-payroll.dtd` is the
same pattern for a second domain.

### 1.4 Element addition (defguide `examples/add.sect6.dtd`)

Adding a new element to a family = redeclaring a parent content model to
include the new child plus declaring the new element — the additive
customization layer.

---

## 2. What the RTR-RE extractor currently sees vs. what these patterns add

Current extractor (`eval/dtd_extractor.py` + `_scan_dtd_declarations`):
element/attribute/entity/notation counts, content-model fragments, attribute
owners. It does **not** currently capture:

1. **External-entity lineage** — PUBLIC/SYSTEM references (`%DocBookDTD;`
   style). These are the strongest family discriminator: two families with
   identical element names can be separated by their PUBLIC owner/version.
2. **Driver vs. module role** — which file is the entry driver vs. a module
   (.mod/.ent). The driver carries the customization switches; the modules
   carry the vocabulary.
3. **Customization-layer switches** — `%xxx.module "IGNORE"` parameter
   entities. A family with switches is a customized family; the switch set is
   a signature of the customization.
4. **Extension hooks** — `%local.*.attrib` pools; the family's declared
   extension surface.

## 3. Assimilation proposals (concrete engine additions)

- **A. Lineage extraction**: extend the scanner to capture external parameter-
  entity references with PUBLIC/SYSTEM identifiers. Yield `(kind, owner,
  family, version)` tuples (e.g., `PUBLIC OASIS DocBook V3.1`). Store them in
  the DTD profile as `lineage`.
- **B. Driver/module role detection**: classify each DTD-like file as driver
  (declares module switches or includes external DTDs) vs. module (pure
  declaration pool). Add `role` to the profile.
- **C. Customization-layer detection**: count `%xxx.module` switch entities
  with IGNORE/INCLUDE values; record the switch set as `module_switches`.
- **D. Family signature enrichment**: feed `lineage` + `role` +
  `module_switches` into the inventory header (the DTD chunk header built by
  `chunk_dtd_whole`) so dense retrieval can separate families that share
  element vocabulary — directly targeting the T10 cross-family taxon, which
  currently collapses on shared vocabulary (measured: DITA vs DocBook
  `appendix` collapse).
- **E. Taxonomy extension**: add T11 (lineage discrimination) and T12
  (customization-layer recognition) to the DTD taxon set, with queries derived
  from the defguide's own examples (e.g., "DocBook V3.1 customization removing
  Sect4").

## 4. Verification hooks

- The defguide examples are small and self-contained: `arch-letter.dtd`,
  `arch-payroll.dtd`, `add.sect6.dtd`, `remv.sect4.dtd` are ready-made
  fixtures for extractor tests (lineage, switches, role).
- DocBook 4.5's `docbookx.dtd` driver + modules are the reference modular
  family for driver/module role tests.
- The DTD_FAMILY families (JATS/DITA/TEI/MathML/SVG/XHTML/Office) provide the
  cross-family corpus for T11/T12 measurement.

Encoding: UTF-8, LF, no BOM, no CR.
