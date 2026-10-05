# Build Prompt: Pratibimb — the diabetes twin that needs no sensor and speaks your language

> Hand this whole file to a coding agent (Claude Code, Copilot agent, Cursor, etc.).
> It is a complete build specification. Follow the phases in order and do not skip the acceptance checks.

---

## 0. Instructions to the coding agent

You are building a competition-grade proof of concept for the **Happiest Health Digital Twin Challenge 2026** (India). Read the whole file before writing any code.

Ground rules:

1. **Real numbers only.** Every metric shown in the UI, README or slides must be produced by a script in this repo and written to `reports/`. Never type a metric by hand. If a result is weak, report it as it is.
2. **No LLM ever produces a glucose number.** Predictions come from the twin engine (Section 4). LLMs are used only for perception (photo, speech, lab-report parsing) and explanation.
3. **Verify, do not guess.** Before using any dataset column, provider endpoint or model ID, read the dataset's documentation or the provider's current API docs. If something in this file conflicts with what you find, follow what you find and note it in `docs/DEVIATIONS.md`.
4. **Keys live in `.env` only.** Never commit `.env`. Commit `.env.example`. The app must run fully in **offline demo mode** with no keys at all (Section 9).
5. **Not a medical device.** No insulin or drug dose recommendations anywhere. Decision support only. Show the disclaimer in the UI footer and README.
6. Work in small commits, one phase at a time. After each phase, run its acceptance checks and fix failures before moving on.
7. If a "Stretch" item threatens the "Must" items, drop the stretch item.

---

## 1. The idea in one paragraph

Almost no Type 2 Diabetes (T2D) patient in India wears a continuous glucose monitor (CGM), so CGM-based digital twins do not reach them. **Pratibimb** ("reflection") calibrates a personal glucose twin from **one short CGM wear (up to 14 days)**, then keeps that twin alive using only **two finger-prick readings a day, a smartwatch, and photos of meals**. The patient talks to the twin in **Bengali, Hindi, Kannada or English** and hears the answer spoken back. The twin always shows how sure it is, and tells the patient the single best time to take the next finger-prick.

Target outcome (the "specific, localized health outcome" the challenge asks for): **probability of a post-meal glucose excursion above 180 mg/dL in the next 2 hours, and of a low below 70 mg/dL in the next 2 hours**, for an adult with T2D.

---

## 2. Killer features (priority order)

### Must have

| # | Feature | What the user sees |
|---|---|---|
| M1 | **Calibrate once, twin forever** | A "sensor ladder" switch: Full CGM → 4 pricks/day → 2 pricks/day → no glucose data. The forecast and its uncertainty band redraw live for each level. |
| M2 | **Living uncertainty** | The forecast band widens as hours pass without a reading and snaps narrower the moment a finger-prick is entered. A "Twin freshness" meter shows it. |
| M3 | **Next best prick** | The twin recommends the one time in the next 24 h when a finger-prick would reduce its uncertainty most ("Check at 9:40 pm, it will teach me the most"). |
| M4 | **Thali to forecast** | Photo of an Indian meal → detected dishes and estimated carbs (editable chips) → this patient's predicted curve. |
| M5 | **What-if studio** | Swap rice for roti, halve the portion, add a 15-minute walk, shift dinner earlier. Curves overlay with the change in excursion risk. |
| M6 | **Voice in four languages** | Push-to-talk. Ask in Bengali, Hindi, Kannada or English; hear a short spoken answer in the same language with the matching chart highlighted. |
| M7 | **Grounded explanations** | Every spoken or written number is traced to a twin tool output. A "Why?" drawer shows the drivers of each forecast. |
| M8 | **Trust panel** | Real metrics from `reports/`: accuracy per sensor-ladder level, calibration plot, transfer test, subgroup table, known limitations. |

### Should have

| # | Feature | What the user sees |
|---|---|---|
| S1 | **Lab report to record** | Photo or PDF of a lab report → structured EHR fields (HbA1c, fasting glucose, lipids, eGFR, medications) → stored as FHIR R4 resources. |
| S2 | **Doctor view** | A panel of patients ranked by 7-day risk, each with a one-screen summary and a printable visit brief. |
| S3 | **90-day outlook** | Projected time-in-range and estimated HbA1c trend if current habits continue versus if the top what-if change is adopted. |

### Stretch

| # | Feature |
|---|---|
| X1 | Family mode: a caregiver gets a spoken daily summary. |
| X2 | Festival and fasting mode: the what-if studio handles a long fasting window and flags low-glucose risk. |
| X3 | 3D body visual of the twin (glucose shown as a flow through liver, muscle, blood). Only if everything else is finished. |

---

## 3. Architecture

```
frontend (React + Vite + TypeScript)
   │  REST + WebSocket
backend (FastAPI, Python 3.11)
   ├── twin/          physiology model, particle filter, residual model, conformal, next-best-prick
   ├── perception/    meal photo → carbs, speech ↔ text, lab report → FHIR
   ├── agent/         tool-calling LLM orchestrator + numeric grounding verifier
   ├── providers/     one thin adapter per API provider, all behind interfaces
   ├── data/          dataset loaders, harmonisation, patient-wise splits
   ├── eval/          ablations, baselines, calibration, transfer, subgroup reports
   └── api/           routes, schemas, demo-replay engine
storage: SQLite (app state) + Parquet (time series) + JSON (FHIR bundles)
deploy: docker compose up  →  frontend on :8080, API on :8000
```

Tooling: `uv` for Python, `ruff`, `pytest`, `mypy` on `twin/`; `pnpm`, ESLint, Vitest on the frontend; GitHub Actions CI running both.

---

## 4. The twin engine (the core AI — build this first and best)

A **hybrid, hierarchical, sequentially-updated** model. Three layers.

### 4.1 Mechanistic layer

A compact glucose–insulin model with meal absorption and exercise effect, in ODE form:

- Glucose compartment with endogenous production and insulin-dependent uptake (minimal-model style).
- Remote insulin action state.
- Endogenous insulin secretion responding to glucose (patients with T2D mostly still secrete insulin; do not assume external insulin).
- Two-compartment gut absorption driven by meal carbs, with absorption speed modulated by a meal-composition factor (fat, protein, fibre slow it down).
- Exercise term that raises glucose uptake for a period after activity (driven by steps or heart rate).
- Circadian term on insulin sensitivity (dawn effect).

Personal parameters (per patient): insulin sensitivity, glucose effectiveness, secretion gain, absorption rate, basal glucose, exercise gain, circadian amplitude. Solve with a fixed-step RK4 at 5-minute resolution; keep it vectorised with NumPy so thousands of particles run fast.

### 4.2 Hierarchical Bayesian personalisation

- **Population prior:** fit parameter distributions across training patients, conditioned on EHR covariates (age, sex, BMI, HbA1c, diabetes duration, medication class) with a small regression model that outputs prior mean and variance per parameter.
- **Calibration phase (CGM available):** estimate the personal posterior from the calibration window. Use a particle filter with parameter jitter (Liu–West) or SMC; keep the posterior as a weighted particle set.
- **Maintenance phase (no CGM):** keep running the same particle filter, but observations are now sparse: finger-pricks (with glucometer noise model, roughly ±15%), meal events, steps, heart rate, sleep. Between observations, particles propagate and spread — that spread is the "living uncertainty" (M2).
- A new patient with no CGM at all starts from the EHR-conditioned prior ("Tier 0").

### 4.3 Learned residual and calibration

- **Residual model:** gradient-boosted trees (LightGBM) predicting the mechanistic model's error at 30/60/90/120 min from features: twin state summary, time since last observation, meal features, activity, sleep, time of day. Train patient-wise out-of-fold.
- **Event probabilities:** P(>180 in next 2 h) and P(<70 in next 2 h) from the particle forecast distribution plus residual correction, then calibrated (isotonic).
- **Conformal prediction:** split conformal on held-out patients, stratified by sensor-ladder level and hours-since-last-reading, so stated 90% bands really cover about 90%.
- **Abstain state:** if the input is far from training data (e.g. Mahalanobis distance on feature vector above threshold) or effective particle count collapses, the twin says "I am not sure enough" and asks for a finger-prick.

### 4.4 Next best prick (active sensing, M3)

For each candidate time in the next 24 h (30-minute grid, skipping the user's sleep window), estimate the **expected reduction in forecast variance over the following 12 h** if a reading were taken then (simulate readings from the particle predictive distribution, reweight, measure variance drop). Recommend the top time, plus a plain-language reason. Cache results; it must return in under 2 seconds.

### 4.5 What-if engine (M5)

Counterfactuals are run on the **same particle set** with modified inputs (meal carbs or composition, meal time, added activity). Return paired curves, the change in excursion probability with an interval, and a note when the difference is within uncertainty ("too small to call").

### 4.6 Twin API (the only way anything else gets numbers)

```
get_state(patient_id, at)                    → current estimate, band, freshness, last observation
forecast(patient_id, horizon_min, inputs)    → trajectory quantiles, P(high), P(low), drivers
what_if(patient_id, scenario)                → baseline vs scenario, delta risk with interval
next_best_prick(patient_id)                  → time, expected gain, reason
assimilate(patient_id, observation)          → updated state, before/after band width
outlook_90d(patient_id, scenario?)           → projected TIR and eHbA1c trend (label clearly as projection)
explain(patient_id, forecast_id)             → ranked drivers with signed contributions
```

Drivers for `explain` come from (a) the mechanistic terms' contributions and (b) SHAP on the residual model. Report them separately.

---

## 5. Data and evaluation

### 5.1 Datasets (open; verify licences and schemas yourself)

- **CGMacros** (PhysioNet): about 45 adults including people with T2D and prediabetes; CGM, meals with macronutrients, activity tracker data, and — verify — meal photographs. Primary dataset.
- **ShanghaiT2DM**: about 100 adults with T2D; CGM plus clinical and diet records. Use for the cross-population transfer test.
- Optional extras from the Awesome-CGM list if time allows.

Write `data/download.py` (never commit raw data), `data/harmonise.py` (common 5-minute schema), and `data/README.md` recording source, licence, citation and access date for each dataset.

**No open Indian CGM dataset is known.** State this plainly in the README and Trust panel. Indian meal handling is done through a food composition table (Section 6.1), not by pretending the training data is Indian.

### 5.2 Demo patients

Three clearly labelled **synthetic composite** personas (real open trajectories + invented EHR and names), e.g. a 54-year-old shopkeeper in Kolkata, a 47-year-old teacher in Mysuru, a 61-year-old retiree in Lucknow. Label them "synthetic composite" in the UI.

### 5.3 Experiments (each is a script writing to `reports/`)

1. **Sensor-ladder ablation (headline result).** After calibration on the first N days of CGM, hide the CGM and reveal only k readings per day (k = full, 4, 2, 1, 0), chosen at realistic times (fasting, post-dinner). Report RMSE at 30/60/90/120 min, event AUROC and AUPRC, and interval coverage and width per level.
2. **Calibration-length ablation.** 3, 7, 10, 14 days of CGM.
3. **Baselines.** Persistence, population-average curve, LightGBM on sparse features only (no twin), mechanistic only, full hybrid.
4. **Next-best-prick value.** Same number of readings per day, placed at (a) fixed clinic-style times, (b) random times, (c) twin-recommended times. Report the accuracy difference.
5. **Transfer test.** Train on CGMacros, test on ShanghaiT2DM, and the reverse. Report the gap.
6. **Subgroup audit.** Metrics and calibration by sex, age band, BMI band (use Asian cut-offs 23 and 25), HbA1c band. Flag any subgroup with clearly worse calibration.
7. **Meal-photo carb error.** Vision-estimated carbs vs logged carbs on CGMacros photos (if available), and the effect of that error on forecast RMSE.
8. **Clinical safety view.** Clarke or Parkes error-grid zone percentages for the virtual CGM reconstruction.

Rules: patient-wise splits only (GroupKFold), fixed seeds, bootstrap confidence intervals by patient, a single `make reproduce` target that regenerates every report and figure.

---

## 6. Perception and language layer

### 6.1 Meal photo → carbs (M4)

- Vision LLM returns strict JSON: dishes, estimated portion (grams or household units like katori, roti count), confidence.
- Map dishes to an **Indian food composition table** stored in `data/food/` (build from an open source such as IFCT 2017 values where licensing allows; otherwise a hand-curated table of the 150 most common dishes across Bengali, North Indian and Karnataka cuisine with carbs, fibre, fat, protein per unit, each row citing its source).
- Nutrition numbers come from the table, never from the LLM. Unknown dish → ask the user to pick the closest match.
- UI shows editable chips so the user can correct portions before the forecast runs. Carb uncertainty feeds into the forecast band.

### 6.2 Voice (M6)

- Languages: `bn-IN`, `hi-IN`, `kn-IN`, `en-IN`.
- Speech-to-text and text-to-speech: **Sarvam AI** as the primary provider for all four languages (check current docs for model names, language codes, streaming support and limits). **Fish Audio** as an optional alternate TTS voice. Browser Web Speech API as the no-key fallback.
- Latency target: first audio within 2.5 seconds of the user finishing. Stream TTS if the provider supports it.
- Replies are short (under 40 spoken words), plain, no jargon, numbers spoken naturally in the target language, units said as people say them.
- All UI text is internationalised (`i18next`) in the four languages. Use proper fonts: Noto Sans Bengali, Noto Sans Devanagari, Noto Sans Kannada. Have translations produced by an LLM, then stored as static JSON so they are reviewable; mark machine-translated strings in a file a native speaker can check.

### 6.3 Lab report → EHR (S1)

Vision LLM extracts fields into a Pydantic schema with units and reference ranges; out-of-plausible-range values are flagged for confirmation; confirmed values are stored as FHIR R4 `Observation`, `Condition`, `MedicationStatement` resources. Provide FHIR bundle export.

---

## 7. Agent layer (unique AI implementation)

A tool-calling orchestrator with a strict contract:

1. **Router** (small fast model): classify intent — forecast, what-if, log meal, log reading, explain, general education, out of scope, emergency.
2. **Planner** (strong model): may call only the Twin API tools in Section 4.6 plus `log_meal`, `log_reading`, `lookup_food`. It receives no raw glucose history, only tool outputs.
3. **Numeric grounding verifier** (deterministic code, not an LLM): extract every number from the draft reply; each must match a value in the tool outputs of this turn within rounding. If not, regenerate once, then fall back to a template reply built directly from tool outputs.
4. **Safety filter** (deterministic rules first, LLM second): block dose or medication-change advice; on reported symptoms of severe low or very high glucose, show and speak a fixed emergency message advising immediate medical help; refuse diagnosis.
5. **Localiser:** produce the reply in the user's language. The verifier runs again on the localised text (handle Bengali, Devanagari and Kannada numerals).
6. **Audit trail:** each reply stores the tool calls and outputs it used; the UI's "Why?" drawer shows them.

Provider routing through one `LLMClient` interface with per-role model IDs read from `.env` (router, planner, vision, translator). Support OpenRouter, OpenAI, DeepSeek, Kimi (Moonshot), xAI and NanoGPT adapters with automatic fallback order and timeouts. Do not hardcode model names in code; put sensible current defaults in `.env.example` after checking each provider's model list.

Evaluate the agent too: a `eval/agent_suite.jsonl` of at least 60 prompts across the four languages (in scope, out of scope, unsafe requests, prompt-injection attempts in meal descriptions) with pass criteria; report grounding-pass rate and unsafe-advice rate in `reports/`.

---

## 8. UI and experience (must look exceptional)

Stack: React 18+, TypeScript, Vite, Tailwind, Framer Motion, visx or D3 for the custom charts, Zustand, TanStack Query. Responsive and mobile-first for the patient view; desktop for the doctor view.

### 8.1 Design direction

- **Concept:** "a calm reflection." The patient's twin is a living curve, not a wall of gauges.
- **Palette (define as CSS variables, light and dark):** deep indigo night background `#0E1230` for the twin stage, warm paper `#FAF6EF` for reading surfaces, a marigold accent `#F2A33A` for the twin itself, teal `#2BB3A3` for in-range, coral `#E5604D` for high, violet `#7C6CF0` for low. Check WCAG AA contrast for all text.
- **Type:** a humanist sans for UI (e.g. Inter or Plus Jakarta Sans) paired with the Noto families for Indic scripts; large tabular numerals for glucose values.
- **Motion:** purposeful only. The uncertainty band "breathes" slowly; assimilation of a reading is a visible ripple that tightens the band; what-if curves morph instead of jumping. Respect `prefers-reduced-motion`.
- Avoid generic admin-dashboard looks, emoji as icons, and gradient-on-everything. Use one icon set (Lucide or Phosphor).

### 8.2 Screens

1. **Twin stage (home).** Full-width "glucose river": past readings as dots, the virtual-CGM reconstruction as a line, the next 2–4 h forecast as a marigold curve inside a soft band, target range as a shaded lane. Top-right: freshness meter and sensor-ladder switch. Bottom: three large actions — *Speak*, *Snap a meal*, *Add a reading*.
2. **Assimilation moment.** Entering a finger-prick plays the ripple, shows "band narrowed by X%" (real value from `assimilate`), and updates the next-best-prick card.
3. **Meal flow.** Camera → dish chips with portions → forecast overlay → one-tap suggestions that open the what-if studio.
4. **What-if studio.** Left: scenario controls as tactile cards (swap, portion, walk, timing). Right: baseline vs scenario curves, risk delta with interval, "too small to call" state.
5. **Voice conversation.** Push-to-talk orb with live waveform, live transcript in native script, spoken answer, and the relevant chart region highlighted in sync.
6. **Why? drawer.** Ranked drivers ("dinner carbs", "no walk today", "short sleep"), split into physiology-model and learned-correction contributions, plus the tool calls behind the answer.
7. **Trust panel.** Sensor-ladder accuracy chart, calibration curve, transfer and subgroup tables, limitations in plain words, data sources and licences. All read from `reports/*.json`.
8. **Doctor view (S2).** Patient list ranked by risk, sparkline per patient, visit brief with print stylesheet.
9. **Guided demo mode.** A 5-step scripted tour with a persona, used for the video and the jury. One click resets it.

### 8.3 Explanatory by default

Every chart has a one-sentence caption in the user's language. Every probability is also shown as a frequency ("about 7 times out of 10"). First-run onboarding explains the twin in four short cards. Tooltips define terms such as "time in range".

---

## 9. Configuration, keys and offline mode

`.env.example` (create it; real values go in the untracked `.env`):

```
# LLM providers (any subset works; fallback order is configurable)
OPENROUTER_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
KIMI_API_KEY=
XAI_API_KEY=
NANOGPT_API_KEY=

# Speech
SARVAM_API_KEY=
FISH_AUDIO_API_KEY=

# Media (optional, for demo-video visuals only; not used at runtime)
FAL_KEY=
BYTEDANCE_API_KEY=

# Model routing (fill defaults after checking provider model lists)
LLM_ROUTER_MODEL=
LLM_PLANNER_MODEL=
LLM_VISION_MODEL=
LLM_TRANSLATOR_MODEL=
LLM_PROVIDER_ORDER=openrouter,openai,deepseek,kimi,xai,nanogpt

# App
APP_MODE=demo            # demo | live
DEFAULT_LANGUAGE=en-IN
```

- Load with `pydantic-settings`; fail with a clear message naming the missing key only when a live feature is actually used.
- **Offline demo mode (`APP_MODE=demo`):** all LLM, vision and speech calls are served from recorded fixtures in `fixtures/` (recorded once with live keys via `make record-fixtures`). The twin engine always runs for real. Judges must be able to run `docker compose up` with an empty `.env` and see the full guided demo, including pre-recorded audio in all four languages.
- Add `.env`, raw data and model artefacts above 50 MB to `.gitignore`. Add a pre-commit secret scan (e.g. `gitleaks`).
- Never log request bodies containing audio, images or health values at INFO level.

---

## 10. Submission deliverables (generate these in the repo)

Confirm the exact list on the Unstop page; the items below reflect what other teams' public checklists show.

- `README.md` with: team details, college/incubator, project title, problem statement, healthcare use case, technical stack, AI/ML model details, demo video link placeholder, licence, links to the architecture diagram and presentation, quick start, results tables auto-inserted from `reports/`, limitations, responsible-AI notes (DPDP Act 2023, CDSCO software-as-medical-device awareness, ABDM/FHIR readiness).
- `LICENSE` (MIT).
- `docs/architecture.pdf` and `.pptx` (generate from a script so it stays in sync).
- `docs/presentation.pdf` and `.pptx`, 12 slides: problem, why CGM twins miss India, idea, live demo screenshots, twin engine, sensor-ladder result, next-best-prick result, trust and fairness, voice in four languages, safety and limits, roadmap, ask.
- `docs/VIDEO_SCRIPT.md` for a 15–20 minute demo, timestamped, following the guided demo mode.
- `docs/JURY_QA.md` with prepared answers: Who has a CGM? What if the finger-prick is wrong? Why trust non-Indian training data? What does the LLM do and not do? What is the false-alarm cost? How would this be validated clinically?
- Public repo, no permissions needed, CI badge green.

---

## 11. Build phases and acceptance checks

| Phase | Build | Accept when |
|---|---|---|
| 1 | Repo scaffold, CI, config, data download and harmonisation | `make data` produces harmonised Parquet; schema tests pass |
| 2 | Mechanistic model + particle filter + calibration phase | Unit tests on ODE conservation and filter convergence on simulated patients with known parameters |
| 3 | Sparse maintenance phase, residual model, conformal, abstain | Sensor-ladder ablation runs end to end; 90% bands cover 85–95% on held-out patients |
| 4 | Next-best-prick and what-if engines | Experiment 4 report generated; what-if returns in < 1 s |
| 5 | Twin API + demo-replay engine + personas | All Section 4.6 endpoints documented in OpenAPI and covered by tests |
| 6 | Frontend: twin stage, assimilation, what-if, trust panel | Lighthouse accessibility ≥ 90; works at 380 px width |
| 7 | Providers, agent, grounding verifier, safety filter | Agent suite: 100% grounding pass or template fallback; zero dose advice |
| 8 | Meal photo, voice in four languages, i18n | Round trip (speak → answer audio) works live in all four languages and in demo mode |
| 9 | Lab report → FHIR, doctor view, 90-day outlook | FHIR bundle validates; doctor brief prints on one page |
| 10 | Remaining experiments, README auto-tables, docs, deck, video script | `make reproduce` regenerates all reports; `docker compose up` works with an empty `.env` |
| 11 | Polish pass: motion, empty states, error states, loading skeletons, copy review | Guided demo runs start to finish without a dead end |

If time runs short, cut in this order: X3, X2, X1, S3, S2, S1. Never cut M1–M8, Experiments 1, 3, 4, 5, or offline demo mode.

---

## 12. Definition of done

- A stranger clones the repo, runs `docker compose up` with no keys, and completes the guided demo in any of the four languages.
- With keys in `.env` and `APP_MODE=live`, voice, meal photo and lab-report parsing work against real providers.
- Every number on screen and in the README traces to a file in `reports/` or a Twin API call.
- The README states plainly what was validated on real data, what is synthetic, and what is not yet proven.
