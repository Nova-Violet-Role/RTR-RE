<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose graded-relevance protocol v1

Full product name: Role-Type-Retrieval-RE:Symbiotized. This protocol is
the supervision contract for the official graded versus. It freezes how
judgments are made before comparative graded scores are computed.

## Why this exists

The precedent versus derives one expected file per query from that same
file's title, rare term, keyword pair, stem or identifier. That is a sound
binary regression bench, but it is not graded relevance: every other file
is implicitly zero even when it partially answers the intent, and only the
top three returned names are stored. This protocol replaces one-hot source
identity with inspectable graded judgments over the same real corpora.

## Corpora and document identity

- Corpora and staged samples are exactly `CORPORA` in
  `eval/bench_versus.py`: nt-studies (36), dita-spec (30), dtd-commands (48).
- A document ID is `<corpus>/<filename>`.
- Staged files are byte copies; the versus JSON sha256 manifest is the
  corpus identity. A corpus sample change requires a new qrels version.
- Ranking unit is document. Chunk hits are deduplicated by source file,
  preserving first (best) rank.

## Queries

- Queries are natural-language intents authored from corpus titles,
  headings and content, not copied file titles alone.
- Each query records: id, corpus, text, taxon, intent, authoring note and
  the concept family used during adjudication.
- Query text must not contain the expected filename or a unique identifier
  copied from only one document unless the intent is explicitly identifier
  lookup (taxon G6 mirrors precedent T6).
- Draft query IDs are immutable once qrels are frozen.

## Taxons

| Taxon | Intent shape | Depth question |
|---|---|---|
| G1 exact concept | one defined concept/mechanism | canonical explanation vs mentions |
| G2 procedure | how a mechanism is configured/used | complete procedure vs fragments |
| G3 comparison | distinction between neighboring concepts | both sides vs one side |
| G4 example | concrete example of a named mechanism | worked example vs prose mention |
| G5 paraphrase | intent without corpus wording | semantic reach without exact terms |
| G6 identifier | file/element/command identifier intent | exact owner vs references |

## Grades

| Grade | Meaning | Evidence required |
|---|---|---|
| 3 | Exact/primary: document directly and substantially satisfies the full intent | title/heading plus body treatment, or the defining section |
| 2 | Highly relevant: substantial partial answer, sibling mechanism, or one required side of a comparison | a dedicated section or sustained treatment |
| 1 | Marginally relevant: useful background, mention, prerequisite or one fragment | at least one concrete relevant passage |
| 0 | Judged irrelevant after inspection | candidate was in the judged pool and does not satisfy grade 1 |

Unjudged is a state, not grade 0. Metrics must report judged and unjudged
returned counts separately. Ideal rankings use all judged relevant docs in
qrels, including relevant docs no system returned.

## Pooling and blindness

1. Run every system to retrieval depth 20 per query.
2. Union returned documents by corpus/query (the pool).
3. Annotation view sorts candidates by document ID and shows title,
   headings and content excerpts. It must not show system names, ranks,
   scores or which systems returned a candidate.
4. Machine provenance (systems and ranks per candidate) is stored in a
   separate pool file for coverage analysis, never used to assign grades.
5. Curated canonical/family documents may be added to qrels even when no
   system pooled them; their provenance is `curated`, not `pool`.

## Annotation record

Each judgment records query_id, doc_id, grade, rationale, evidence
(title/heading/term), annotator, status (`judged` or `adjudicated`) and
qrels version. Ambiguous boundaries keep the rationale; silent relabeling
after a comparative run is forbidden. Corrections create the next qrels
version and require a full rerun.

## Metrics (frozen formulas)

- Gain: `2^grade - 1` (0, 1, 3, 7).
- DCG@k: sum over ranks `gain / log2(rank + 1)`, rank starting at 1.
- nDCG@k: DCG@k divided by ideal DCG@k from all qrel grades sorted desc.
- ERR@k: cascade with stopping probability `(2^g - 1) / 2^3` per rank.
- Graded precision@k: sum of gains in top k divided by `7 * k`.
- MAP: binary relevance at grade >= 2, standard average precision over
  judged-relevant denominator; unjudged returned docs count as ranks but
  never as relevant.
- Cutoffs: 3, 5, 10, 20. Continuity metrics R@1/R@3/MRR keep the
  precedent binary definition at grade >= 2 unless a report says otherwise.

## Freeze rule

`queries.json` and `qrels.json` carry `version`, `seed`, corpus manifest
hash inputs and counts. Once a comparative run starts, both files are
immutable for that run. Any change increments the dataset version and
invalidates comparisons against older scoreboards except as history.
