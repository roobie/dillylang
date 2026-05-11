---
name: dillylang-rotate
description: Changes the frame of inquiry via implicit-subject probe. Trigger= /dillylang-rotate PROBLEM
argument-hint: "[target_frame] [--axis-only] [--view-only]"
---

# Dillylang `rotate`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

Change the axis of inquiry. Identify what's implicitly centered in the
current framing, then rotate to alternatives that reveal what the
original framing hid.

Rotate is not "consider another perspective" — it's a structural move
that changes what's *visible*. If the rotation doesn't make something
new visible and something old recede, it hasn't rotated.

## Arguments

**Optional:** A `target_frame` — the frame of reference to rotate toward.

- Bound: `/dillylang-rotate 'end user'` — rotates toward that frame,
  plus at least one rotation of the other kind discovered during the probe.
- Unbound: `/dillylang-rotate` — open-ended frame exploration via the
  implicit-subject probe.

**Flags:**

| Flag | Default | Effect |
|------|---------|--------|
| `--axis-only` | no | Only axis_change rotations (filter out viewpoint_change) |
| `--view-only` | no | Only viewpoint_change rotations (filter out axis_change) |

When neither filter flag is set, produce 3–4 rotations with at least one
of each kind.

## Prompt constraints

- **Probe first, rotate second.** Before generating any rotations, identify
  the implicit subject of the original framing — who or what is being
  centered. This is where rotate's leverage lives. The probe must find
  something *specific to this problem's framing*, not a default subject
  for the problem's domain.
- **Specific probe, not generic.** "The developer" fails as an implicit
  subject for software problems — it's the default observer, not an
  interesting centering choice. "The write path" passes — centering writes
  over reads is a genuine framing decision that could have been different.
- **Rotate, don't relabel.** A rotation that uses different vocabulary to
  describe the same perspective has not rotated. "From a quality assurance
  perspective, we need better testing" is a relabeling of "we need better
  test coverage," not a rotation.
- **`what_recedes` must be concrete.** Every rotation gains visibility at
  a cost. `what_recedes` must name something that would change a concrete
  decision, not just "receive less focus" or "become less salient."
- **Restate, don't append.** `restated_problem` must re-see the problem
  through the new frame, not append the new frame's concerns to the
  original problem. "Our API latency is too high, which affects revenue"
  is an append. "Our product is losing competitive deals on responsiveness"
  is a restatement.
- **Bound invocations stay focused.** When `target_frame` is provided,
  produce one primary rotation to that frame. Additional rotations go to
  genuinely different frames discovered during the probe — not subdivisions
  of the target frame.
- **Minimum one of each kind** (when unfiltered). At least one axis_change
  and at least one viewpoint_change. Axis changes are harder to generate
  than viewpoint changes — the model will gravitate toward "from X's
  perspective" templates unless forced past them.

**Calibration examples:**

Rejected (relabeling): "Original: 'We need better test coverage.'
Rotation: 'From a QA perspective, we need more thorough testing.'
what_becomes_visible: ['testing gaps', 'quality metrics']."
(Same question in QA vocabulary. what_becomes_visible lists things
already visible in the original framing.)

Rejected (vague recedes): "what_recedes: ['some implementation details
may be less salient']."
(True of any rotation. Name the specific thing that recedes and what
decision it would have affected.)

Rejected (append, not restate): "restated_problem: 'Our API latency is
too high, which is causing customer churn and revenue loss.'"
(Appends consequences to the original. The API is still the subject.)

Accepted: "Implicit subject: the *write path* — the original frames
latency as a write-throughput problem. Rotation: center the *read path*.
restated_problem: 'Read-heavy consumers are blocked by a system
optimized for write throughput.' rotation_kind: 1 (axis_change).
what_becomes_visible: ['cache invalidation patterns', 'read replica
lag as the actual user-facing bottleneck'].
what_recedes: ['write batching optimizations — the team would deprioritize
the current write-coalescing work, which is 2 sprints in']."

## Output template

### Implicit subject

Name what the original framing centers — the subject, dimension, or
stakeholder that's treated as default. State why this is a *choice*,
not a given — what alternative centering would be plausible?

### Rotations (RT-n)

Each rotation must include:

- **new_axis:** the frame being rotated to
- **rotation_kind:** `1` (axis_change), `2` (viewpoint_change), or `3` (both)
- **restated_problem:** the original problem re-seen through this frame —
  not appended to, not summarized, re-seen
- **what_becomes_visible:** specific things now visible that were hidden
- **what_recedes:** specific things now hidden that were visible, with
  what concrete decision they would have affected

Produce 3–4 rotations when unbound. When filtered (`--axis-only` or
`--view-only`), produce 2–3 of the requested kind.

`n` is sequential starting from 1.

## Self-review

After generating rotations, check two things:

**1. Relabeling detection.** For each rotation, compare `what_becomes_visible`
against what the original framing already made visible (explicitly or
implicitly). If >50% of the visibility items were already accessible in the
original frame, the rotation is a relabeling — strengthen or replace it.

**2. Restatement quality.** For each `restated_problem`, check lexical overlap
with the original problem statement. High overlap (>40% of content words
shared) suggests appending rather than restating. A genuine rotation should
use substantially different vocabulary because it's seeing different things.
