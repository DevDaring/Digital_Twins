# Machine-translated locales: review required

An AI model machine-translated the following locale files from `locales/en-IN.json`.
A native speaker has **not** reviewed them yet. Before any real use with patients,
a native speaker must check each one, ideally someone with some clinical background.

| File | Language | Script |
|---|---|---|
| `locales/hi-IN.json` | Hindi | Devanagari |
| `locales/bn-IN.json` | Bengali | Bengali |
| `locales/kn-IN.json` | Kannada | Kannada |

`en-IN.json` is the source of truth. If you add or change an English string, update all three files, or mark them for re-translation.

## Conventions used

- **Structure:** the key paths are exactly the same as in `en-IN.json`: no keys missing, no extra keys. A script checked this.
- **Placeholders:** every `{{...}}` placeholder is kept exactly as written. Word order around a placeholder was changed where the grammar needs it, e.g. `{{total}} में से {{n}}`.
- **Digits:** Western digits (0-9) are used everywhere, never native digits. The numbers match the English (70, 180, 108, 90%, 4, 24 and so on).
- **Kept untranslated:** `Pratifalan` (including in the disclaimer), `app.nativeName` = `प्रतिफलन` in every file, `mg/dL`, CGM, HbA1c, GMI, RMSE, eGFR, LDL, FHIR, BMI, and `data/README.md`.
- **Register:** plain, everyday speech with short sentences. Common English loanwords are preferred over formal or Sanskritised words.
  - Hindi: शुगर, रीडिंग, चेक, कार्ब्स, डेटा, रिपोर्ट, चांस
  - Bengali: সুগার, রিডিং, চেক, কার্বস, ডেটা, রিপোর্ট, ব্যান্ড
  - Kannada: ಶುಗರ್, ರೀಡಿಂಗ್, ಚೆಕ್, ಕಾರ್ಬ್ಸ್, ಡೇಟಾ, ರಿಪೋರ್ಟ್, ಬ್ಯಾಂಡ್, ವಾಕ್
- **Key terms:**

| English | Hindi | Bengali | Kannada |
|---|---|---|---|
| twin | ट्विन | টুইন | ಟ್ವಿನ್ |
| finger-prick | उंगली की जांच | আঙুলের পরীক্ষা | ಬೆರಳು ಪರೀಕ್ಷೆ |
| next best prick | अगली सबसे ज़रूरी जांच | পরের সবচেয়ে দরকারি পরীক্ষা | ಮುಂದಿನ ಮುಖ್ಯ ಪರೀಕ್ಷೆ |
| band (uncertainty) | पट्टी | ব্যান্ড | ಬ್ಯಾಂಡ್ (not ಪಟ್ಟಿ, which also means "list") |
| curve | लाइन | রেখা | ಗೆರೆ |
| marigold (colour) | नारंगी | কমলা | ಕಿತ್ತಳೆ |
| sensor ladder | सेंसर सीढ़ी | সেন্সর সিঁড়ি | ಸೆನ್ಸರ್ ಏಣಿ |
| what-if studio | 'अगर ऐसा हो' स्टूडियो | 'যদি এমন হয়' স্টুডিও | 'ಹೀಗಾದರೆ?' ಸ್ಟುಡಿಯೋ |
| calibrated | सेट किया गया | সেট করা | ಸೆಟ್ ಮಾಡಲಾಗಿದೆ |
| uncertainty | शक | সন্দেহ | ಸಂಶಯ |

## Reviewer checklist

**Medical-safety strings (highest priority)**
- [ ] `footer.disclaimer` must keep its exact meaning: it gives decision support, it is not a medical device, it never recommends insulin or medicine doses, and in an emergency the user should contact a doctor or call 108.
- [ ] `abstain.title`, `abstain.body`, `abstain.action` must clearly say the twin is not sure and the user should take a finger-prick reading. Nothing should sound like a diagnosis.
- [ ] `voice.emergency` and `voice.blocked` must read clearly as "emergency" and "I can't advise on this".
- [ ] `onboarding.c4.body` must keep "never gives medicine doses".
- [ ] `risk.*`, `whatif.deltaTitle`, `whatif.down`/`up`: the high/low direction and the 180 and 70 thresholds must be correct.

**Plural forms**
- [ ] `freq.n_one` / `freq.n_other` (and `freq.rare`, `freq.always`) must read naturally with `{{count}}`. Hindi, Bengali and Kannada mostly do not inflect here, but confirm the counter words: बार / বার / ಸಲ.
- [ ] Check other strings that contain counts (`common.years`, `trust.nPatients`, `trust.prompts`, `lab.saved`, `risk.dots`) with the values 1 and many.

**Tone and clarity**
- [ ] Would a 55-year-old shopkeeper understand each string the first time? Flag any words that are too formal or too technical.
- [ ] Check that "twin" is a good name in each language. The current choice is a transliteration, used the same way everywhere.
- [ ] Check that the loanwords sound natural in the target region (e.g. Bengali সম্ভাবনা vs চান্স, Kannada ಸಾಧ್ಯತೆ vs ಚಾನ್ಸ್).
- [ ] Check that strings fit the UI, especially `nav.*`, `ladder.*`, `actions.*` and buttons.
- [ ] Check that the gender/politeness forms are consistent (Hindi uses आप; Bengali uses আপনি; Kannada uses ನೀವು).

## Added 2026-10-05 (machine-translated, not yet reviewed)

New Trust-panel strings, written in English and machine-translated into hi/bn/kn with the same
conventions as above. Please review them together with the checklist.

- `trust.recent*`, `trust.withPrick`, `trust.withoutPrick`: value of a recent finger-prick
  (the sentences `recentHelps` / `recentHurts` / `recentUnclear` must keep their exact meaning: they
  are chosen from the 95% interval of the difference).
- `trust.living*`, `trust.hoursRange`, `trust.hoursOpen`, `trust.seriesRmse`, `trust.seriesWidth`:
  error and band width by hours since the last reading (`livingFlat` is an honest null result).
- `trust.col.hours`, `trust.col.forecasts`, `trust.col.width60`, `trust.col.people`,
  `trust.nPeople_*`, `trust.nRecordings_*`, `trust.recordingsNote`: people vs recordings.
- `trust.mealPhotoCaption` (changed), `trust.mealMetrics.median_abs_error_g`, `trust.ba*`,
  `trust.impact*`, `trust.indian*`, `trust.modelsUsed`: Experiment 7 (meal photos).
  `trust.indianSmoke` changed to a standalone sentence.
- `trust.agentModes.*`, `trust.agentMetrics.*`, `trust.agentByLang`, `trust.lowerBetter`,
  `trust.knownIssues`, `trust.seconds`, `trust.ms`: voice-assistant test suite.
  Safety-relevant: `agentMetrics.unsafe_advice_rate`, `agentMetrics.emergency_recall`,
  `agentMetrics.block_rate_unsafe` must read as "unsafe advice", "emergencies recognised",
  "unsafe requests blocked".
