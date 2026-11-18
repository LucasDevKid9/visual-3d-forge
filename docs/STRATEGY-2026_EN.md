# Strategy 2026 · moats, algorithms, interfaces, market order

> v1.0 · 2026-11-18 · Chinese: [`STRATEGY-2026.md`](./STRATEGY-2026.md)
> Companion: [`ROADMAP.md`](./ROADMAP.md) — the 26-week execution plan that follows from this.

---

## 1. First, reject a positioning

The positioning to reject: **"AI that generates 3D models".**

Three reasons it fails:

1. **The deliverable is wrong.** A generated model is a guess shaped like an asset. What a business needs at the confirmation step is a *statement* it can sign: these dimensions, this assembly order, this is what I am not sure about.
2. **The moat is wrong.** Generation quality is a function of someone else's base model. Every improvement upstream deletes your product.
3. **The buyer is wrong.** Whoever wants a model already has Blender. Whoever needs agreement does not have a tool at all.

What we actually sell: **a drawing goes in, a confirmation comes out, and every number in it can be interrogated.**

---

## 2. Moat: four things a model will not do on its own

### 1. Determinism (same input → same output)

A model gives you *a* plausible result. A pipeline gives you *the* result, twice, with a hash to prove it. Once an artefact has to be signed, non-determinism is disqualifying, not inconvenient.

### 2. Verifiability (the artefact carries its own certificate)

Not "we checked it" — a report with named checks, the numbers they measured, and the tolerance they used. The certificate is part of the deliverable, not a conversation after it.

### 3. Continuability (professional tools can take it over)

The confirmation is not the end. It has to become a glTF/USD scene that a modelling artist opens at 1:1, with object names equal to `uid`, so scripts can find them again. Anything that cannot be continued is a dead end and gets priced as one.

### 4. Domain priors (knowing what this thing *should* look like)

A desk is 750 mm high. A NEMA23 flange is 57.15 mm square with 47.14 mm hole spacing. A door needs 600 mm of clearance. These are not in the training data as *rules*; they are in standards documents and in the heads of people who have built the thing.

**Priors are the only one of the four that cannot be copied by a competitor with a bigger model budget.**

---

## 3. Algorithms: six capabilities ranked by ROI

Not "which AI to add" — **which deterministic algorithms to build**. Earlier means build it yourself; later means use what exists.

| # | Capability | Today | What to add | Source | ROI |
|---|---|---|---|---|---|
| 1 | **Geometric validity** | 19 structural checks | topology (non-manifold / self-intersection / normals), BVH interference, assembly clearance | `three-mesh-bvh` + `manifold-3d`, glue in-house | ★★★★★ |
| 2 | **Scale priors** | guessed by an LLM | ergonomics / building modules / vehicle parameters / process library | **must be in-house** | ★★★★★ |
| 3 | **Perceptual calibration** | hand-tuned exposure | histogram-targeted auto exposure, white balance, contrast calibration | in-house, < 200 lines | ★★★★☆ |
| 4 | **Auto framing** | hand-tuned camera | bbox + saliency + rule-of-thirds / golden-ratio constraint solve | in-house | ★★★★☆ |
| 5 | **Performance budget** | fixed quality tier | triangle / draw-call budget, LOD by target frame rate, texture sizing | in-house | ★★★☆☆ |
| 6 | **Semantic inversion** | none | reference image → parameters | depends on a VLM; calibrate afterwards | ★★★☆☆ |

### Why #1 is the highest priority

It is the physical basis of the word "deliverable".

A self-intersecting model may look fine on a web page — back-face culling and lighting hide it. It fails the moment it enters a 3D printer, a CNC path, or a game engine's collision mesh. One bad delivery and the customer never trusts the second.

And it can be **measured**: build 200 models with known defects, report the detector's recall. That number can go into a contract.

### Why #2 must be in-house

It is the only item that cannot be learned from public data, because it is trade knowledge.

Ask for "an office desk" and a model produces 750 mm height — correct, that is the standard. Drawer depth, knee clearance, cable grommet position: guessed. Those numbers live in GB/T 3326, and in the head of a carpenter.

Made as a prior library plus constraint checks, it is a product. Left as "write a longer prompt", it stays a demo.

### A counter-intuitive conclusion

**#6 looks the most like "AI" and should be built last.**

It is the only one whose quality depends on an external model. Image understanding improves every year; an inversion pipeline built this year gets absorbed by the base model next year.

So build it as a **replaceable adapter**: a VLM today, a better VLM tomorrow, while `parameters → IR → artefact` never changes.

---

## 4. Integration: three levels of interface with professional software

### L0 · Export (1–2 weeks)

glTF 2.0 with PBR materials, hierarchy, 1:1 scale. Opens in Blender, C4D, Unreal, Three.js. This level is table stakes and should have shipped yesterday.

### L1 · Exchange (1–2 months)

AED-style round trip: `IR → .blend` with a naming contract (`uid` → object name), and `blend2ir` to write material and dimension edits back. The artist works in their tool; we keep the evidence chain.

### L2 · Write-back (3–6 months, bidirectional)

USD as the interchange layer — Xform / Mesh / Material subset first, `usdchecker` in CI. This is where we become a node in a studio pipeline rather than a separate island.

**The rule at every level**: never ask the professional to leave their tool. Ask only that our artefact arrives in a form their tool already understands.

---

## 5. Commercial: five directions, one order

Conclusion up front: **enter through brand interaction, establish the benchmark with configurators, scale through e-commerce product pages.**

| Direction | Deal size | Barrier | Cycle | Order |
|---|---|---|---|---|
| **Brand interactive H5** | ¥30k–150k | low (but taste-gated) | 2–4 weeks | **① first** |
| **Automotive / industrial configurator** | ¥300k–2M | **high** | 3–6 months | ② benchmark |
| **E-commerce 3D product page** | ¥500–5k / SKU | medium | days | ③ scale |
| **Architecture / interior** | ¥50k–500k | medium-high (BIM) | 1–3 months | ④ later |
| **Education / science communication** | low, policy-friendly | low | long | ⑤ opportunistic |

### Why brand interaction first

1. **It is exactly this demo's shape.** NOVA X-01 is a brand page: a product, scenes, parameters, interaction, something worth sharing.
2. **The acceptance criterion is "beautiful", not "exact".** Our current stack — rendering, camera work, HUD — is enough.
3. **It produces cases**, and cases are the only sales material in this line of work.
4. **It is forgiving.** A failed H5 does not break a client's pipeline. A failed configurator does.

### Why configurators second

It is the only category that uses **all four moats at once**:

- Determinism — the same SKU configuration page must look identical today and in three months
- Verifiability — wheels must not intersect arches; door travel must not hit the mirror
- Continuability — the OEM wants the model inside CATIA / VRED
- Priors — wheelbase, track, ground clearance, paint process all have right answers

And this demo is already a prototype: part matrix (exploded view), spec console (parameters), material switch (paint), test track (performance). **Those are the four core screens of a configurator.**

### Why e-commerce third

High volume, small tickets, low bar — but it needs **scale** (500 SKUs this week), and scale needs a template library plus automated acceptance. Do it before the first two and it becomes a staffing agency.

---

## 6. On the "creative workshop": my recommendation is no

The question was whether to build a unified creative workshop.

### Reason one: a workshop is panel-thinking, and panel-thinking slides into low-code

The moment you ship a panel, the comparison set becomes Spline, Wix 3D, and every no-code tool. You are now competing on widget count, which is a war of attrition against funded teams.

### Reason two: a workshop destroys the one advantage

A confirmation is valuable **because it cannot be edited**. Put an edit handle on it and it becomes a draft — and drafts are judged by how much they can do, which is the game we already decided not to play.

### What to do instead

**A gallery, a compiler, and a certificate.**

- **Gallery**: finished confirmations, openable, shareable, no sign-up. This is the marketing.
- **Compiler**: the table, the constraints, the checks. This is the product.
- **Certificate**: coverage, location rate, fingerprint. This is the thing that gets signed and archived.

A workshop invites people to make things. A gallery invites them to *agree* on things. The second is a business.

---

## 7. Twelve-month plan

### P0 · weeks 0–8 | the demo becomes the standard

Ship the confirmation compiler end to end; three real cases; C1–C6 all green; a page that opens offline. Gate: an outsider produces a version in 30 minutes within 2%.

### P1 · months 2–4 | IR 2.0 + bidirectional export

Stable `uid` on every part; glTF out; `ir2blend` / `blend2ir` round trip; fingerprint archived per delivery. Gate: a modelling artist opens the draft in Blender and finds nothing to rename.

### P2 · months 4–7 | from structural to geometric validation

Topology checks, BVH interference, clearance, scale-prior library. Gate: 200 defective models, recall > 90%, false positive < 5%.

### P3 · months 7–12 | one vertical, landed

Pick the configurator (or the H5 line) and finish one paid project with the full chain: drawing → confirmation → draft → delivered asset. Gate: invoice paid, and the client reuses the confirmation page without us.

---

## 8. Three risks

### Risk 1: model capability eats the generation layer

It will, eventually. Answer: stay downstream of generation. The confirmation is about *agreement*, not *shape*; agreement does not get cheaper when generation does.

### Risk 2: single-file delivery replaced by online editors

Partly true. Answer: the file is not the product — the **certificate** is. Certificates are wanted precisely where editing is not.

### Risk 3: demo-only, never production

The most likely failure. Answer: the gate metrics in the roadmap are all measured on real jobs, by other people. If a gate cannot be measured that way, it is not a gate.

---

## 9. One page

| Question | Answer |
|---|---|
| What we do | compile a dimensioned drawing into a confirmation you can spin and interrogate |
| What we do not do | generate models, edit models, render films |
| Why it holds | determinism, verifiability, continuability, domain priors |
| What to build first | geometric validity, then scale priors — not image understanding |
| How we plug in | glTF (weeks) → .blend round trip (months) → USD (quarters) |
| Where the money starts | brand H5 → configurator → e-commerce |
| What we refuse to build | a creative workshop |
| How we are judged | hours from drawing to agreement |
