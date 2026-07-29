# UTM DIC — Innovation & Automation Roadmap

Status of the "smart UTM" features (automated test modes, live DIC, one-click workflow, safety).
Living source of truth; the V6a deck's roadmap slides are generated to match this.

**Legend:** ✅ done + **rig-validated** · 🟢 built (offline/sim-validated) · 🟡 partial / in progress · ⬜ planned · 🔴 blocked by hardware

_Last updated: 2026-07-29 — full rig-test campaign complete (see `TESTING_TODO.md`)._

---

## 1. Implemented & validated

### Shared foundations (offline modules, tracked in git)
| Feature | Module | Status | Evidence |
|---|---|---|---|
| Shared analysis library (E, σ_y, UTS, ε_f, toughness, anchor, fracture detector) | `utm_analysis.py` | ✅ | Reproduces V5/V6 deck numbers (UTS 46.2 / E 2.60 etc.) |
| Closed-loop control engine (Force/Strain-rate/Cyclic/Staircase/Relaxation/Creep policies + sim) | `control_policies.py`, `control_sim.py` | 🟢 | 9/9 sim checks pass |
| Recipes / settings (save + reload test setups, always-present Default) | `utm_recipes.py` | ✅ | Round-trip verified on the rig |
| Test registry (one queryable index of every test + anchor) | `utm_registry.py`, `registry.json` | ✅ | Seeded 8.6.20 tests; S16 added |
| One-click per-specimen report (PDF + PNGs) | `utm_report.py` | ✅ | Every KPI verified vs CSV (S16) |
| Live-DIC helpers (health + multi-marker geometry) | `utm_dic.py` | 🟢 | Self-tested (ν=0.35 recovered) |

### App features (in `main.py`, snapshot `a3b187f`) — all rig-validated
- **DIC health HUD** — OK/WARN/BAD badge (markers · tracking % · jitter) on both test tabs.
- **Prepare specimen** — one-button tare (position + force + DIC), clears consoles + stress-strain plot; DIC tares only at green 2/2.
- **Settings** — Load / Save… + always-present **Default** (auto-stop ON), infill label.
- **Generate report** — one button → PDF + PNGs.
- **Release preload** — controlled return to ~0 N.
- **Fracture test** button — checklist → arm auto-stop → tension pull → auto-stop at fracture.
- **Auto-stop at fracture** — live load-collapse detector on a manual pull.
- **Strain-rate fracture test** — closed-loop constant *gauge* strain rate → fracture → auto-stop.
- **Safety net (3 layers):** load-collapse fracture detector · **stall guard** (crosshead frozen <0.05 mm/6 s under load — in BOTH the auto-stop path and the strain-rate loop) · **10 kN / 30 mm** force/travel backstop · **dead-DIC guard** (freeze speed at 0.2 s, halt at 1.0 s).
- **CSV richness** — `DIC_Blobs` health column + `# DIC Health` header + infill label.

### Rig-validation highlights (2026-07-28/29)
- **S16** — first successful 100 % infill fracture: UTS 47.4 MPa (anchor-corrected), auto-stop caught it, stall guard correctly silent through the ductile draw.
- **#6.1** — dead-DIC guard fires on marker loss; staged freeze/halt tuned (T2/T3: overshoot 518 → 175 N).
- **#6.2** — strain-rate to fracture on a 50 % specimen: **held 0.00051 /s vs 0.0005 target** while the crosshead **auto-adapted 0.10 → 0.05 mm/s** (fast in stiff elastic, slow in necking) = true constant-strain-rate control; fractured (UTS 17.3 MPa nominal), auto-stopped on load collapse.
- **3 rig facts resolved:** Stop holds position · direct reversal auto-decels ~1 s · travel cap 30 mm.

---

## 2. Partial / in progress
- 🟡 **Closed-loop test modes (Phase B):** strain-rate ✅ done & validated. The other four — **cyclic, staircase, relaxation, creep** — are engine-ready (`control_policies.py`, sim-validated) but **not yet wired into the app**. The rig facts that gated them are now confirmed → **unblocked to wire next.**
- 🟡 **Multi-marker Poisson / true Cauchy:** math ready in `utm_dic.py`; needs a 4-marker specimen preset + camera wiring. Also limited by the current mini-dogbone (narrow gauge, sub-pixel transverse change) → see §4.

---

## 3. Remaining / planned  (checklist)
- ⬜ **Wire the 4 remaining control modes** (cyclic / staircase / relaxation / creep) into the Motor-Control UI + recipes.
- ⬜ **Multi-marker Poisson** — 4-marker preset in the dropdown, `detect_blobs`/`tare_dic`/`calculate_dic_strain` for 4 markers, new CSV columns (lateral strain / ν / current area / Cauchy), live ν readout. Needs a matte-black backdrop and/or a gauge-zoomed camera.
- ⬜ **Phase D — UX layer:** guided Connect→Calibrate→Mount→Prepare→Recipe→Run→Save wizard; live analysis overlay (live E / predicted UTS / fracture flag); glanceable dashboard + audio cue on fracture; event-annotation hotkey.
- ⬜ **DIC auto-calibrate (Phase C remainder):** auto-exposure/threshold sweep on Start Camera; auto-follow ROI (shift offset to keep markers centred through ductile draw).
- ⬜ **Auto-metadata + foldering** and **one-click per-specimen deck** (extract pptx builders → `utm_slides.py`).
- ⬜ **Deferred script migration:** `v6a_plots.py` / `v6a_analyze.py` → shared `utm_analysis` (when it grows a live-plotting return).

---

## 4. Hardware constraints (not software — track separately)
- 🔴 **Motor torque ceiling ~2.6 kN (variable).** At the SAME crosshead speed the rig has stalled at 2.6 kN (S15, and today) yet reached 3.2–3.8 kN on other days (V6, S16). **Blocks 100 % full-area fracture** (needs ~3.7 kN). It is a torque-capacity issue, **not** speed or the strain-rate mode. Suspects, in order: stepper **driver current (Vref)**, **driver thermal derating**, **PSU voltage sag under load**, mechanical binding. Workaround: **smaller-cross-section / 50 % specimens** so fracture force < 2.6 kN. See `TEST_FAILURES.md` (S15) and memory `project_motor_stall_limit`.
- ⚠️ **Multi-marker transverse Poisson** infeasible on the current mini-dogbone (gauge too narrow for a transverse pair; elastic width change sub-pixel at ~20 px/mm). Needs a gauge-zoomed camera + dark backdrop, or a dedicated extensometer.

---

## 5. Key files
- **App:** `main.py` (control loop, live hook `on_load_cell_data`, CSV export, UI).
- **Engine/analysis:** `utm_analysis.py`, `control_policies.py`, `control_sim.py`, `utm_dic.py`.
- **Workflow/data:** `utm_recipes.py` + `recipes/`, `utm_registry.py` + `registry.json`, `utm_report.py`.
- **Records:** `TESTING_TODO.md` (test checklist), `TEST_FAILURES.md` (S15 stall), this file.
