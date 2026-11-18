# Drawing-to-Confirmation · a 26-week roadmap

**Compile "one dimensioned drawing + one sentence of intent" into "a 3D confirmation page you can spin, section and measure".**

> v1.0 · 2026-11-18 · Chinese: [`ROADMAP.md`](./ROADMAP.md)
> [`STRATEGY-2026.md`](./STRATEGY-2026_EN.md) answers *where to go*. This document answers *where we stand, how we move, and what ships each week*.
> Moat and algorithm ordering are inherited; **product position and cadence are defined here.**

---

## 1. The difference that matters

The question is: both have 3D — what separates us from Blender / C4D / Spline.

It is not "our rendering is weaker" or "our modelling is thinner". It is three more fundamental differences.

### Difference one: who makes the decisions

| | Blender / C4D | Spline | Us |
|---|---|---|---|
| Decision maker | **A person**, vertex by vertex, edge by edge | **A designer**, dragging components | **The spec** — the number on the drawing |
| Software's role | Hand | Hand (a nicer hand) | **Translator** |
| Skill required | High (~300 h) | Medium (~30 h) | **Low — read the drawing** |

Blender's value = a person's hours × a person's skill. It cannot decide "what is this flange's outer diameter", because that is not a thing software is supposed to know.

In the cases we handle, **someone has already decided that number** — it is on the drawing, in the datasheet, in the screenshot the client sent. What remains is not creation, it is **translation**.

> One line: **they amplify craft; we delete the translation step.**

### Difference two: what the artefact is

An asset is editable, continuable, has no end. A statement is read-only, deterministic, finished.

| | Asset (Blender / C4D) | Statement (us) |
|---|---|---|
| Editable | Yes — that's the point | **No — that's the promise** |
| Same input → same output | Not guaranteed | **Guaranteed, hash-verified** |
| When it's done | Never quite | When the checks pass |
| Who receives it | The next artist | The person signing off |

Read-only is not a limitation we apologise for. It is the only form in which "this is what we agreed" can exist.

### Difference three: which cell on the timeline

```
concept → spec → [CONFIRM] → model → render → deliver
                    ↑
              this cell is empty
```

Blender owns model→render, and we will never take that. The confirm cell is currently held by "wait three days for the modelling queue" or "draw some boxes in PowerPoint".

**That is the cell we occupy.** It does not need to be beautiful. It needs to be right, fast, and spin in the room.

> Three words: **they build models, we build consensus.**

---

## 2. Why this position is both safe and large

### Safe: three things a model will not do for us

1. **Decide which number is which.** "160 is the outer diameter, not the length" is a judgement about a drawing, not a pattern in pixels.
2. **Make twelve dimensions agree with each other.** A model produces plausible geometry; it does not produce a contradiction report.
3. **Say which number it invented.** This is a liability question, not a capability question.

### Safe: 3D software will not descend here

Shipping "a confirmation page in three minutes" tells customers they do not need a seat. And the buyer is marketing or project management, not the 3D department — there is no sales channel for it.

### Large: one metric you can invoice against

**Hours from "we have a drawing" to "everyone agrees on the shape".** Today that is 2–5 days at a design institute, 1–2 days at a small manufacturer, and "whenever the designer is free" at an agency.

We are not competing on model quality. We are competing on the length of that interval.

---

## 3. Product definition: a three-layer contract

The whole chain is three things. Get these right and the rest is engineering.

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ ① SpecSheet     │     │ ② Spec-IR       │     │ ③ Three outputs  │
│ drawing + table │ ──▶ │ parts/scale/asm │ ──▶ │ page/report/draft│
│ + intent card   │     │ + evidence chain│     │                  │
└─────────────────┘     └─────────────────┘     └──────────────────┘
    human: 30 min            compiler solves        open and spin
```

### ① Input contract: SpecSheet (a human *identifies*, never models)

One YAML file (JSON also accepted), four blocks:

```yaml
source:                    # where the drawing came from, how far to trust it
  image: drawing.png
  grade: R1                # reuses the R1–R5 scale
  note: three views, dimensioned

intent:                    # the seven-field intent card, nothing dropped
  object: single-stage gear reducer R40
  purpose: confirm assembly order and overall envelope
  audience: 有基础
  scale: 1:1
  must: [input shaft, output shaft, housing, gear mesh]
  drop: [oil galleries, bolt chamfers]
  delivery: D1

parts:                     # the part list: what it is, plus a few numbers
  - uid: housing
    label: 箱体
    kind: revolve          # one of five primitives
    axis: z
    params:
      profile: [[0,0],[80,0],[80,120],[0,120]]
    evidence:              # every number states its provenance
      外径: { value: 160, src: "图注 A2", grade: measured }
      长:   { value: 120, src: "图注 A3", grade: measured }
    explode: [0, 1, 0]

assembly:                  # intent as constraints, not coordinates
  - { type: mate, a: shaft_in, b: housing, offset: 0 }
  - { type: mount, ... }

views:
  - { kind: iso }
  - { kind: section, axis: z }
```

**The design decision**: no coordinates, only relations. The compiler solves the positions.

That is the real line between this and drag-and-drop modelling. The dragger is doing geometry; the constraint writer is doing **intent**. Intent is reproducible; geometry is not.

### ② Intermediate representation: Spec-IR

The compiler's only source of truth. Flat, explicit, no DSL left inside:

- **parts** — uid, label, kind, axis, material, expanded params, evidence with grades **and anchors**
- **transform** — solved world position per part
- **report** — checks C1–C6, coverage, counts, orphans
- **views**, **source**, **intent**

Everything downstream reads only this. The page, the report, the future glTF export. One representation, three consumers.

### ③ Output contract: three artefacts, three purposes

| Artefact | Who reads it | What it must do |
|---|---|---|
| **Confirmation page** (single HTML) | the person signing off | spin, section, explode, hover a number and see where it came from |
| **Conformance report** (HTML + JSON) | the project lead, the archive | pass/fail per check, coverage, fingerprint |
| **IR / draft** (JSON → glTF) | the modelling artist | open in Blender at 1:1, named by uid |

---

## 4. Technical core: five primitives + one solver

This is the line between "deliverable promise" and "talk". General modelling is out of scope. We cover the five families that make up ~80% of machined and product parts:

| Primitive | Covers | Implementation |
|---|---|---|
| `revolve` | shafts, sleeves, flanges, hubs, end caps, housing bodies | `LatheGeometry` + profile |
| `extrude` | plates, brackets, profiles, shell walls | `ExtrudeGeometry` + outline + depth |
| `gear` | spur / helical / internal | parametric tooth profile |
| `pattern` | bolt circles, fins, arrays | `InstancedMesh` |
| `hole` | through / counterbore / tapped | cut in the profile, shown by section |

**Why these five**: every one is determined by "one outline + a set of scalars". The outline can be traced from a three-view drawing; the scalars are the numbers already on it. **None requires topology editing by a human.**

### The solver: scale consistency + assembly constraints

Two small, deterministic problems:

1. **Scale coherence** — given dimensions and relations (coaxial / flush / symmetric), check for contradiction. If `total 120 ≠ 60 + 60 + 2×6`, it goes red.
2. **Assembly placement** — `mate`, `mount`, `pattern`; topological solve of world transforms; report the conflicting pair instead of picking one.

Neither needs AI, and neither should use it. **They can be unit-tested**, and testable = promiseable = priceable.

### Honest degradation: when the drawing is not enough

| Drawing quality | What we do | How the page says it |
|---|---|---|
| R1 dimensioned three-view | measure everything, error < 1% | all green |
| R2 multi-angle photos | measure principal dims, infer depth | green primary, amber depth |
| R3 single photo | proportion only, absolute scale from priors | banner: "absolute size inferred, proportions reliable" |
| R4 sketch | form only | all amber + "indicative, not measured" |
| R5 text only | intent → IR path | marked "no reference drawing" |

**That table is not a disclaimer. It is a price list.** An R1 job can be sold at 10× an R4 job, because what can be promised is different.

---

## 5. 26 weeks: four stages, one falsifiable gate each

The rule: **no gate, no next stage.** Better to finish one stage than to half-finish four.

### P0 · W1–W4 | Replace the entrance: from "a sentence" to "drawing + table"

**Goal**: prove that human-fills-table → machine-produces-page works, with **zero dependence on a large model**.

| Week | Task | Deliverable | Done when |
|---|---|---|---|
| W1 | SpecSheet + IR schema | `spec/schema/*.json` | both validate with `jsonschema` |
| W1 | five primitives at runtime | `spec/runtime/` | each primitive renders correctly on its own |
| W2 | assembly solver | same | 10 assembly cases solve; conflicts report |
| W2 | compiler CLI: YAML → IR → HTML | `tools/spec_compile.py` | one command produces a single-file page |
| W3 | evidence colouring + hover provenance | `spec/runtime/viewer.js` | three grades distinguishable on screen |
| W3 | conformance report | report template | every dimension shows source and grade |
| W4 | three real cases | `spec/examples/*.yaml` | reducer / bracket / frame |

**Gate**: hand a person who was not in the room a dimensioned drawing and an empty table. **30 minutes**, a page that spins, **envelope error < 2%**.

**Not doing**: image recognition (that's P2), material realism, animation.

> Why: get determinism working first. If P0 cannot hit 30 minutes, nothing downstream matters.

**Status: ✅ shipped** — `spec/examples/nema23-actuator.yaml` compiles to a 10-part confirmation page with C1–C6 passing.

### P1 · W5–W10 | Evidence chain: every number can be interrogated

**Goal**: from "looks right" to "can explain why it is right".

| Week | Task | Deliverable | Done when |
|---|---|---|---|
| W5 | **dimension → geometry anchoring** | `locate_evidence()` in the compiler | every dimension resolves to a span, diameter, profile, hole or pitch, or is reported as unlocated |
| W5 | dimension lines in the viewport | `viewer.js` | line lands outside the part outline, no overlap |
| W6 | scale-coherence solve (linear system + conflict) | solver module | contradictory input goes red with the conflicting pair named |
| W7 | report upgrade: coverage + **location rate** | report page | coverage < 60% raises an amber banner |
| W8 | section system (axial / radial / arbitrary plane) | `viewer.js` | interior visible, no z-fighting |
| W9 | measure interaction (pick two points, compare to the table) | in-page tool | user-measured value matches the report |
| W10 | five-case regression + archived fingerprints | `spec/regression/` | recompiling five cases yields stable hashes |

**Gate**: randomly pull 20 dimensions, send them to a third party for provenance check. **The count of "inferred presented as measured" must be 0.** Missing labels allowed; wrong labels not.

**Not doing**: OCR (too early), multi-user collaboration.

> Why: honesty has to be productised, otherwise it is a slogan.

**Status: 🟡 in progress** — anchoring is live: 26/26 dimensions land on geometry, 4 dimensionless params excluded from the denominator, C6 in the report.

### P2 · W11–W18 | Semi-automatic inversion: drawing → primitive suggestions

**Goal**: cut "fill the table" from 30 minutes to 5. **Suggestions**, not generation.

| Week | Task | Deliverable | Done when |
|---|---|---|---|
| W11 | drawing preprocess: denoise, deskew, scale detection | `vision/preprocess.py` | auto-corrects up to 15° skew |
| W12 | contour extraction (Canny + line/arc fit) | `vision/contour.py` | closure rate > 90% on three-view drawings |
| W13 | primitive classifier (revolve / extrude / pattern) | `vision/classify.py` | top-1 > 70% over 50 samples |
| W14 | dimension OCR + arrow pairing | `vision/annotate.py` | digits > 90%, pairing > 80% |
| W15 | suggestion panel (accept / reject, logged) | front end | every suggestion rejectable; reject is recorded |
| W16 | feedback loop: rejects enter the training set | `vision/feedback.py` | weekly retrain |
| W17 | three-view consistency | `vision/views.py` | same dimension across views within 3% |
| W18 | end to end: upload → table → page | demo | under 5 minutes |

**Gate**: on 50 real drawings, **first-pass > 50%, within two passes > 85%**.

**Not doing**: scan-to-CAD, freeform surfaces.

> Why: move a human from filling 40 numbers to editing 8. **Lower the barrier, don't remove the human.**

### P3 · W19–W26 | Draft: make the modelling artist want to take it

**Goal**: prove we plug into someone else's pipeline instead of building an island.

| Week | Task | Deliverable | Done when |
|---|---|---|---|
| W19 | glTF export (PBR + hierarchy + 1:1 scale) | `spec/export/` | Blender opens it, bounding box within 1% |
| W20 | material mapping (IR → glTF PBR) | `materials.json` | 8 common materials round-trip |
| W21 | `ir2blend.py`: IR → Blender scene, named by uid | `spec/bridge/` | every object name = uid, script-recoverable |
| W22 | `blend2ir.py`: write back material/dimension edits | `spec/bridge/` | change a colour, recompile, see it |
| W23 | USD minimal subset (Xform / Mesh / Material) | `spec/export/usd.py` | `usdchecker` passes |
| W24 | joint test with a working modelling artist | test log | their own words go into the README |
| W25 | delivery packager (page + report + glb + readme) | `tools/deliver.py` | one zip, four files, double-click |
| W26 | public docs + gallery | gallery page | a stranger says what it is within 30 seconds |

**Gate**: an artist takes the draft from "start" to "renderable" in **> 40% less time** than modelling from scratch. Timed by them, not estimated by us.

**Not doing**: real-time bidirectional sync, C4D/Houdini adapters. One integration, done properly.

---

## 6. Four risks, and the answer to each

### Risk 1: being read as "a cut-down modelling tool"

Every screenshot invites the comparison, and in that comparison we lose.

**Answer**: never compete on editability. Every artefact carries "confirmation, not a model" in the corner. The moment we ship an edit handle, the comparison becomes fair and we lose.

### Risk 2: the drawing is too poor to compile

Most real inputs are phone photos of a printout.

**Answer**: the degradation table in §4, and the R-grade price list. Refuse R5 rather than fake it.

### Risk 3: five primitives do not cover enough

They won't. Someone will send a casting with draft angles and fillets.

**Answer**: the scope line is explicit — machined and product parts, not organic or sculpted. When a request falls outside, say so and quote a partner. **Saying no is part of the product.**

### Risk 4: nobody wants to fill in a table

True for the first version. A 40-row table is worse than opening Blender.

**Answer**: P2 exists for this. Until suggestions ship, the table stays under 12 rows by design — if it needs more, the part is out of scope.

---

## 7. North star and stage metrics

**North star**: hours from drawing to agreement, measured on real jobs.

| Stage | Metric | Target |
|---|---|---|
| P0 | time to first page, new user | < 30 min |
| P1 | dimensions with provable provenance | 100% labelled, 0 mislabelled |
| P1 | dimensions anchored to geometry | > 90% |
| P2 | first-pass acceptance on real drawings | > 50% |
| P3 | artist time saved | > 40% |

Deliberately absent: number of users, GitHub stars, render quality scores. None of them survive contact with a paying job.

---

## 8. One page

| Question | Answer |
|---|---|
| **Biggest difference from Blender/C4D** | they amplify craft; we delete the translation step |
| **What we sell** | not a model — **consensus**, "we can see it now" |
| **Which position** | the *confirm* cell on the project timeline, before modelling, outside rendering |
| **What ships** | confirmation page (HTML) + conformance report + a draft (glb) for the artist |
| **What it runs on** | five primitives + one constraint solver + an evidence chain. **No large model required** |
| **The one unique thing** | telling the user "this number is my guess", visibly, without being asked |
| **26 weeks** | entrance (W1–4) → evidence (W5–10) → inversion (W11–18) → draft export (W19–26) |
| **Not doing** | no editor, no renderer, no general modelling, no organic surfaces |
| **How to price** | by R grade: an R1 job sells at 10× an R4 job |

---

> Last line, for the position itself:
>
> **In this industry the fastest one is not the one who computes fastest — it is the first one who gets someone to say "yes, that's it".**
>
> Blender lets one person spend three days making a model. We let three people spend thirty minutes reaching agreement.
>
> The first is craft. The second is a business.
