# Pratifalan — challenge readiness, code review, and visual improvement plan

Reviewed on **5 October 2026**. This is an assessment and implementation plan; application code has not been changed.

**Recommendation:** build the submission around one memorable story: **“See two possible glucose futures, understand the uncertainty, and watch the twin update when a new measurement arrives.”** The existing model, Indian meal workflow, multilingual interface, and uncertainty visualization give you a useful foundation. The highest-value work now is to fix the evidence and workflow gaps below, then bring those capabilities together into one polished experience. Extra features alone cannot guarantee a competition result.

## 1. Match the actual competition

The [official challenge listing](https://unstop.com/hackathons/crp-digital-twin-challenge-2026-happiest-health-1757873/amp), checked on the review date, asks for historical/EHR and dynamic sensor data fusion, a specific adverse-event prediction, and a conceptual clinician dashboard. Open, anonymized, or synthetic data are required.

Submission requirements from that listing:

- Public GitHub repository, using the requested `Team Name_College Name` folder naming.
- README containing team/college information, title, problem/use case, stack/model details, and license information.
- **At least 20 minutes of explanatory/demo video.**
- Architecture diagram and project presentation in PDF/PPT format.
- Registration deadline: **18 October, 19:00 IST / 13:30 UTC**.
- Prototype/code deadline: **20 October, 19:00 IST / 13:30 UTC**.

The listing has inconsistent shortlist counts and an implausibly short jury time slot. Verify those details with the organizer. The priorities below are my assessment, not a published judging rubric.

**Local submission gap:** no project-root `README.md`, architecture PDF/PPT, presentation PDF/PPT, or video link was found in `Codes`. `scripts/build_readme.py` prints tables when the README is absent; it does not create the missing submission narrative. This workspace also has no Git metadata, so repository publication and tracked-file status could not be verified.

## 2. What was checked

| Check | Result |
|---|---|
| Backend `pytest` | **436 passed, 1 expected failure**, one dependency deprecation warning |
| Backend Ruff | Passed |
| Backend mypy | Passed: 40 source files |
| Frontend Vitest | **509 passed**, across six test files |
| Frontend ESLint | Passed |
| Frontend TypeScript + Vite production build | Passed |
| Browser inspection | Desktop twin and what-if screens at 1440 px; twin screen at 390 px; actual backend reported `demo` mode |
| Mobile horizontal overflow | None detected on the inspected twin screen |
| Targeted API probes | Separate in-memory database; reproduced safety, lab isolation, ignored timestamp, and explanation-scoping issues |
| Evaluation inspection | Reviewed scripts and existing reports; demonstrated outer-fold overlap in prior training membership |

Full model retraining, clean-container deployment, live paid LLM/speech calls, and a clinical validation study were not run. The frontend test count is dominated by translation-key checks: 475 of 509 assertions come from one translation-key test file. Passing these checks does not establish end-to-end clinical workflow correctness.

Strengths to preserve: explicit synthetic-persona labeling, deterministic numerical tools, patient-grouped outer folds, baseline/transfer reports, an honest next-best-prick null result, food-table-based nutrition, existing reduced-motion support, and separate physiology/learned explanations.

## 3. Fix these before the final demo

P0 = resolve before public submission/demo claims; P1 = important for a convincing and reliable prototype; P2 = follow-on improvement. Some fixes concern existing features; they do not require expanding into a production medical product.

### P0 — Manual measurements bypass safety and are prefilled with a prediction

**Evidence:** `backend/pratifalan/api/main.py:315`, `frontend/src/components/AddReadingSheet.tsx`, and `frontend/src/pages/TwinStage.tsx:73`.

Submitting a measured glucose value of `45` to `/assimilate` returned HTTP 200 and an updated state without an explicit safety/emergency result. Chat has a separate safety assessment, but the manual entry flow only updates the chart and displays a success/uncertainty toast. The reading sheet also starts with the twin's estimated glucose as its suggested value, allowing a prediction to be submitted back as if it were a measurement.

**Fix:** start measurement entry empty; require an actual measurement and explicit unit. Run the same clinician-reviewed safety policy for manual entry, chat, and future imports. Return a structured safety result and give it priority over celebratory success UI. Store an extreme observation when appropriate without implying the model update itself resolves the situation.

**Acceptance:** identical observations trigger consistent safety states across entry paths and all four languages; no forecast value is automatically entered as measured data.

### P0 — Lab data and forecast explanations lack adequate ownership checks

**Evidence:** `backend/pratifalan/db.py:63`, `backend/pratifalan/api/main.py:566`, `:585`, `:331`.

`FhirResource` has no user/tenant ownership field. A lab uploaded as user A was returned by the FHIR bundle endpoint as user B for the same persona in the isolated probe. Explanation lookup only uses a forecast ID: a Haripada forecast could be requested through `/api/twin/ramesh/explain/{id}` and returned HTTP 200. Authentication exists, but these object-level checks do not.

**Fix:** define the intended shared-care permissions; for the current demo, scope uploaded labs to the signed-in user, matching `TwinEvent`. Bind forecast references to the authorized user and persona. Enforce clinician permissions on clinician endpoints if separate roles are offered.

**Acceptance:** another user cannot retrieve an upload without explicit access, and a mismatched persona/forecast pair returns 403/404. Include both successful authorized sharing and rejected access in tests.

### P0 — The outer evaluation boundary is incomplete across the two-stage pipeline

**Evidence:** `backend/pratifalan/eval/stage1.py:105`, `backend/pratifalan/eval/experiments.py:133`, and `backend/pratifalan/twin/prior.py`.

Stage 1 excludes each participant's own fold when fitting that participant's prior. However, those globally cached Stage-1 runs are then reused to train the hybrid model in each outer fold. A training row from fold 1 can have a prior trained using fold 0, even when fold 0 is the hybrid model's test set. The prior's target parameters are fitted from participants' glucose records. A membership probe for outer fold 0 found **all 10 outer-test participants** included in the prior-training membership of an example hybrid-training row.

This is an indirect test-data path through feature construction. It does not prove a particular amount of score inflation, but the current results should not be described as fully isolated end-to-end validation.

**Fix:** split people before fitting any learned stage. Within each outer training set, generate inner-fold features using only that outer training set; build outer-test features from a prior fitted solely on outer-training participants. Keep the test person's permitted initial calibration window separate from population-model training. Regenerate affected comparisons and confidence intervals.

**Acceptance:** record participant membership for every fitted prior, residual model, classifier, and calibrator. Assert that no outer-test participant enters any training dependency. Report score changes after correcting the protocol.

### P0 — Client-controlled sample IDs can escape fixture directories

**Evidence:** `backend/pratifalan/perception/lab.py:94–106` and `backend/pratifalan/perception/meal.py:146–161`.

Both parsers construct a filesystem path directly from `sample_id`. Paths are not restricted to the sample manifest. In live mode, a successful parse also writes to that path. A crafted relative or absolute ID can therefore target another JSON path writable by the API process. Even valid sample IDs allow an arbitrary uploaded image to overwrite shared sample fixtures. This is a code-path finding; no exploit or paid provider call was executed.

**Fix:** accept only manifest IDs; resolve/check paths beneath the fixture root. Keep packaged fixtures read-only. Save live results under server-generated, user-scoped IDs in a separate runtime directory.

**Acceptance:** unknown IDs, traversal, and absolute paths are rejected; uploading an image cannot alter a packaged sample.

### P1 — Imported EHR data does not update the personalized twin

**Evidence:** `backend/pratifalan/api/main.py:566` stores FHIR resources; `_detail()` and the engine still use original covariates/base states.

After confirming HbA1c `12.3` for Haripada in an isolated probe, the patient endpoint still returned `7.2`. The upload/export feature works as storage, but there is no versioned path from a confirmed lab to model inputs. Existing EHR-conditioned priors do demonstrate historical-data fusion; the gap is specifically newly imported information.

**Fix:** create a confirmed, timestamped patient covariate revision; identify which fields the model actually uses; apply it through a supported personalization/recalibration path; invalidate dependent results. Show the revision used by every forecast. If updating is outside scope, explicitly label lab upload as export/storage only.

**Acceptance:** an approved change to a model-supported field appears in the input provenance and triggers recomputation. Do not force a particular direction or magnitude of glucose change just to make a demo impressive.

### P1 — The clinician dashboard mixes hidden reference data with operational estimates

**Evidence:** `backend/pratifalan/twin/engine.py:794`, `:808`; `backend/pratifalan/api/main.py:602`; `frontend/src/i18n/locales/en-IN.json` doctor labels.

The seven-day summaries and daily profile read the reference `tl.cgm`, including glucose hidden from the sparse twin. The clinician UI calls historical time above range “7-day risk,” which sounds like a future-risk prediction. The brief also calls `forecast(..., [], ...)`, ignoring the user's added events, and always includes a walking discussion point with a claimed what-if benefit without computing that scenario there.

**Fix:** label historical reference statistics explicitly. Keep reference-CGM reveal as an evaluation feature. Build operational summaries from available measurements/estimates with provenance, label TAR as historical TAR, and use the user's actual event state for the brief. Generate scenario-specific discussion points only from a corresponding tool result.

**Acceptance:** add a reading, then open the doctor brief: patient state and provenance agree. Removing hidden reference CGM must not break the operational dashboard. Historical summaries and future probabilities use distinct labels.

### P1 — Event time is discarded; the displayed twin is a fixed replay

**Evidence:** `AssimilateIn.at` in `api/main.py` is unused; `twin/engine.py:177` shifts a replay to today's date, and `:260` applies readings at a fixed `now_idx`.

A reading submitted with `at = 2020-01-01T08:00:00Z` was returned as a current replay observation at `2026-10-05T19:30`. Added meals also accumulate around the same replay origin. This is acceptable only when explicitly presented as a controlled simulation.

**Fix:** provide a visible simulation clock with play/pause/scrub. Store `observed_at`, `received_at`, source, units, and an idempotency key. Handle late, duplicate, and out-of-order events. Use timezone-aware timestamps. For the submission, deterministic timestamped replay is sufficient; simulated/open sensor streams are allowed.

**Acceptance:** the same timestamped input sequence produces the same state; an old observation cannot silently become a fresh reading; replay time is visibly distinct from wall-clock time.

### P1 — Uncertainty claims need correction before becoming the visual centerpiece

**Evidence:** `twin/engine.py:399`, `:642–654`, `:895`; `backend/tests/test_api.py:130`.

- Risk intervals use a binomial formula around a calibrated classifier probability with the number of simulated particles as sample size, plus an arbitrary inflation factor. This does not estimate the classifier's clinical uncertainty.
- An existing expected-failure test records a case where a reading equal to the estimate widens the current band. A band can legitimately widen after surprising evidence, but this behavior needs explanation rather than a promise that every measurement tightens it.
- Negative narrowing is clipped to zero. Current-band endpoints and the headline two-hour forecast narrowing refer to different quantities, which can confuse the animation and toast.
- The app presents four-hour trajectories, while learned corrections/calibration are evaluated at 30–120 minutes; the correction is held beyond 120 minutes.

**Fix:** distinguish empirical forecast intervals, simulation variability, and uncertainty about event probabilities. Estimate model uncertainty from appropriately grouped held-out/resampled fits or omit unsupported risk intervals. Return signed width changes with the time horizon named. Mark 120–240 minutes as exploratory or evaluate those horizons separately.

**Acceptance:** increasing the particle count alone cannot make a patient-risk confidence interval look more certain; the displayed before/after numbers match the animated band; widening is shown honestly.

### P1 — Number matching does not establish clinical or semantic grounding

**Evidence:** `backend/pratifalan/agent/verifier.py:verify`, `agent/safety.py:output_unsafe`, and `reports/agent_suite.json`.

The verifier accepted “Your low glucose risk is 80%” when the tool outputs contained high risk `0.8` and low risk `0.01`. It checks whether numbers appear somewhere in the allowed set, not whether the metric, unit, horizon, patient, or direction is correct. A separate adversarial detector probe containing a medication-dose instruction also passed the output safety regex. This demonstrates detector gaps, not that a live model necessarily emits that instruction.

The stored agent report itself gives template emergency recall as **0.85**, despite 100% numeric-grounding-or-fallback. Do not advertise that grounding figure as 100% safe medical answers.

**Fix:** generate structured claims referencing specific tool fields; render sensitive claims deterministically in each language. Check semantic bindings and use a constrained policy for medication content. Add independent human-reviewed adversarial cases, including transliteration, negation, unit confusion, and swapped high/low risks. Rerun reports after changes.

**Acceptance:** the swapped-risk example fails; an independent safety suite is not judged solely by the same regex used in production; known emergency misses are resolved or clearly disclosed.

### P1 — CI's database configuration is overridden by the tests

**Evidence:** `.github/workflows/ci.yml:39` versus `backend/tests/conftest.py:12–16`.

CI configures a `pratifalan` PostgreSQL user through `DATABASE_URL`, but `conftest.py` ignores that value and replaces it with its different default unless `PRATIFALAN_TEST_DATABASE_URL` is provided. Local tests passed because the local test database matched the fallback. That does not establish that the workflow works on a clean runner.

**Fix:** set `PRATIFALAN_TEST_DATABASE_URL` in CI to the provisioned database, or consolidate test configuration safely. Preserve the guard against resetting a non-test database. Check README presence/results freshness rather than only printing generated tables.

**Acceptance:** backend tests and artifact checks pass on a clean GitHub runner with only the declared PostgreSQL service.

### P1 — Lab export changes provenance and units without deterministic validation

**Evidence:** `backend/pratifalan/perception/lab.py:to_fields` and `:to_fhir`.

The prompt asks the LLM to convert units, but the code then supplies canonical units without checking or converting the returned values itself. Confirmation accepts a `unit`, while FHIR export uses the field's canonical unit regardless. Collection date is extracted but export uses the current time. HbA1c above a threshold creates an unconfirmed Type 2 diabetes Condition and a note claiming it came from an existing diagnosis, although that diagnosis was not extracted as evidence.

**Fix:** validate and convert units deterministically; retain original values/units and observation dates; record user confirmation separately from collection time. Export only supported diagnoses with their actual source. An abnormal measurement alone must not manufacture diagnosis provenance.

**Acceptance:** equivalent inputs in supported units export equivalent quantities; observation date survives; a lab-only upload does not acquire an invented diagnosis-source note.

## 4. Evidence and reliability improvements

| Area | Current evidence | Recommended action |
|---|---|---|
| Added value of the twin | At two pricks/day, stored 60-minute RMSE is **30.72** versus **31.00** for sparse-feature LightGBM and **33.25** for personal average | After fixing validation, compute paired person-level intervals. Quantify whether physiology adds predictive value; explain simulation utility separately. |
| Sensor-light benefit | Two-prick RMSE **30.72** versus no-maintenance-glucose **31.40**; both follow initial CGM calibration | Lead with the measured tradeoff, including initial calibration burden. Replace “needs no sensor” and “calibrate once, twin forever” with a supported description. |
| Uncertainty | Two-prick 60-minute coverage **90.51%**, average width **116.62 mg/dL** | Show width beside coverage; a broad interval can cover well while offering limited decision precision. |
| Population transfer | CGMacros-trained model on Shanghai real-prick data: RMSE **47.76**, versus **37.49** for Shanghai in-domain | Show domain shift prominently. Avoid suggesting Indian food support establishes Indian clinical validation. |
| Sampling advice | Next-best-prick paired confidence intervals cross zero | Keep it as an experimental information-gathering suggestion. Do not promise improved accuracy or fewer complications. |
| Voice | Stored 12-trip synthetic-speech benchmark: median response audio latency **10.46 s**, intent preserved **66.67%** | Show/edit the transcript before consequential actions, separate STT/tool/TTS status, bound fallbacks, and test real speakers. Stream only verified speech segments. |
| Food photos | Report acknowledges the large photo experiment uses a different nutrition-estimation path; app pipeline checked on four Indian samples | Build a small, independently annotated Indian dish/portion test set using the actual app pipeline. Treat photo parsing as an editable estimate. |
| Repeat recordings | Outer folds group by person, but hybrid inner folds use `pid`; some reports/bootstrap routines also count recordings | Carry stable person IDs through inner fitting and resampling; distinguish people, recordings, and forecast windows. |
| Reproducibility | Cache keys omit source-code/data fingerprints; Python dependencies use lower bounds | Add code/data/config/model manifests, pinned dependencies, and cache versioning. Ship one command that checks artifact compatibility. |
| Live deployment | Non-root Docker user owns `artifacts`/`fixtures`, while live TTS writes under `data/cache/tts` | Provision an explicit writable TTS volume/directory and test its permissions. Add readiness checks for DB/model warm-up, request limits, and bounded upload reads. |

Numbers above come from the existing `backend/reports/{summary,baselines,sensor_ladder,transfer,nbp_value,voice_roundtrip,meal_photo}.json` files. They were inspected, not independently reproduced, and evaluation numbers remain provisional until the pipeline boundary issue is addressed.

## 5. Make the UI visually striking

The current UI already has a coherent identity: indigo stage, marigold forecast, warm paper cards, large numbers, and a distinctive glucose river. Keep that identity. The main opportunity is **composition and interaction**, not adding more gradients.

### What the browser review showed

- On desktop, patient chips, freshness, and the sensor ladder occupy much of the first screen. The current number dominates, while the forecast risk and useful next action appear much lower down.
- On mobile, users must pass the persona selection and sensor controls before reaching the main graph. Risk and uncertainty actions are several scrolls down.
- The what-if controls form a tall left column, while the chart/result occupy only its upper right. Much of the lower right is empty, and controls can move away from the result being edited.
- The unvalidated low-risk percentage gets visual prominence comparable to the better-supported high-risk estimate.
- The palette and spacing are already strong. Preserve the readable warm-paper surfaces for detailed clinician content and exports.

### Proposed signature screen: “Tonight, with your twin”

Make the first screen answer four questions in order: **Who is this? What might happen? What can I explore? How much should I trust it?**

```text
PRATIFALAN                       Patient | Clinician | Evidence
Haripada · synthetic persona      Simulation: day 7, 19:30  ▶

TONIGHT, WITH YOUR TWIN
Current estimate + range          Next 2 h: high-glucose risk
Last measured reading + age       Evidence / uncertainty status

┌──────────────────────────────────────┬──────────────────────┐
│                                      │ YOUR DINNER          │
│      TWO POSSIBLE FUTURES             │ dish + portion       │
│      Same past, branching curves     │                      │
│      with uncertainty bands          │ Explore a change     │
│                                      │ [Portion] [Walk]     │
│      meal / reading event markers    │                      │
├──────────────────────────────────────┴──────────────────────┤
│ Simulated difference · interval · assumptions · Why?        │
└─────────────────────────────────────────────────────────────┘
Next useful measurement          Measurement → updated forecast
```

This is a layout proposal, not a screenshot or new implementation. Populate every metric from the backend; do not use invented “better future” values.

### Concrete design specification

| Element | Direction |
|---|---|
| Desktop layout | Approximately 8/4 chart-to-action split; compact patient context; graph, risk, and next action visible at 1366×768 without scrolling |
| Mobile layout | One patient selector; risk/uncertainty summary; chart; one primary action. Put sensor-ladder controls in an expandable experiment panel. |
| Color | Retain `#0E1230`, `#FAF6EF`, and `#F2A33A`. Give observed history, baseline forecast, and scenario stable meanings; use line styles and labels as well as color. |
| Typography | Reuse the existing UI/Indic families and tabular numbers. Keep large display type for one main result; increase small chart labels for projection. Bundle licensed font files for offline use. |
| Chart | Label curves directly; show units and horizon; pin the selected timestamp; add clear meal/measurement markers and keyboard-accessible equivalents. |
| Motion | Animate a meaningful state transition over roughly 250–450 ms. Retain the previous curve as a ghost while the new result arrives. Animate uncertainty according to the returned values. |
| What-if layout | Sticky chart/result beside grouped controls on desktop; compact result stays visible while editing on mobile; compare at most three scenarios. |
| Low-risk output | Replace the large unvalidated percentage with a concise evidence-status panel; reserve urgent UI for the shared safety policy. |
| Trust | Distinguish “measured,” “estimated,” “simulated scenario,” and “not validated” beside the relevant number. Explain these in everyday language. |
| Accessibility | Keep reduced-motion behavior, visible focus, text alternatives, adequate contrast, and large touch targets. Test Indic scripts and 200% text zoom. |
| Presentation mode | Large labels, clean fullscreen composition, visible replay/fixture status, and a deterministic reset. Keep all evidence caveats accessible. |

Primary implementation files: `frontend/src/pages/TwinStage.tsx`, `pages/WhatIf.tsx`, `charts/GlucoseRiver.tsx`, `charts/CompareChart.tsx`, `components/twin.tsx`, `components/AppShell.tsx`, and `index.css`.

## 6. Standout features ranked by value

Effort estimates assume an engineer familiar with this code, exclude clinical research, and overlap with the fixes above. Build the first two well before adding more scope.

| Rank | Feature | What judges can see | Smallest useful implementation | Effort |
|---|---|---|---|---|
| 1 | **Two Possible Futures** | One patient's forecast branches as a confirmed dinner portion or walk scenario changes; both uncertainty bands remain visible | Integrate existing meal, what-if, and river components; pin the baseline; show signed peak/risk differences and assumptions | 2–3 days |
| 2 | **Watch the Twin Learn** | Pause replay, make a forecast, reveal the next recorded measurement, assimilate it, and compare the revised forecast | Timestamped replay controls, fixed forecast origin, before/after state, and separately marked reference reveal | 2–4 days |
| 3 | **Evidence Receipt** | Every important claim opens the measurement/lab revision, tool result, model version, horizon, and validation status behind it | Extend the existing Why drawer with structured provenance and a downloadable receipt | 1–2 days |
| 4 | **Clinician Review Queue** | A doctor can distinguish missing data, a concerning observation, and a model risk signal, then record a review action | Correct dashboard data sources; add reason, freshness, uncertainty, and an in-app reviewed/note state | 2–3 days |
| 5 | **Missing-Sensor Challenge** | Pause/remove simulated readings and show what changes in accuracy, uncertainty, and abstention | Extend the current sensor ladder with replay comparison and recorded error on the same timeline | 1–2 days after replay |
| 6 | **Regional Dinner Explorer** | A household portion can be corrected visually and compared with culturally familiar alternatives | Reuse curated swaps; add photo-backed portion references, editable quantities, and source labels | 1–2 days for UI; evaluation extra |
| 7 | **Speak → Confirm → Act** | A regional-language voice request becomes editable text and visible structured meal/reading fields before changing state | Confirmation for mutations, clear progress states, cancellable processing, safe fallback | 1–2 days plus speaker testing |

For **Two Possible Futures**, label the output as a model simulation. Existing paired particles make the interaction feasible, but observational forecasting does not prove that the simulated intervention causes the predicted benefit. Do not automatically select “the healthiest plan” without validating that additional claim.

For **Watch the Twin Learn**, use a declared evaluation participant excluded from the population-model fit if presenting it as unseen-person performance. Current demo artifacts use a production hybrid trained on all CGMacros participants, including the source population behind the personas. A demonstration of mechanics and a held-out performance demonstration need different labeling.

The most memorable combined sequence is: **dinner → two simulated futures → new measurement → updated uncertainty → clinician evidence receipt**. It communicates personalization, prediction, updating, and clinical usability in a single story.

Defer a decorative 3D human body, more disease models, an autonomous treatment optimizer, WhatsApp integration, blockchain, and new vendor integrations. None addresses the immediate evidence gaps, and each competes with time needed for the required submission assets.

## 7. Delivery plan through submission

| Dates (2026) | Deliverable | Exit condition |
|---|---|---|
| Oct 5–7 | Safety parity, ownership checks, fixture-path protection, CI fix; create submission README | Targeted regressions pass; no false claim that tests guarantee safety |
| Oct 7–10 | Correct evaluation dependencies; rerun core baselines; repair clinician provenance and timestamp semantics | Auditable folds; updated results with limitations; operational and reference data separated |
| Oct 10–13 | Two Possible Futures plus a controlled replay/measurement-update sequence | One complete, deterministic story works with real backend results |
| Oct 13–15 | Responsive visual refinement and Evidence Receipt | Desktop presentation and phone flows tested; no unvalidated output given misleading prominence |
| Oct 15–17 | Architecture PDF, presentation, README, and at least 20-minute video | Submission links and artifacts reviewed; video readable/audible and clearly labeled |
| Oct 18–19 | Clean-clone/container rehearsal; check registration; final artifact/link audit | Offline demo works from documented setup; no missing model/data assets or secrets in publication |
| Oct 20 | Submission buffer | Submit ahead of the listed cutoff; retain a release copy |

If time is short, prioritize the P0 fixes, a defensible core evaluation, the submission assets, and **one** excellent combined futures/measurement demonstration. Ship a smaller coherent experience rather than several unfinished screens.

## 8. Demo narrative and claim discipline

Suggested **22-minute recording**:

1. **0–2 min:** the Indian diabetes use case, intended user, and exact prediction target.
2. **2–5 min:** architecture and provenance: historical covariates, sensor stream, personalization, and validation split.
3. **5–10 min:** dinner input and Two Possible Futures, showing uncertainty and simulation assumptions.
4. **10–13 min:** a new measured observation updates the twin; show a case where evidence is insufficient.
5. **13–16 min:** clinician workflow and the evidence behind a selected result.
6. **16–20 min:** corrected baselines, calibration/width, transfer limits, safety evaluation, and India-specific validation still needed.
7. **20–22 min:** reproducible setup, intended pilot design, and the team's contributions.

Showcase language: **“A sensor-light glucose twin with Indian meal inputs, multilingual interaction, and visible uncertainty.”** State that initial CGM calibration is part of the tested setup. Keep the next-two-hour high-glucose outcome central. Present long-term outlook, low-glucose probability, and intervention comparisons with their existing limitations; do not frame them as proven clinical outcomes.

For final confidence, rehearse login → persona → meal confirmation → scenario → measurement → doctor brief → evidence export. Cover backend unavailable, speech unavailable, stale measurements, repeated clicks, a failed upload, and patient switching during an outstanding request. Existing unit tests do not exercise that entire journey.
