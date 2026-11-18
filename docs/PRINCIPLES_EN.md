# Engineering principles · the standard we ship to

> v1.0 · 2026-11-18
> This is not a values poster. It is an **acceptance checklist**: every line can be falsified by a code review, a test, or a screenshot.
> Chinese version: [`PRINCIPLES.md`](./PRINCIPLES.md)

---

## 0. One premise

**Verifiable beats trustworthy.**

Nothing in this repository stands on "the author is a professional". Every claim has to land on one of three things: a command that runs, a test that can go red, a page that opens.

A principle you cannot violate is a slogan. If it can be violated, something should be there to stop it. Each of the ten below is paired with the time we actually broke it.

---

## 1. Make errors visible before making them rare

A tool that only demonstrates success proves nothing about whether it understands the problem. The playground's first feature is not "generate a pretty gear" — it is **refusing an illegal tooth ratio**, and telling you how far the nearest legal one is.

What earns trust is not "it got it right", it is "it knows what counts as wrong".

> We broke it: early versions always produced *some* result for any input, so the page was permanently green. Too green to trust.

---

## 2. Determinism is a feature, not an optimisation

The same input, compiled twice, must produce a byte-identical fingerprint. Change one number, the hash must change; change nothing, it never does.

This rules out a whole class of "let's add a little noise so it feels natural" — and those are exactly the ideas that make an artefact impossible to sign off.

> We broke it: added noise to gear faces for texture. Two compiles of one SpecSheet produced two different glb files, and nobody could tell whether the file on the table was the one they approved.

---

## 3. Every number states where it came from

Dimensions carry one of three grades, written on the page and visible at a glance:

| Grade | Meaning | On screen |
|---|---|---|
| **measured** | dimensioned on the drawing | green edge, callout id on hover |
| **standard** | NEMA / GB / ISO | grey edge, standard number shown |
| **inferred** | derived from proportion, symmetry or priors — **not on the drawing** | amber edge, basis explained on hover |

No modelling tool volunteers "I guessed this number", because that is bad for selling software. The person signing off cares about exactly that sentence.

> We broke it: filled an inferred bore diameter in as measured because it "looked about right". Report fully green. Off by 4 mm at assembly.

---

## 4. Errors caught at compile time must not be left to the eye

Anything decidable at build time gets decided at build time: profile winding, degenerate normals, unit mismatches, holes outside the outline, AABB interference, evidence that cannot be located.

What these share is that **they never throw**. They just look slightly off — and "slightly off" is the most expensive kind of debugging.

> We broke it: a lathe profile wound the wrong way. The entire outer wall got back-face culled, so the screen showed the far inner wall as a set of inexplicable diagonal bands. Three passes on materials, two on shadows, one on environment maps — the answer came from printing a normal dot product.

---

## 5. Degrade out loud, never silently

A blurry drawing, a missing dimension, conflicting constraints — each must become a specific "this is what is missing", not a plausible-looking artefact filled in with defaults.

**Looking complete is far more dangerous than looking broken.**

> We broke it: when the assembly solver failed, we snapped parts to the nearest fit. Two parts overlapped, the page looked fine, and it held until someone measured the physical prototype.

---

## 6. Offline-openable is a hard constraint

The artefact is a single HTML file: no network, double-click, it spins. No CDN, no remote fonts, no build service, no account.

This is not purism. A confirmation page gets opened on a meeting-room projector, inside a WeChat message, on a factory floor with no Wi-Fi. Any network dependency fails exactly when it matters.

> We broke it: wrote `assets/vendor/three.module.js` in the import map, missing the leading `./`. Chromium parsed it as `null`, loaded zero modules, made zero requests, and printed one line: `blocked by a null value`. Blank page in production, fine locally — because locally it was served with a directory index.

---

## 7. Visual problems are measurement problems

"It's a bit small", "it feels empty", "the colour is dirty" — none of these belong in a review. They become numbers: percentage of frame occupied by the model, pixel margins on each edge, shadow histogram, material separation.

What can be measured can be fixed. What can only be felt will be changed forever.

> We broke it: seven rounds of "still doesn't feel right". One line of numpy counting model pixels (17%) revealed the problem was never lighting — it was camera distance, computed from a bounding sphere, on a part that is long and thin.

---

## 8. Refuse rather than guess

When a gate fails, return failure and say which item is missing. No best-effort fallback, no quietly turning `null` into `0`.

A tool that can say "I can't do this here" is the only kind fit for a production pipeline.

> We broke it: the `at` offset on a `shape` was silently dropped, so every hole sat at the origin — and the "holes inside outline" check **passed forever**. The check was green because it was measuring nothing.

---

## 9. Docs live in the same pipeline as code

Commands in the README must run. Links in the docs must resolve. Chinese and English must match section for section. Tests enforce all three; discipline does not scale.

Once documentation is allowed to rot, it loses trust faster than having none.

> We broke it: a new section went into the Chinese README and never reached the English one. The two files described two different products, and the commands in the English one did not exist.

---

## 10. Ship so someone else can finish it, not so you can present it

The measure is not "the author can demo it". It is "someone who was not in the room produces a version in 30 minutes, within 2% on dimensions".

A smooth demo only proves the author knows how to use it.

> We broke it: the demo script ran beautifully. A colleague got stuck on step two — it depended on an environment variable on the author's laptop.

---

## Red lines (hitting one disqualifies the output)

- Any remote URL in the artefact
- Two compiles of one input with different fingerprints
- An inferred value labelled as measured
- A check that passes because it measured nothing
- A geometry error found by eye rather than by a failed build
- A command in the docs that does not run
- Chinese and English telling different stories
- An interaction that only works at one resolution
- A deliverable that needs the author present

---

## How to use this document

1. **Before a PR**: run the red lines as a checklist. Hit one, don't open it.
2. **In review**: don't say "this isn't great". Say "this breaks principle N", and give the measurable gap.
3. **Designing a feature**: ask what its failure looks like. If you can't answer, it isn't designed yet.
4. **When you deadlock**: whoever can turn it into a test that goes red wins.

> This document gets edited too. The way to edit it is not to argue about wording — it is to bring the incident it failed to stop, and add a test.
