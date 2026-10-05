# Deviations from the build specification

The build specification (`PRATIBIMB_BUILD_PROMPT.md`) says to follow what we find when it
conflicts with the plan, and to record it here. Each entry gives what changed, why, and where
to check it. Results are cited by report file and field rather than copied, because
`make reproduce` regenerates them. The few counts quoted here were checked against the data
and code on 2026-10-05.

## Product and engineering

| # | Spec | What we did | Why | Where |
|---|---|---|---|---|
| 1 | Product name "Pratibimb" | Renamed **Pratifalan** ("Reflect your health issues before they really occur") | Owner request | Whole repo |
| 2 | SQLite for app state | **PostgreSQL 16** (SQLAlchemy + psycopg); `docker compose` ships a `postgres:16-alpine` service | Owner request | `backend/pratifalan/db.py`, `docker-compose.yml` |
| 3 | pnpm for the frontend | **npm** (`package-lock.json`, `npm ci`) | pnpm is not installed on the build server | `frontend/`, `Makefile`, CI |
| 4 | uv for Python | **pip + venv** (`backend/.venv`, `pip install -e backend[dev]`) | uv is not installed on the build server; pip is enough | `Makefile` (`install`), `backend/Dockerfile` |

## Data and evaluation protocol

| # | Spec | What we did | Why | Where |
|---|---|---|---|---|
| 5 | Calibration-length ablation with 3, 7, 10 and 14 days of CGM | **1, 3, 5 and 7 days**, all scored on the same window (day 7 onward). The headline calibration (sensor ladder, demo personas) uses **5 days** | CGMacros records last about 10 days (median about 10.6, minimum about 7.2), so 10 and 14 days cannot be tested and still leave a scoring window | `reports/calibration_length.json` (`protocol`), `pratifalan/twin/personas.py` (`CALIB_DAYS`) |
| 6 | "k finger-pricks a day" | Finger-pricks in the CGMacros experiments are **simulated** from the hidden Dexcom CGM with a 5% relative glucometer error (`PRICK_REL_SD = 0.05`). Only the ShanghaiT2DM transfer arm uses **real** capillary readings (`cbg`) | CGMacros has no finger-prick data | `pratifalan/twin/runner.py`, `reports/transfer.json` |
| 7 | Reference CGM not specified | **Dexcom G6** (`Dexcom GL`) is the reference sensor; the Libre Pro column is not used | Scoring needs one consistent reference sensor. Both columns are near-complete in CGMacros; we chose the factory-calibrated Dexcom G6 and did not compare against the Libre Pro | `pratifalan/data/harmonise.py` |
| 8 | ShanghaiT2DM diet records | Meal carbohydrates are **approximated** by keyword matching of the English diet notes to rounded USDA-like carbohydrate values per 100 g (unknown meals = 50 g) | The dataset has free-text diet notes, not nutrient values | `SH_CARBS_PER_100G` in `pratifalan/data/harmonise.py` |
| 9 | ShanghaiT2DM "about 100 adults" | The T2DM archive holds **109 recordings from 100 patients**; each recording is one `pid`. Reports count recordings as "patients". 56 of 109 recordings (51 of 100 patients, about 51% either way) involve insulin, which the model **does not represent** | Dataset structure | `pratifalan/data/harmonise.py`, `reports/transfer.json` (`shanghai_by_insulin`) |
| 10 | Experiment 7 on CGMacros photos | The meal-photo experiment uses the **US CGMacros photos**. A vision LLM gives a carbohydrate estimate **for this experiment only**; in the app, nutrition always comes from the Indian food table (the LLM only names dishes and portions) | No open Indian meal-photo dataset with logged carbohydrates | `pratifalan/eval/meal_photo.py`, `pratifalan/perception/meal.py` |

## Twin engine

| # | Spec | What we did | Why | Where |
|---|---|---|---|---|
| 11 | Particle filter learns parameters in the calibration phase | **CEM multiple-shooting calibration** in front of the Liu-West particle filter: the cross-entropy method fits the calibration window with the state reset to the CGM every few minutes, and its elite distribution seeds the particle cloud | With dense CGM, the filter re-anchors the state every 5 minutes and the parameters barely affect the likelihood, so PF-only parameter learning drifted. In development, before the fix, sparse (2 pricks/day) reconstruction RMSE was about 49 mg/dL, worse than a personal-mean baseline at about 37 mg/dL. These two values are from the development log and are **not** in `reports/` | `pratifalan/twin/calibrate.py`, `pratifalan/twin/filter.py`; current values in `reports/sensor_ladder.json` (`reconstruction`) and `reports/baselines.json` (`personal_average`) |
| 12 | Event probabilities from the particle cloud | A **stacked LightGBM classifier** on twin features plus the particle probability, then **isotonic calibration** (out-of-fold). The classifier is skipped when events come from too few patients | Raw particle probabilities were poorly calibrated | `pratifalan/twin/hybrid.py`; `reports/calibration_curve.json` (`high_uncalibrated` vs `high`) |
| 13 | P(<70 in 2 h) as a target outcome | Shown in the app but labelled **not validated** | CGMacros participants are mostly not on glucose-lowering drugs: in the scored 2-pricks/day forecast windows, only 83 windows from 9 of 45 participants contain a low (stage-1 cache, 2026-10-05). Too few to train or validate | `reports/sensor_ladder.json` (`low_events`, written by `pratifalan/eval/experiments.py`), `pratifalan/twin/hybrid.py` |
| 14 | Next-best-prick improves accuracy | **Null result reported.** Twin-recommended timing showed no significant gain over fixed clinic times (07:00 and 22:00) or random times: the 95% CIs of the paired differences include zero | That is what the experiment found | `reports/nbp_value.json` (`paired_differences`) |
| 15 | NBP planning uses the filter posterior | Planning adds a persistent **misspecification spread** of 0.12 (GB) and 0.30 (SI) log-sd to the particle cloud | Without it, the filter cloud under-represents slowly varying bias and the planner chases short-lived post-meal variance | `PLAN_EXTRA_LOGSD` in `pratifalan/twin/nbp.py` |
| 16 | Conformal bands per horizon | The "now" band (current glucose estimate) uses the **30-minute** conformal quantile | No separate 0-minute calibration set; the 30-minute quantile is conservative | `pratifalan/twin/engine.py` (conformal now-band) |
| 17 | 90-day outlook | A **GMI-based projection** (GMI % = 3.31 + 0.02392 × mean glucose in mg/dL) from the twin's simulated typical day. Not a validated HbA1c prediction, and labelled so | No dataset in reach follows HbA1c over 90 days | `pratifalan/twin/engine.py` (`outlook_90d`) |

## Agent, language and speech

| # | Spec | What we did | Why | Where |
|---|---|---|---|---|
| 18 | Separate localiser step after the planner | **Localiser merged into the planner**: the planner writes directly in the user's language, and the numeric grounding verifier re-runs on the localised text (Indic numerals normalised) | One fewer LLM call per turn (latency); grounding is still checked on the text the user sees | `pratifalan/agent/orchestrator.py`, `pratifalan/agent/verifier.py` |
| 19 | Sarvam AI for Indic speech | Sarvam adapter (saarika STT, bulbul TTS) is implemented, but **no Sarvam key is available**. Live speech uses **OpenAI gpt-4o-mini-transcribe / gpt-4o-mini-tts**, with **Fish Audio** as an alternate TTS and the browser Web Speech API as the last fallback | No key | `pratifalan/providers/speech.py` |

## Repository and packaging

| # | Spec | What we did | Why | Where |
|---|---|---|---|---|
| 20 | `docker compose up` with an empty `.env` | Done. The API image contains code, `artifacts/`, `reports/`, `fixtures/` and `data/food/`, but not the research datasets. Ports bind to `127.0.0.1` by default (`BIND_ADDR` changes it) | Licences (CGMacros is CC BY-NC-SA) and image size; localhost binding is the safer default on shared servers | `docker-compose.yml`, `backend/Dockerfile` |
| 21 | "Model artefacts above 50 MB" in `.gitignore` | git cannot ignore by size. All current artefacts are small (the largest, `hybrid_cgmacros.pkl`, is about 2 MB), and the pre-commit hook `check-added-large-files --maxkb=51200` blocks anything larger | Tooling limit | `.gitignore`, `.pre-commit-config.yaml` |
