# Visual 3D Forge

**Compile "one reference image + one sentence" into a 3D web page you can double-click open.**

[中文说明](README.md) · MIT · three.js r187 pinned

![Planetary gearbox example](docs/screenshot.png)

<sub>`examples/planetary-gear-3d/` — module 2 mm, 18/21/60 teeth, ratio 4.33, exploded 62%. Fully procedural, no external textures.</sub>

## The problem

Ask an AI for a 3D page and it fails in a very specific way: **it spins, but it doesn't look like the thing.**
Not because the model is weak, but because the **intermediate representation is missing** — it jumps from
one sentence straight to `new THREE.Mesh`, with no layer saying *which parts make up this object, how big
each one is, and what it is made of*. Without that layer, the model can only fetch the nearest template
from its training distribution, and everything comes out as the same smooth box.

This skill inserts the IR:

```
request ─▶ intent card ─▶ part tree + dimension table + material hypotheses ─▶ geometry strategy ─▶ code ─▶ 19 checks
                                  └──────────────── IR ────────────────┘
```

**Build the model before writing code.** That is the one non-negotiable ordering rule.

## Four delivery modes

| Mode | Artifact | Measured size | Deps | When |
|---|---|---|---|---|
| **D0** | single `.html` | 13 KB | online (jsDelivr) | **default** |
| **D1** | single `.html` | 2852 KB | none | offline / intranet |
| **D2** | `.html` + `vendor/` | 13 KB + 2391 KB | none | readable sources |
| **D3** | React Three Fiber app | npm | build chain | React integration |

The mode follows the runtime environment, not "which one is fancier". If you pick D1, it must be truly
zero external requests — the validator checks.

## Five entry gates

Passed before the first line of code; **any gate may veto the whole task**.

| Gate | Question | Veto case |
|---|---|---|
| **G0 carrier** | Is a third dimension actually needed? | "make it move" is not a reason → use CSS/2D |
| **G1 intent** | Seven-field intent card complete? | object / purpose / audience / scale / must-have / droppable / mode |
| **G2 reference** | Which level, R1–R5? | below R3 you may not claim "exact reproduction" |
| **G3 budget** | Triangle & draw-call tier fixed? | web scenes don't need hundreds of thousands of triangles |
| **G4 dependency** | Where will this run? | offline requirement with a CDN build |

G0's exit is **"don't use WebGL"**. A pipeline that can only say yes is not a pipeline, it's a template.

## Quick start

```bash
# 1. decide the mode (references/00-delivery-modes.md), assume D1 (offline single file)

# 2. start from a scaffold — never hand-write the pipeline in a blank file
cp assets/scaffold/forged-scene.html ./task-x01/scene.html

# 3. modify the subject → bundle → check APIs → validate
python3 scripts/bundle.py --src ./task-x01/scene.html --out ./task-x01/offline.html --vendor ./assets/vendor
python3 scripts/validate_scene.py ./task-x01/offline.html --strict
```

Measured: 13.3 KB source → 2851.5 KB single file, 19/19 checks pass, zero remote references.

## The four tools

| Script | Purpose | The hard part |
|---|---|---|
| `vendor.py` | trim three.js from source | resolves addon relative-import closure recursively; emits `manifest.json` with hashes |
| `bundle.py` | inline vendor into one file | **must recursively inline the relative closure and rewrite to `vf-int-N`** — otherwise `./three.core.js` inside a data URL fails to resolve → white screen |
| `api_lookup.py` | verify an API really exists | 488-entry symbol table; `check` diffs the artifact and suggests the closest correct name |
| `validate_scene.py` | pre-delivery static self-check | 19 checks (D1) / 18 (D0, D2); `--strict` makes warnings fatal |

## Repository layout

```
SKILL.md            contract, gates, six stages, algorithm index (host-skill entry)
references/         13 stage-scoped references
assets/vendor/      three 0.187.0 trimmed to 18 files, hashed manifest
assets/scaffold/    D0 / D2 / D3 scaffolds
scripts/            four tools, standard library only
examples/           runnable example (planetary gearbox)
docs/               architecture, design notes, validation log
tests/              26 contract tests
```

## Verification

```bash
python3 -m pytest tests/ -q      # 26 passed
```

The tests turn the skill's promises into falsifiable assertions: document/frontmatter consistency,
bidirectional index integrity, per-file sha256 of the vendor manifest, stdlib-only scripts,
D0/D2 → bundle → D1 → 19 checks → zero remote refs → size sanity, plus a **negative test**
(delete the importmap: lenient warns, `--strict` must fail).

## Ten red lines (any hit = fail)

Precision lie · hallucinated API · material split · metalness as a gloss slider · decorative physics ·
default camera · perpetual drift · uniform spin as motion · particles hiding bad geometry · inconsistent
multi-view or no sense of scale.

## Honest limits

1. Static checks cannot judge aesthetics. 19/19 ≠ beautiful.
2. `api_lookup.py` needs three.js **source** (`npm pack three@0.187.0`); this package ships build artifacts only.
3. No visual regression: no pixel comparison against the reference.
4. `vendor/` commits 2.4 MB of binaries — the price of zero-network, zero-build delivery.
5. The skill body is Chinese; English readers get this README plus the code structure.
6. D3 ships a scaffold and a trap list, not a full R3F architecture.

## Docs

- [Architecture: why this is a compiler](docs/ARCHITECTURE.md)
- [Design notes: eleven decisions and their counterexamples](docs/DESIGN-NOTES.md)
- [Validation log](docs/VALIDATION.md)
