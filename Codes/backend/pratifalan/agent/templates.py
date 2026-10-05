"""Template replies built directly from tool outputs, in four languages.

Used (a) in offline demo mode and (b) as the fallback when an LLM draft fails the
numeric grounding verifier twice. Every number comes from a tool output, so these
always pass verification. Translations are machine-produced; see
frontend/src/i18n/MACHINE_TRANSLATED.md for the review list.
"""

from __future__ import annotations

from datetime import datetime

LANGS = ("en-IN", "hi-IN", "bn-IN", "kn-IN")

T: dict[str, dict[str, str]] = {
    "state": {
        "en-IN": "Right now your glucose is about {est}, most likely between {lo} and {hi}. In the next 2 hours the chance of going above 180 is {phigh_freq}.",
        "hi-IN": "अभी आपकी शुगर लगभग {est} है, ज़्यादातर {lo} से {hi} के बीच। अगले 2 घंटों में 180 से ऊपर जाने की संभावना {phigh_freq} है।",
        "bn-IN": "এখন আপনার সুগার প্রায় {est}, সম্ভবত {lo} থেকে {hi}-এর মধ্যে। পরের 2 ঘণ্টায় 180-এর ওপরে যাওয়ার সম্ভাবনা {phigh_freq}।",
        "kn-IN": "ಈಗ ನಿಮ್ಮ ಸಕ್ಕರೆ ಸುಮಾರು {est}, ಹೆಚ್ಚಾಗಿ {lo} ಮತ್ತು {hi} ನಡುವೆ. ಮುಂದಿನ 2 ಗಂಟೆಗಳಲ್ಲಿ 180 ಮೀರುವ ಸಾಧ್ಯತೆ {phigh_freq}.",
    },
    "forecast_meal": {
        "en-IN": "If you eat {meal} now, about {carbs} grams of carbs, your glucose may peak near {peak} around {peak_time}. Chance of going above 180: {phigh_freq}.",
        "hi-IN": "अगर आप अभी {meal} खाते हैं, लगभग {carbs} ग्राम कार्ब्स, तो आपकी शुगर {peak_time} के आसपास {peak} तक जा सकती है। 180 से ऊपर जाने की संभावना: {phigh_freq}।",
        "bn-IN": "এখন যদি {meal} খান, প্রায় {carbs} গ্রাম কার্বস, তাহলে {peak_time} নাগাদ সুগার প্রায় {peak} পর্যন্ত উঠতে পারে। 180-এর ওপরে যাওয়ার সম্ভাবনা: {phigh_freq}।",
        "kn-IN": "ನೀವು ಈಗ {meal} ತಿಂದರೆ, ಸುಮಾರು {carbs} ಗ್ರಾಂ ಕಾರ್ಬ್ಸ್, ನಿಮ್ಮ ಸಕ್ಕರೆ {peak_time} ಹೊತ್ತಿಗೆ ಸುಮಾರು {peak} ತಲುಪಬಹುದು. 180 ಮೀರುವ ಸಾಧ್ಯತೆ: {phigh_freq}.",
    },
    "whatif": {
        "en-IN": "{label}: your peak changes by {dpeak}, and the chance of going above 180 moves from {p0} to {p1} percent.",
        "hi-IN": "{label}: आपका उच्चतम स्तर {dpeak} बदलता है, और 180 से ऊपर जाने की संभावना {p0} से {p1} प्रतिशत हो जाती है।",
        "bn-IN": "{label}: আপনার সর্বোচ্চ মাত্রা {dpeak} বদলায়, আর 180-এর ওপরে যাওয়ার সম্ভাবনা {p0} থেকে {p1} শতাংশ হয়।",
        "kn-IN": "{label}: ನಿಮ್ಮ ಗರಿಷ್ಠ ಮಟ್ಟ {dpeak} ಬದಲಾಗುತ್ತದೆ, ಮತ್ತು 180 ಮೀರುವ ಸಾಧ್ಯತೆ {p0} ರಿಂದ {p1} ಶೇಕಡಾ ಆಗುತ್ತದೆ.",
    },
    "whatif_small": {
        "en-IN": "{label}: the difference is too small to call. It stays within what I'm unsure about.",
        "hi-IN": "{label}: फ़र्क इतना छोटा है कि पक्का नहीं कह सकते। यह मेरी अनिश्चितता के भीतर है।",
        "bn-IN": "{label}: পার্থক্য এত ছোট যে নিশ্চিত বলা যায় না। এটা আমার অনিশ্চয়তার মধ্যেই থাকে।",
        "kn-IN": "{label}: ವ್ಯತ್ಯಾಸ ತುಂಬಾ ಚಿಕ್ಕದು, ಖಚಿತವಾಗಿ ಹೇಳಲಾಗದು. ಇದು ನನ್ನ ಅನಿಶ್ಚಿತತೆಯೊಳಗೇ ಇದೆ.",
    },
    "nbp": {
        "en-IN": "Check at {time}. That reading will teach me the most: it cuts my uncertainty by about {gain} percent.",
        "hi-IN": "{time} पर जाँच करें। उस रीडिंग से मुझे सबसे ज़्यादा सीखने को मिलेगा: मेरी अनिश्चितता लगभग {gain} प्रतिशत कम होगी।",
        "bn-IN": "{time}-এ মাপুন। সেই রিডিং থেকে আমি সবচেয়ে বেশি শিখব: আমার অনিশ্চয়তা প্রায় {gain} শতাংশ কমবে।",
        "kn-IN": "{time} ಕ್ಕೆ ಪರೀಕ್ಷಿಸಿ. ಆ ರೀಡಿಂಗ್‌ನಿಂದ ನಾನು ಹೆಚ್ಚು ಕಲಿಯುತ್ತೇನೆ: ನನ್ನ ಅನಿಶ್ಚಿತತೆ ಸುಮಾರು {gain} ಶೇಕಡಾ ಕಡಿಮೆಯಾಗುತ್ತದೆ.",
    },
    "reading": {
        "en-IN": "Thank you, I've added your reading of {value}. My band just narrowed by {pct} percent.",
        "hi-IN": "धन्यवाद, मैंने आपकी {value} की रीडिंग जोड़ दी। मेरा दायरा {pct} प्रतिशत छोटा हो गया।",
        "bn-IN": "ধন্যবাদ, আপনার {value} রিডিংটা যোগ করেছি। আমার সীমা {pct} শতাংশ সরু হলো।",
        "kn-IN": "ಧನ್ಯವಾದ, ನಿಮ್ಮ {value} ರೀಡಿಂಗ್ ಸೇರಿಸಿದ್ದೇನೆ. ನನ್ನ ವ್ಯಾಪ್ತಿ {pct} ಶೇಕಡಾ ಕಿರಿದಾಯಿತು.",
    },
    "forecast_meal_lowcarb": {
        "en-IN": "{meal} has very little carbohydrate, so it should barely move your glucose. With it, the twin expects a peak near {peak} around {peak_time}. Chance of going above 180: {phigh_freq}.",
        "hi-IN": "{meal} में बहुत कम कार्ब्स हैं, इसलिए इससे शुगर पर बहुत कम असर होगा। इसके साथ ट्विन को {peak_time} के आसपास लगभग {peak} तक का अनुमान है। 180 से ऊपर जाने की संभावना: {phigh_freq}।",
        "bn-IN": "{meal}-এ কার্বস খুবই কম, তাই সুগারে প্রায় প্রভাব পড়বে না। এর সঙ্গে টুইনের অনুমান {peak_time} নাগাদ সর্বোচ্চ প্রায় {peak}। 180-এর ওপরে যাওয়ার সম্ভাবনা: {phigh_freq}।",
        "kn-IN": "{meal} ನಲ್ಲಿ ಕಾರ್ಬ್ಸ್ ತುಂಬಾ ಕಡಿಮೆ, ಆದ್ದರಿಂದ ಸಕ್ಕರೆ ಹೆಚ್ಚು ಬದಲಾಗುವುದಿಲ್ಲ. ಇದರೊಂದಿಗೆ {peak_time} ಹೊತ್ತಿಗೆ ಗರಿಷ್ಠ ಸುಮಾರು {peak} ಎಂದು ಟ್ವಿನ್ ಅಂದಾಜಿಸುತ್ತದೆ. 180 ಮೀರುವ ಸಾಧ್ಯತೆ: {phigh_freq}.",
    },
    "whatif_peak_same": {
        "en-IN": "{label}: your peak stays about the same, and the chance of going above 180 moves from {p0} to {p1} percent.",
        "hi-IN": "{label}: आपका उच्चतम स्तर लगभग वैसा ही रहता है, और 180 से ऊपर जाने की संभावना {p0} से {p1} प्रतिशत हो जाती है।",
        "bn-IN": "{label}: আপনার সর্বোচ্চ মাত্রা প্রায় একই থাকে, আর 180-এর ওপরে যাওয়ার সম্ভাবনা {p0} থেকে {p1} শতাংশ হয়।",
        "kn-IN": "{label}: ನಿಮ್ಮ ಗರಿಷ್ಠ ಮಟ್ಟ ಸುಮಾರು ಹಾಗೆಯೇ ಇರುತ್ತದೆ, ಮತ್ತು 180 ಮೀರುವ ಸಾಧ್ಯತೆ {p0} ರಿಂದ {p1} ಶೇಕಡಾ ಆಗುತ್ತದೆ.",
    },
    "whatif_peak_only": {
        "en-IN": "{label}: your peak changes by {dpeak}, but the chance of going above 180 stays about {p0} percent.",
        "hi-IN": "{label}: आपका उच्चतम स्तर {dpeak} बदलता है, लेकिन 180 से ऊपर जाने की संभावना लगभग {p0} प्रतिशत ही रहती है।",
        "bn-IN": "{label}: আপনার সর্বোচ্চ মাত্রা {dpeak} বদলায়, কিন্তু 180-এর ওপরে যাওয়ার সম্ভাবনা প্রায় {p0} শতাংশই থাকে।",
        "kn-IN": "{label}: ನಿಮ್ಮ ಗರಿಷ್ಠ ಮಟ್ಟ {dpeak} ಬದಲಾಗುತ್ತದೆ, ಆದರೆ 180 ಮೀರುವ ಸಾಧ್ಯತೆ ಸುಮಾರು {p0} ಶೇಕಡಾದಲ್ಲೇ ಇರುತ್ತದೆ.",
    },
    "nbp_flat": {
        "en-IN": "Any time after {time} is fine. Right now I am fairly sure of your glucose, so one more reading would teach me only a little.",
        "hi-IN": "{time} के बाद कभी भी जाँच कर सकते हैं। अभी मुझे आपकी शुगर का अच्छा अंदाज़ा है, इसलिए एक और रीडिंग से थोड़ा ही सीखूँगा।",
        "bn-IN": "{time}-এর পরে যেকোনো সময় মাপতে পারেন। এখন আপনার সুগার সম্পর্কে আমি মোটামুটি নিশ্চিত, তাই আরেকটা রিডিং থেকে অল্পই শিখব।",
        "kn-IN": "{time} ನಂತರ ಯಾವಾಗ ಬೇಕಾದರೂ ಪರೀಕ್ಷಿಸಬಹುದು. ಈಗ ನಿಮ್ಮ ಸಕ್ಕರೆ ಬಗ್ಗೆ ನನಗೆ ಸಾಕಷ್ಟು ಖಚಿತತೆ ಇದೆ, ಆದ್ದರಿಂದ ಇನ್ನೊಂದು ರೀಡಿಂಗ್‌ನಿಂದ ಸ್ವಲ್ಪವೇ ಕಲಿಯುತ್ತೇನೆ.",
    },
    "reading_confirms": {
        "en-IN": "Thank you, I've added your reading of {value}. It matches what I expected, so my band stays about the same.",
        "hi-IN": "धन्यवाद, मैंने आपकी {value} की रीडिंग जोड़ दी। यह मेरे अनुमान से मेल खाती है, इसलिए मेरा दायरा लगभग वैसा ही रहा।",
        "bn-IN": "ধন্যবাদ, আপনার {value} রিডিংটা যোগ করেছি। এটা আমার অনুমানের সঙ্গে মিলে গেছে, তাই আমার সীমা প্রায় একই রইল।",
        "kn-IN": "ಧನ್ಯವಾದ, ನಿಮ್ಮ {value} ರೀಡಿಂಗ್ ಸೇರಿಸಿದ್ದೇನೆ. ಇದು ನನ್ನ ಅಂದಾಜಿಗೆ ಹೊಂದುತ್ತದೆ, ಆದ್ದರಿಂದ ನನ್ನ ವ್ಯಾಪ್ತಿ ಸುಮಾರು ಹಾಗೆಯೇ ಇದೆ.",
    },
    "explain_small": {
        "en-IN": "No single factor stands out right now: each one changes your peak only a little. The largest is {driver}.",
        "hi-IN": "अभी कोई एक कारण ख़ास नहीं है: हर कारण आपके उच्चतम स्तर को थोड़ा ही बदलता है। सबसे बड़ा है {driver}।",
        "bn-IN": "এখন আলাদা করে কোনো একটা কারণ বড় নয়: প্রতিটা কারণ সর্বোচ্চ মাত্রাকে অল্পই বদলায়। সবচেয়ে বড়টা হলো {driver}।",
        "kn-IN": "ಈಗ ಯಾವುದೇ ಒಂದು ಕಾರಣ ಎದ್ದು ಕಾಣುವುದಿಲ್ಲ: ಪ್ರತಿಯೊಂದೂ ನಿಮ್ಮ ಗರಿಷ್ಠ ಮಟ್ಟವನ್ನು ಸ್ವಲ್ಪವೇ ಬದಲಿಸುತ್ತದೆ. ದೊಡ್ಡದು {driver}.",
    },
    "low_risk": {
        "en-IN": "My estimate for going below 70 in the next 2 hours is {plow_freq}, but this low-sugar estimate is not validated yet: my training data had too few lows. If you feel shaky, sweaty or confused, check with a finger-prick.",
        "hi-IN": "अगले 2 घंटों में 70 से नीचे जाने का मेरा अनुमान {plow_freq} है, लेकिन कम शुगर का यह अनुमान अभी प्रमाणित नहीं है: मेरे सीखने के डेटा में बहुत कम लो थे। काँपना, पसीना या उलझन लगे तो उँगली से जाँच करें।",
        "bn-IN": "পরের 2 ঘণ্টায় 70-এর নিচে নামার আমার অনুমান {plow_freq}, কিন্তু কম সুগারের এই অনুমান এখনও যাচাই করা হয়নি: আমার শেখার ডেটায় লো খুব কম ছিল। কাঁপুনি, ঘাম বা বিভ্রান্তি হলে আঙুলে মেপে নিন।",
        "kn-IN": "ಮುಂದಿನ 2 ಗಂಟೆಗಳಲ್ಲಿ 70 ಕ್ಕಿಂತ ಕೆಳಗೆ ಹೋಗುವ ನನ್ನ ಅಂದಾಜು {plow_freq}, ಆದರೆ ಕಡಿಮೆ ಸಕ್ಕರೆಯ ಈ ಅಂದಾಜು ಇನ್ನೂ ಪರಿಶೀಲಿತವಲ್ಲ: ನನ್ನ ತರಬೇತಿ ಡೇಟಾದಲ್ಲಿ ಲೋ ತುಂಬಾ ಕಡಿಮೆ ಇದ್ದವು. ನಡುಕ, ಬೆವರು ಅಥವಾ ಗೊಂದಲ ಅನಿಸಿದರೆ ಬೆರಳಿನ ಪರೀಕ್ಷೆ ಮಾಡಿ.",
    },
    "explain": {
        "en-IN": "The biggest reason is {driver}: it changes your peak by about {contrib}.",
        "hi-IN": "सबसे बड़ा कारण है {driver}: इससे आपका उच्चतम स्तर लगभग {contrib} बदलता है।",
        "bn-IN": "সবচেয়ে বড় কারণ {driver}: এতে আপনার সর্বোচ্চ মাত্রা প্রায় {contrib} বদলায়।",
        "kn-IN": "ದೊಡ್ಡ ಕಾರಣ {driver}: ಇದು ನಿಮ್ಮ ಗರಿಷ್ಠ ಮಟ್ಟವನ್ನು ಸುಮಾರು {contrib} ಬದಲಿಸುತ್ತದೆ.",
    },
    "meal_logged": {
        "en-IN": "I've noted {meal}, about {carbs} grams of carbs. Your peak may reach {peak} around {peak_time}.",
        "hi-IN": "मैंने {meal} दर्ज कर लिया, लगभग {carbs} ग्राम कार्ब्स। आपकी शुगर {peak_time} के आसपास {peak} तक जा सकती है।",
        "bn-IN": "{meal} লিখে রাখলাম, প্রায় {carbs} গ্রাম কার্বস। {peak_time} নাগাদ সুগার {peak} পর্যন্ত উঠতে পারে।",
        "kn-IN": "{meal} ದಾಖಲಿಸಿದ್ದೇನೆ, ಸುಮಾರು {carbs} ಗ್ರಾಂ ಕಾರ್ಬ್ಸ್. {peak_time} ಹೊತ್ತಿಗೆ ಸಕ್ಕರೆ {peak} ತಲುಪಬಹುದು.",
    },
    "abstain": {
        "en-IN": "I am not sure enough right now. Please take a finger-prick reading so I can see clearly again.",
        "hi-IN": "अभी मैं पक्का नहीं हूँ। कृपया उँगली से एक जाँच कर लें ताकि मैं फिर साफ़ देख सकूँ।",
        "bn-IN": "এখন আমি যথেষ্ট নিশ্চিত নই। আঙুলে একবার মেপে নিন, যাতে আবার পরিষ্কার দেখতে পাই।",
        "kn-IN": "ಈಗ ನನಗೆ ಸಾಕಷ್ಟು ಖಚಿತತೆ ಇಲ್ಲ. ದಯವಿಟ್ಟು ಬೆರಳಿನ ಪರೀಕ್ಷೆ ಮಾಡಿ, ಆಗ ನಾನು ಮತ್ತೆ ಸ್ಪಷ್ಟವಾಗಿ ನೋಡುತ್ತೇನೆ.",
    },
    "outlook": {
        "en-IN": "This is a projection, not a promise. If habits stay the same, time in range stays near {tir0} percent; with smaller rice portions and short walks it could reach {tir1} percent.",
        "hi-IN": "यह एक अनुमान है, वादा नहीं। आदतें वैसी रहीं तो सही दायरे में समय लगभग {tir0} प्रतिशत रहेगा; कम चावल और छोटी सैर से यह {tir1} प्रतिशत तक जा सकता है।",
        "bn-IN": "এটা একটা আনুমানিক হিসাব, প্রতিশ্রুতি নয়। অভ্যাস একই থাকলে সঠিক সীমায় সময় প্রায় {tir0} শতাংশ থাকবে; কম ভাত আর ছোট হাঁটায় তা {tir1} শতাংশে পৌঁছাতে পারে।",
        "kn-IN": "ಇದು ಅಂದಾಜು, ಭರವಸೆ ಅಲ್ಲ. ಅಭ್ಯಾಸ ಹಾಗೆಯೇ ಇದ್ದರೆ ಸರಿಯಾದ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ ಸಮಯ ಸುಮಾರು {tir0} ಶೇಕಡಾ ಇರುತ್ತದೆ; ಕಡಿಮೆ ಅನ್ನ ಮತ್ತು ಸಣ್ಣ ನಡಿಗೆಯಿಂದ {tir1} ಶೇಕಡಾ ತಲುಪಬಹುದು.",
    },
    "education": {
        "en-IN": "Time in range means the share of the day your glucose stays between 70 and 180. Higher is better. HbA1c shows your average sugar over about 3 months.",
        "hi-IN": "सही दायरे में समय का मतलब है दिन का वह हिस्सा जब शुगर 70 से 180 के बीच रहती है। जितना ज़्यादा, उतना अच्छा। HbA1c लगभग 3 महीनों की औसत शुगर बताता है।",
        "bn-IN": "সঠিক সীমায় সময় মানে দিনের কতটা সময় সুগার 70 থেকে 180-এর মধ্যে থাকে। যত বেশি, তত ভালো। HbA1c প্রায় 3 মাসের গড় সুগার দেখায়।",
        "kn-IN": "ಸರಿಯಾದ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ ಸಮಯ ಎಂದರೆ ದಿನದಲ್ಲಿ ಸಕ್ಕರೆ 70 ರಿಂದ 180 ರ ನಡುವೆ ಇರುವ ಭಾಗ. ಹೆಚ್ಚು ಇದ್ದಷ್ಟು ಒಳ್ಳೆಯದು. HbA1c ಸುಮಾರು 3 ತಿಂಗಳ ಸರಾಸರಿ ಸಕ್ಕರೆಯನ್ನು ತೋರಿಸುತ್ತದೆ.",
    },
    "whatif_unknown": {
        "en-IN": "I could not tell which change you mean. You can ask, for example: what if I take a short walk after dinner, or what if I eat roti instead of rice?",
        "hi-IN": "मैं समझ नहीं पाया कि आप कौन-सा बदलाव पूछ रहे हैं। आप ऐसे पूछ सकते हैं: खाने के बाद थोड़ा टहलूँ तो, या चावल की जगह रोटी खाऊँ तो क्या होगा?",
        "bn-IN": "আপনি কোন বদলের কথা বলছেন বুঝতে পারিনি। এভাবে জিজ্ঞাসা করতে পারেন: খাওয়ার পরে একটু হাঁটলে, বা ভাতের বদলে রুটি খেলে কী হবে?",
        "kn-IN": "ನೀವು ಯಾವ ಬದಲಾವಣೆ ಕೇಳುತ್ತಿದ್ದೀರಿ ಎಂದು ತಿಳಿಯಲಿಲ್ಲ. ಹೀಗೆ ಕೇಳಬಹುದು: ಊಟದ ನಂತರ ಸ್ವಲ್ಪ ನಡೆದರೆ, ಅಥವಾ ಅನ್ನದ ಬದಲು ಚಪಾತಿ ತಿಂದರೆ ಏನಾಗುತ್ತದೆ?",
    },
    "reading_offer": {
        "en-IN": "Thank you for your reading of {value}. Confirm below if you want me to add it to your twin.",
        "hi-IN": "{value} की रीडिंग के लिए धन्यवाद। अगर आप चाहते हैं कि मैं इसे आपके ट्विन में जोड़ूँ, तो नीचे पुष्टि करें।",
        "bn-IN": "{value} রিডিংটার জন্য ধন্যবাদ। এটা আপনার টুইনে যোগ করতে চাইলে নিচে নিশ্চিত করুন।",
        "kn-IN": "{value} ರೀಡಿಂಗ್‌ಗೆ ಧನ್ಯವಾದ. ಇದನ್ನು ನಿಮ್ಮ ಟ್ವಿನ್‌ಗೆ ಸೇರಿಸಬೇಕಾದರೆ ಕೆಳಗೆ ಖಚಿತಪಡಿಸಿ.",
    },
    "reading_widened": {
        "en-IN": "Thank you, I've added your reading of {value}. It surprised me, so my 2-hour band widened by {pct} percent.",
        "hi-IN": "धन्यवाद, मैंने आपकी {value} की रीडिंग जोड़ दी। यह मेरे अनुमान से अलग थी, इसलिए मेरा 2 घंटे का दायरा {pct} प्रतिशत चौड़ा हो गया।",
        "bn-IN": "ধন্যবাদ, আপনার {value} রিডিংটা যোগ করেছি। এটা আমার অনুমানের থেকে আলাদা, তাই আমার 2 ঘণ্টার সীমা {pct} শতাংশ চওড়া হলো।",
        "kn-IN": "ಧನ್ಯವಾದ, ನಿಮ್ಮ {value} ರೀಡಿಂಗ್ ಸೇರಿಸಿದ್ದೇನೆ. ಇದು ನನ್ನ ಅಂದಾಜಿಗಿಂತ ಬೇರೆ ಇತ್ತು, ಆದ್ದರಿಂದ ನನ್ನ 2 ಗಂಟೆಯ ವ್ಯಾಪ್ತಿ {pct} ಶೇಕಡಾ ಅಗಲವಾಯಿತು.",
    },
    "meal_offer": {
        "en-IN": "Confirm below if you want me to log this meal now.",
        "hi-IN": "अगर आप चाहते हैं कि मैं यह खाना अभी दर्ज करूँ, तो नीचे पुष्टि करें।",
        "bn-IN": "এই খাবারটা এখন লিখে রাখতে চাইলে নিচে নিশ্চিত করুন।",
        "kn-IN": "ಈ ಊಟವನ್ನು ಈಗ ದಾಖಲಿಸಬೇಕಾದರೆ ಕೆಳಗೆ ಖಚಿತಪಡಿಸಿ.",
    },
    "action_cancelled": {
        "en-IN": "Okay, I have not added it.",
        "hi-IN": "ठीक है, मैंने इसे नहीं जोड़ा।",
        "bn-IN": "ঠিক আছে, আমি এটা যোগ করিনি।",
        "kn-IN": "ಸರಿ, ನಾನು ಇದನ್ನು ಸೇರಿಸಿಲ್ಲ.",
    },
    "action_stale": {
        "en-IN": "That reading is now more than 30 minutes old on the replay clock, so I did not add it as a current reading. Please enter a fresh one.",
        "hi-IN": "रीप्ले घड़ी पर वह रीडिंग अब 30 मिनट से ज़्यादा पुरानी है, इसलिए मैंने उसे अभी की रीडिंग की तरह नहीं जोड़ा। कृपया नई रीडिंग डालें।",
        "bn-IN": "রিপ্লে ঘড়িতে ওই রিডিংটা এখন 30 মিনিটের বেশি পুরনো, তাই এটাকে এখনকার রিডিং হিসেবে যোগ করিনি। দয়া করে নতুন রিডিং দিন।",
        "kn-IN": "ರೀಪ್ಲೇ ಗಡಿಯಾರದಲ್ಲಿ ಆ ರೀಡಿಂಗ್ ಈಗ 30 ನಿಮಿಷಕ್ಕಿಂತ ಹಳೆಯದು, ಆದ್ದರಿಂದ ಅದನ್ನು ಈಗಿನ ರೀಡಿಂಗ್ ಆಗಿ ಸೇರಿಸಿಲ್ಲ. ದಯವಿಟ್ಟು ಹೊಸದನ್ನು ನಮೂದಿಸಿ.",
    },
}

# What-if labels (the "{label}:" that starts a what-if reply).
WHATIF_LABEL: dict[str, dict[str, str]] = {
    "generic": {"en-IN": "With this change", "hi-IN": "इस बदलाव से", "bn-IN": "এই বদলে", "kn-IN": "ಈ ಬದಲಾವಣೆಯಿಂದ"},
    "swap": {"en-IN": "{new} instead of {old}", "hi-IN": "{old} की जगह {new}", "bn-IN": "{old} না খেয়ে {new}",
             "kn-IN": "{old} ತಿನ್ನುವ ಬದಲು {new}"},
    "walk": {"en-IN": "A {n}-minute walk after the meal", "hi-IN": "खाने के बाद {n} मिनट टहलने से",
             "bn-IN": "খাওয়ার পরে {n} মিনিট হাঁটলে", "kn-IN": "ಊಟದ ನಂತರ {n} ನಿಮಿಷ ನಡೆದರೆ"},
    "half": {"en-IN": "Half the {food}", "hi-IN": "आधा {food} खाने से", "bn-IN": "অর্ধেক {food} খেলে",
             "kn-IN": "ಅರ್ಧ {food} ತಿಂದರೆ"},
    "later": {"en-IN": "Eating later", "hi-IN": "देर से खाने पर", "bn-IN": "দেরিতে খেলে", "kn-IN": "ತಡವಾಗಿ ತಿಂದರೆ"},
    "earlier": {"en-IN": "Eating earlier", "hi-IN": "जल्दी खाने पर", "bn-IN": "আগে খেলে", "kn-IN": "ಬೇಗ ತಿಂದರೆ"},
}

# Physiology driver names from the twin (engine ``_driver_variants``) in plain words, per language.
DRIVER_LABELS: dict[str, dict[str, str]] = {
    "meal_carbs": {"en-IN": "the carbs in this meal", "hi-IN": "इस खाने के कार्ब्स", "bn-IN": "এই খাবারের কার্বস",
                   "kn-IN": "ಈ ಊಟದ ಕಾರ್ಬ್ಸ್"},
    "earlier_meals": {"en-IN": "earlier food still digesting", "hi-IN": "पहले खाया खाना, जो अभी पच रहा है",
                      "bn-IN": "আগের খাবার, যা এখনও হজম হচ্ছে", "kn-IN": "ಮೊದಲು ತಿಂದ ಆಹಾರ, ಇನ್ನೂ ಜೀರ್ಣವಾಗುತ್ತಿದೆ"},
    "insulin_sensitivity": {"en-IN": "how your body handles sugar compared with most people",
                            "hi-IN": "आपका शरीर दूसरों की तुलना में शुगर को कैसे संभालता है",
                            "bn-IN": "অন্যদের তুলনায় আপনার শরীর সুগার কীভাবে সামলায়",
                            "kn-IN": "ಇತರರಿಗೆ ಹೋಲಿಸಿದರೆ ನಿಮ್ಮ ದೇಹ ಸಕ್ಕರೆಯನ್ನು ನಿಭಾಯಿಸುವ ರೀತಿ"},
    "dawn_effect": {"en-IN": "the time of day (your body clock)", "hi-IN": "दिन का समय (शरीर की घड़ी)",
                    "bn-IN": "দিনের সময় (শরীরের ঘড়ি)", "kn-IN": "ದಿನದ ಸಮಯ (ದೇಹದ ಗಡಿಯಾರ)"},
    "recent_activity": {"en-IN": "your recent activity", "hi-IN": "हाल में चलना-फिरना", "bn-IN": "সম্প্রতি হাঁটাচলা",
                        "kn-IN": "ಇತ್ತೀಚಿನ ಚಟುವಟಿಕೆ"},
    "unexplained": {"en-IN": "a recent trend the twin cannot explain", "hi-IN": "हाल का ऐसा रुझान जिसका कारण ट्विन नहीं जानता",
                    "bn-IN": "সাম্প্রতিক এমন ঝোঁক, যার কারণ টুইন জানে না", "kn-IN": "ಟ್ವಿನ್ ವಿವರಿಸಲಾಗದ ಇತ್ತೀಚಿನ ಏರಿಳಿತ"},
}


DRIVER_NAME_BY_EN = {
    "Earlier food still digesting": "earlier_meals", "Your insulin sensitivity vs typical": "insulin_sensitivity",
    "Time of day (body clock)": "dawn_effect", "Recent activity": "recent_activity",
    "Recent unexplained trend": "unexplained",
}


def driver_label(name: str | None, label_en: str, lang: str) -> str:
    """Localised driver label; unknown (learned) drivers keep their English label."""
    if not name:
        name = "meal_carbs" if label_en.startswith("This meal's carbs") else DRIVER_NAME_BY_EN.get(label_en)
    labels = DRIVER_LABELS.get(name or "")
    if labels:
        return labels.get(lang, labels["en-IN"])
    return label_en[:1].lower() + label_en[1:] if lang == "en-IN" else label_en


def whatif_label(kind: str, lang: str, **kw: object) -> str:
    tpl = WHATIF_LABEL[kind].get(lang, WHATIF_LABEL[kind]["en-IN"])
    out = tpl.format(**kw)
    return out[:1].upper() + out[1:] if out[:1].isascii() else out

FREQ = {
    "en-IN": ("less than 1 time in 10", "about {n} times out of 10", "almost every time"),
    "hi-IN": ("10 में 1 से कम बार", "10 में लगभग {n} बार", "लगभग हर बार"),
    "bn-IN": ("10 বারে 1 বারেরও কম", "10 বারে প্রায় {n} বার", "প্রায় প্রতিবার"),
    "kn-IN": ("10 ರಲ್ಲಿ 1 ಕ್ಕಿಂತ ಕಡಿಮೆ ಬಾರಿ", "10 ರಲ್ಲಿ ಸುಮಾರು {n} ಬಾರಿ", "ಬಹುತೇಕ ಪ್ರತಿ ಬಾರಿ"),
}

AMPM = {"en-IN": ("am", "pm")}
# Indian languages name the part of the day instead of am/pm: (from_hour, word), first match wins.
DAYPART = {
    "hi-IN": ((4, "सुबह"), (12, "दोपहर"), (16, "शाम"), (20, "रात"), (0, "रात")),
    "bn-IN": ((4, "সকাল"), (12, "দুপুর"), (15, "বিকেল"), (17, "সন্ধ্যা"), (20, "রাত"), (0, "রাত")),
    "kn-IN": ((4, "ಬೆಳಿಗ್ಗೆ"), (12, "ಮಧ್ಯಾಹ್ನ"), (16, "ಸಂಜೆ"), (20, "ರಾತ್ರಿ"), (0, "ರಾತ್ರಿ")),
}


def freq(p: float, lang: str) -> str:
    lo, mid, hi = FREQ.get(lang, FREQ["en-IN"])
    n = int(round(p * 10))
    if n <= 0:
        return lo
    if n >= 10:
        return hi
    return mid.format(n=n)


def daypart(hour: int, lang: str) -> str:
    for start, word in sorted(DAYPART[lang], key=lambda x: -x[0]):
        if hour >= start:
            return word
    return DAYPART[lang][-1][1]


def clock(iso: str | None, lang: str) -> str:
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso)
    h12 = (dt.hour % 12) or 12
    if lang not in DAYPART:
        am, pm = AMPM["en-IN"]
        return f"{h12}:{dt.minute:02d} {am if dt.hour < 12 else pm}"
    return f"{daypart(dt.hour, lang)} {h12}:{dt.minute:02d}"


def render(key: str, lang: str, claims: list | None = None, **kw: object) -> str:
    """Fill a template. Values may be ``agent.slots.Slot`` objects (anything with ``rendered`` and
    ``claim()``): their rendered text is used and, when ``claims`` is given, their claim is recorded."""
    tpl = T[key].get(lang, T[key]["en-IN"])
    vals: dict[str, object] = {}
    for k, v in kw.items():
        if hasattr(v, "rendered") and hasattr(v, "claim"):
            vals[k] = v.rendered
            if claims is not None and "{" + k + "}" in tpl:
                claims.append(v.claim())
        else:
            vals[k] = v
    out = tpl.format(**vals)
    # A dish name at the very start of a sentence ("boiled egg has ...") reads better capitalised.
    return out[:1].upper() + out[1:] if out[:1].isascii() else out


def signed(v: float) -> str:
    return f"{'+' if v >= 0 else '-'}{abs(round(v))}"
