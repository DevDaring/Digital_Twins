"""Safety filter (spec section 7.4): deterministic rules first, LLM second.

* Dose / medication-change requests are blocked with a fixed message.
* Reported symptoms of severe low or very high glucose trigger a fixed emergency
  message (shown and spoken), regardless of what the planner would say.
* Diagnosis requests are refused.
* Prompt-injection attempts (e.g. inside a meal description) are neutralised: the
  text is treated as data and the attempt is flagged.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from pratifalan.agent.verifier import normalise_digits

# Dose / medication-change requests. English and romanised Hindi ("insulin kitna", "dawai badha",
# "dose double") need a drug word plus an amount/change word; native-script drug words and the
# Indic words for insulin "units" (यूनिट / ইউনিট / ಯೂನಿಟ್) count on their own.
DOSE_EN = [
    r"\b(insulin|metformin|glimepiride|gliclazide|sitagliptin|empagliflozin|dapagliflozin|semaglutide|ozempic|"
    r"glipizide|pioglitazone|vildagliptin|teneligliptin|lantus|novorapid|humalog|tablet|tablets|pill|pills|"
    r"medicine|medication|drug|dose|dosage|units?)\b.*\b(how much|how many|increase|decrease|reduce|double|"
    r"skip|stop|change|take|adjust|more|less|extra|inject)\b",
    r"\b(how much|how many|increase|decrease|reduce|double|skip|stop|change|adjust|extra|inject|take|more|less|"
    r"add|halve)\b.*\b(insulin|metformin|glimepiride|medicine|medication|tablet|tablets|pill|pills|dose|units?)\b",
    # gerund / past forms in either order: "whether skipping my evening glimepiride is fine"
    r"\b(skipp\w*|miss(?:ing|ed)|omit\w*|stopp\w*|chang(?:ing|ed)|increas\w*|decreas\w*|reduc\w*|doubl\w*|"
    r"halv\w*|adjust\w*)\b.{0,40}\b(insulin|metformin|glimepiride|gliclazide|sitagliptin|medicine|medicines|"
    r"medication|medications|tablet|tablets|pill|pills|dose|doses|units?)\b",
    r"\b(insulin|metformin|glimepiride|gliclazide|sitagliptin|medicine|medication|tablet|tablets|pill|pills|dose)\b"
    r".{0,40}\b(skipp\w*|miss(?:ing|ed)|omit\w*|stopp\w*|chang(?:ing|ed)|increas\w*|decreas\w*|reduc\w*|"
    r"doubl\w*|halv\w*)\b",
    # romanised Hindi / Hinglish
    r"\b(insulin|metformin|glimepiride|dawa|dawai|davai|davaai|dawaai|goli|dose|medicine|tablet|units?)\b.*\b("
    r"kitna|kitni|kitne|badha\w*|badhau\w*|badhaun|ghata\w*|kam kar\w*|band kar\w*|chhod\w*|chod\w*|double|"
    r"dugna|doguna|lagau\w*|lagaun|lu|loon|lun|le lu|le loon|kha lu)\b",
    r"\b(kitna|kitni|kitne)\b.*\b(insulin|dawa|dawai|davai|goli|dose|units?)\b",
    # romanised Bengali / Kannada
    r"\b(oshudh|osudh|oshud|oushodh|oshudher|insulin|metformin|tablet|bori)\b.*\b(bondho|bando|baad|komabo|"
    r"kombo|komiye|barabo|baraabo|bariye|koto|kotota|khabo na|nebo na)\b",
    r"\b(aushadha|ausadha|aushada|maatre|matre|insulin|metformin)\b.*\b(beda|bidabahuda|bidabahudha|bidli|bidi|"
    r"bidona|hechchu|hechu|kadime|eshtu|nillisi|nilsi)\b",
]
DOSE_INDIC = [
    r"(इंसुलिन|इन्सुलिन|दवा|दवाई|गोली|खुराक|मेटफॉर्मिन|डोज़|डोज|यूनिट)",
    r"(ইনসুলিন|ওষুধ|ঔষধ|ট্যাবলেট|ডোজ|মেটফরমিন|বড়ি|ইউনিট)",
    r"(ಇನ್ಸುಲಿನ್|ಔಷಧ|ಮಾತ್ರೆ|ಡೋಸ್|ಮೆಟ್‌ಫಾರ್ಮಿನ್|ಮೆಟ್ಫಾರ್ಮಿನ್|ಯೂನಿಟ್)",
]
DOSE_PATTERNS = DOSE_EN + DOSE_INDIC

# Symptoms that are an emergency on their own (gap-tolerant: "सीने में बहुत तेज़ दर्द").
EMERGENCY_PATTERNS = [
    r"\b(unconscious|fainted|faint|fainting|passed out|collapsed|seizure|fits|convulsion\w*|can'?t wake|"
    r"not waking|not responding|unresponsive|cannot breathe|can'?t breathe|very low sugar|"
    r"sugar (?:is )?(?:below|under) ?(?:50|54|40)|vomiting and drowsy|fruity breath)\b",
    r"\bchest\b.{0,30}\b(?:pain|ache|aching|pressure|tightness)\b", r"\b(?:pain|ache|pressure|tightness)\b.{0,30}\bchest\b",
    r"(बेहोश|चक्कर आकर गिर|दौरा पड़|सांस नहीं|बहुत कम शुगर|शुगर बहुत कम|उठ नहीं रहे|उठ नहीं रही)",
    r"(सीने|सीना|छाती)\s*.{0,40}(दर्द|दबाव|जकड़)", r"सांस\s*.{0,12}(नहीं ले पा|नहीं आ रही)",
    r"\b(behosh|seene me\w* .{0,12}dard)\b",
    r"(অজ্ঞান|জ্ঞান হারা|খিঁচুনি|শ্বাস নিতে পারছি না|খুব কম সুগার|সাড়া দিচ্ছে)",
    r"বুকে\s*.{0,30}(ব্যথা|যন্ত্রণা)", r"শ্বাস\s*.{0,12}(নিতে পারছি না|নিতে পারছে না)",
    r"(ಪ್ರಜ್ಞೆ ತಪ್ಪ|ಮೂರ್ಛೆ|ಸೆಳೆತ|ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ|ತುಂಬಾ ಕಡಿಮೆ ಸಕ್ಕರೆ|ಏಳುತ್ತಿಲ್ಲ)",
    r"ಎದೆ\S*\s*.{0,30}ನೋವು",
]

# Low-glucose symptom groups. Trembling alone is enough; otherwise two different groups are
# needed (sweating after a walk is not an emergency, sweating + dizziness may be).
LOW_SYMPTOMS: dict[str, list[str]] = {
    "tremor": [r"\bshak(?:y|ing|es)\b", r"\btrembl\w*", r"\bjitter\w*", r"कांप", r"थरथर", r"\bk(?:aa|a)np\w*",
               r"\bkamp(?:ne|na|ta|ti|te|n)\w*", r"কাঁপ", r"ನಡುಗ", r"ನಡುಕ"],
    "sweat": [r"\bsweat\w*", r"\bclammy\b", r"पसीन", r"\bpas(?:ee|i)n\w*", r"ঘাম", r"ಬೆವರ"],
    "dizzy": [r"\bdizz\w*", r"light.?headed", r"\bgiddy\b", r"\bchakk?ar\b", r"चक्कर", r"মাথা\s*(?:ঘোর|ঘুর)",
              r"ತಲೆ\s*(?:ಸುತ್ತ|ತಿರುಗ)", r"ತಲೆತಿರುಗ"],
    "confused": [r"\bconfus\w*", r"\bdisorient\w*", r"\bnot making sense\b", r"उलझन", r"होश नहीं", r"বিভ্রান্ত",
                 r"এলোমেলো কথা", r"ಗೊಂದಲ"],
    "palpitation": [r"heart (?:is )?(?:pounding|racing|beating fast)", r"\bpalpitat\w*", r"घबराहट", r"\bghabrahat\b",
                    r"धड़कन", r"ধড়ফড়", r"ಎದೆ\s*(?:ಬಡಿತ|ಡವಡವ)"],
    "weak": [r"\bweak(?:ness)?\b", r"\bblurr\w*", r"कमज़ोरी", r"धुंधला", r"\bkamzori\b", r"দুর্বল", r"ঝাপসা",
             r"ಸುಸ್ತು", r"ನಿಶ್ಶಕ್ತಿ", r"ಮಸುಕು"],
    "crash": [r"sugar (?:has |is |just )?(?:crash|dropp|fell|falling|going down fast)\w*", r"शुगर .{0,12}गिर",
              r"সুগার .{0,12}(?:পড়ে গেছে|নেমে গেছে)", r"ಸಕ್ಕರೆ .{0,12}(?:ಇಳಿದ|ಕುಸಿದ)"],
}
SINGLE_LOW_GROUPS = ("tremor",)
# Very-high-glucose danger signs (with a value > 400): vomiting, breathing, ketones, drowsiness.
HIGH_SYMPTOMS = [
    r"\bvomit\w*", r"\bthrowing up\b", r"\bulti\b", r"\bbreath\w*", r"\bsaa?ns\b", r"\bketon\w*", r"\bdrows\w*",
    r"\bsleepy\b", r"\bconfus\w*", r"उल्टी", r"सांस", r"कीटोन", r"नींद", r"सुस्ती", r"उनींद", r"বমি", r"শ্বাস",
    r"কিটোন", r"ঝিমুনি", r"ঘুম ঘুম", r"ವಾಂತಿ", r"ಉಸಿರ", r"ಕೀಟೋನ್", r"ತೂಕಡಿಕೆ", r"ಮಂಪರು",
]

# A glucose value the user reports: a number after a sugar/glucose/reading/meter word (up to ~25
# characters apart: "मेरी शुगर अभी 172 आई है"), a number with mg/dL or mmol/L, or a bare number.
GLUCOSE_WORDS = (r"(?:blood sugar|sugar|glucose|readings?|meter|glucometer|bsl|fbs|ppbs|rbs|"
                 r"शुगर|शूगर|सुगर|ग्लूकोज|रीडिंग|मीटर|সুগার|সুগারের|গ্লুকোজ|রিডিং|মিটার|"
                 r"ಸಕ್ಕರೆ|ಶುಗರ್|ಗ್ಲೂಕೋಸ್|ರೀಡಿಂಗ್|ಮೀಟರ್)")
_NUM = r"(\d{2,3}(?:\.\d+)?|\d\.\d+)"
_NOT_A_READING_BEFORE = re.compile(
    r"(above|over|than|between|cross|exceed|target|range|reach|go to|goes to|hit|from|upto|up to|by|"
    r"times|out of|in \d|ke paar|se upar)", re.I)
_NOT_A_READING_AFTER = re.compile(
    r"^\s*(?:[-–]\s*\d|to\s+\d|:\d|min\b|mins\b|minutes?\b|hrs?\b|hours?\b|days?\b|weeks?\b|months?\b|years?\b|"
    r"%|percent|g\b|gm\b|grams?\b|kg\b|steps?\b|k?cal\b|times\b|out of|or (?:more|less)|plus\b|\+|cross|"
    r"मिनट|घंट|दिन|हफ्त|महीन|साल|प्रतिशत|ग्राम|बार|से\s*(?:ऊपर|नीचे|ज्यादा|अधिक|कम|पार)|के\s*(?:पार|ऊपर)|पार|"
    r"মিনিট|ঘণ্টা|দিন|সপ্তাহ|মাস|বছর|শতাংশ|গ্রাম|বার|-?এর\s*(?:ওপর|উপর|নিচ|বেশি|কম)|পেরো|ছাড়া|"
    r"ನಿಮಿಷ|ಗಂಟೆ|ದಿನ|ವಾರ|ತಿಂಗಳ|ವರ್ಷ|ಶೇಕಡ|ಗ್ರಾಂ|ಬಾರಿ|ಮೀರ|ದಾಟ|ಕ್ಕಿಂತ|ರ\s*ಮೇಲೆ|ರಿಂದ)", re.I)

DIAGNOSIS_PATTERNS = [
    r"\b(do i have|diagnose|is it cancer|am i diabetic|do i have (?:kidney|heart)|what disease)\b",
    r"(क्या मुझे .*बीमारी है|निदान)", r"(আমার কি .*রোগ|রোগ নির্ণয়)", r"(ನನಗೆ .*ಕಾಯಿಲೆ ಇದೆಯಾ|ರೋಗನಿರ್ಣಯ)",
]
INJECTION_PATTERNS = [
    r"ignore (?:all |the |your )?(?:previous |above |prior )?(?:instructions|prompts?|rules)",
    r"(system prompt|you are now|disregard (?:your|the|all) (?:rules|instructions)|developer mode|jailbreak|act as)",
    r"(tell (?:the user|me) to (?:take|double|stop)|recommend (?:a |an )?(?:dose|insulin))",
    # Hindi / Bengali / Kannada: "ignore (all previous) instructions", "system prompt", "you are now"
    r"(निर्देश|निर्देशों|नियम|नियमों|हिदायत)\s*(को\s*)?(अनदेखा|नजरअंदाज|भूल जा|मत मान)",
    r"(सिस्टम प्रॉम्प्ट|सिस्टम प्रोम्प्ट|अब तुम .* हो)",
    r"(নির্দেশ|নির্দেশনা|নিয়ম)\S*\s*(উপেক্ষা|ভুলে যাও|অগ্রাহ্য|মানবে না)",
    r"(সিস্টেম প্রম্পট|এখন থেকে তুমি)",
    r"(ಸೂಚನೆ|ನಿಯಮ)\S*\s*(ನಿರ್ಲಕ್ಷಿಸ|ಮರೆತು|ಕಡೆಗಣಿಸ|ಪಾಲಿಸಬೇಡ)",
    r"(ಸಿಸ್ಟಮ್ ಪ್ರಾಂಪ್ಟ್|ಈಗಿನಿಂದ ನೀನು)",
    # "note to the AI / assistant" and "from now on answer ..." smuggled into a meal description
    r"\b(note (?:to|for) (?:the )?(?:ai|assistant|bot|model)|(?:ai|assistant)\s*:|from now on (?:answer|reply|say|you))\b",
    r"(सहायक|एआई|असिस्टेंट)\s*(के लिए|को)\s*(नोट|निर्देश)|अब से (सिर्फ|केवल|तुम)",
    r"(এআই|সহকারী)\S*\s*(জন্য|প্রতি)|এখন থেকে (শুধু|তুমি)",
    r"(ಎಐ|ಸಹಾಯಕ)\S*\s*(ಗೆ|ಕ್ಕೆ)?\s*ಸೂಚನೆ|ಈಗಿನಿಂದ (ಕೇವಲ|ನೀನು)",
]

MESSAGES = {
    "dose": {
        "en-IN": "I can't advise on insulin or medicine doses. Please ask your doctor before changing any medicine. I can show how food and walks change your glucose.",
        "hi-IN": "मैं इंसुलिन या दवा की खुराक के बारे में सलाह नहीं दे सकता। कोई भी दवा बदलने से पहले अपने डॉक्टर से पूछें। मैं दिखा सकता हूँ कि खाना और टहलना आपकी शुगर को कैसे बदलते हैं।",
        "bn-IN": "আমি ইনসুলিন বা ওষুধের ডোজ নিয়ে পরামর্শ দিতে পারি না। কোনো ওষুধ বদলানোর আগে আপনার ডাক্তারকে জিজ্ঞাসা করুন। খাবার আর হাঁটা কীভাবে আপনার সুগার বদলায়, তা আমি দেখাতে পারি।",
        "kn-IN": "ಇನ್ಸುಲಿನ್ ಅಥವಾ ಔಷಧದ ಪ್ರಮಾಣದ ಬಗ್ಗೆ ನಾನು ಸಲಹೆ ನೀಡಲಾರೆ. ಯಾವುದೇ ಔಷಧ ಬದಲಿಸುವ ಮೊದಲು ನಿಮ್ಮ ವೈದ್ಯರನ್ನು ಕೇಳಿ. ಆಹಾರ ಮತ್ತು ನಡಿಗೆ ನಿಮ್ಮ ಸಕ್ಕರೆಯನ್ನು ಹೇಗೆ ಬದಲಿಸುತ್ತವೆ ಎಂದು ನಾನು ತೋರಿಸಬಲ್ಲೆ.",
    },
    "emergency": {
        "en-IN": "This may be an emergency. Get medical help now: call 108 or go to the nearest hospital. If you are awake and can swallow and think your sugar is low, take something sugary like juice. Do not stay alone.",
        "hi-IN": "यह आपातकाल हो सकता है। तुरंत मदद लें: 108 पर कॉल करें या नज़दीकी अस्पताल जाएँ। अगर आप होश में हैं, निगल सकते हैं और लगता है कि शुगर कम है, तो जूस जैसी कोई मीठी चीज़ लें। अकेले न रहें।",
        "bn-IN": "এটা জরুরি অবস্থা হতে পারে। এখনই সাহায্য নিন: 108-এ ফোন করুন বা কাছের হাসপাতালে যান। আপনি সজাগ থাকলে, গিলতে পারলে এবং সুগার কম মনে হলে জুসের মতো মিষ্টি কিছু খান। একা থাকবেন না।",
        "kn-IN": "ಇದು ತುರ್ತು ಸ್ಥಿತಿ ಆಗಿರಬಹುದು. ಈಗಲೇ ಸಹಾಯ ಪಡೆಯಿರಿ: 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ. ನೀವು ಎಚ್ಚರವಾಗಿದ್ದು, ನುಂಗಬಲ್ಲಿರಾದರೆ ಮತ್ತು ಸಕ್ಕರೆ ಕಡಿಮೆ ಎನಿಸಿದರೆ, ಜ್ಯೂಸ್‌ನಂತಹ ಸಿಹಿ ಏನಾದರೂ ಸೇವಿಸಿ. ಒಬ್ಬರೇ ಇರಬೇಡಿ.",
    },
    "diagnosis": {
        "en-IN": "I can't diagnose illnesses. Please talk to your doctor about this. I can help you understand your glucose twin.",
        "hi-IN": "मैं बीमारी का निदान नहीं कर सकता। कृपया इस बारे में अपने डॉक्टर से बात करें। मैं आपके ग्लूकोज़ ट्विन को समझने में मदद कर सकता हूँ।",
        "bn-IN": "আমি রোগ নির্ণয় করতে পারি না। এ বিষয়ে আপনার ডাক্তারের সঙ্গে কথা বলুন। আপনার গ্লুকোজ টুইন বুঝতে আমি সাহায্য করতে পারি।",
        "kn-IN": "ನಾನು ಕಾಯಿಲೆಯನ್ನು ನಿರ್ಣಯಿಸಲಾರೆ. ದಯವಿಟ್ಟು ಈ ಬಗ್ಗೆ ನಿಮ್ಮ ವೈದ್ಯರೊಂದಿಗೆ ಮಾತನಾಡಿ. ನಿಮ್ಮ ಗ್ಲೂಕೋಸ್ ಟ್ವಿನ್ ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
    },
    "out_of_scope": {
        "en-IN": "I can only help with your glucose twin: forecasts, meals, walks and when to check. For anything else, please ask someone else.",
        "hi-IN": "मैं केवल आपके ग्लूकोज़ ट्विन में मदद कर सकता हूँ: अनुमान, भोजन, टहलना और कब जाँच करें। बाकी बातों के लिए किसी और से पूछें।",
        "bn-IN": "আমি শুধু আপনার গ্লুকোজ টুইন নিয়ে সাহায্য করতে পারি: পূর্বাভাস, খাবার, হাঁটা আর কখন মাপবেন। অন্য বিষয়ে অন্য কাউকে জিজ্ঞাসা করুন।",
        "kn-IN": "ನಾನು ನಿಮ್ಮ ಗ್ಲೂಕೋಸ್ ಟ್ವಿನ್ ಬಗ್ಗೆ ಮಾತ್ರ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ: ಮುನ್ಸೂಚನೆ, ಊಟ, ನಡಿಗೆ ಮತ್ತು ಯಾವಾಗ ಪರೀಕ್ಷಿಸಬೇಕು. ಬೇರೆ ವಿಷಯಗಳಿಗೆ ಬೇರೆಯವರನ್ನು ಕೇಳಿ.",
    },
    "hypo": {
        "en-IN": "A reading of {value} is low (below 70). Take something sugary now, like half a glass of fruit juice or a spoon of sugar in water, and check again in 15 minutes. If it stays low or you feel unwell, call 108. Please tell your doctor about low readings.",
        "hi-IN": "{value} की रीडिंग कम है (70 से नीचे)। अभी कुछ मीठा लें, जैसे आधा गिलास फलों का जूस या पानी में एक चम्मच चीनी, और 15 मिनट बाद फिर जाँचें। शुगर कम ही रहे या तबीयत ठीक न लगे तो 108 पर कॉल करें। कम रीडिंग के बारे में अपने डॉक्टर को ज़रूर बताएँ।",
        "bn-IN": "{value} রিডিংটা কম (70-এর নিচে)। এখনই মিষ্টি কিছু খান, যেমন আধ গ্লাস ফলের রস বা জলে এক চামচ চিনি, আর 15 মিনিট পরে আবার মাপুন। সুগার কম থাকলে বা শরীর খারাপ লাগলে 108-এ ফোন করুন। কম রিডিংয়ের কথা আপনার ডাক্তারকে জানান।",
        "kn-IN": "{value} ರೀಡಿಂಗ್ ಕಡಿಮೆ ಇದೆ (70 ಕ್ಕಿಂತ ಕೆಳಗೆ). ಈಗಲೇ ಸಿಹಿ ಏನಾದರೂ ಸೇವಿಸಿ, ಉದಾಹರಣೆಗೆ ಅರ್ಧ ಲೋಟ ಹಣ್ಣಿನ ರಸ ಅಥವಾ ನೀರಿನಲ್ಲಿ ಒಂದು ಚಮಚ ಸಕ್ಕರೆ, ಮತ್ತು 15 ನಿಮಿಷದ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ. ಸಕ್ಕರೆ ಕಡಿಮೆಯೇ ಇದ್ದರೆ ಅಥವಾ ಹುಷಾರಿಲ್ಲ ಎನಿಸಿದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ. ಕಡಿಮೆ ರೀಡಿಂಗ್ ಬಗ್ಗೆ ನಿಮ್ಮ ವೈದ್ಯರಿಗೆ ತಿಳಿಸಿ.",
    },
    "hyper": {
        "en-IN": "A reading of {value} is very high. Drink some water, check again in a while, and test for ketones if you can. If it stays above 300, or you have vomiting, trouble breathing or drowsiness, call 108 or see a doctor today. Do not change any medicine without your doctor.",
        "hi-IN": "{value} की रीडिंग बहुत ज़्यादा है। थोड़ा पानी पिएँ, कुछ देर बाद फिर जाँचें, और हो सके तो कीटोन की जाँच करें। अगर शुगर 300 से ऊपर ही रहे, या उल्टी, साँस लेने में तकलीफ़ या बहुत नींद आए, तो 108 पर कॉल करें या आज ही डॉक्टर को दिखाएँ। डॉक्टर से पूछे बिना कोई दवा न बदलें।",
        "bn-IN": "{value} রিডিংটা খুব বেশি। একটু জল খান, কিছুক্ষণ পরে আবার মাপুন, আর পারলে কিটোন পরীক্ষা করুন। সুগার 300-এর ওপরে থাকলে, বা বমি, শ্বাসকষ্ট বা খুব ঘুম ঘুম ভাব হলে 108-এ ফোন করুন বা আজই ডাক্তার দেখান। ডাক্তারকে না জিজ্ঞেস করে কোনো ওষুধ বদলাবেন না।",
        "kn-IN": "{value} ರೀಡಿಂಗ್ ತುಂಬಾ ಹೆಚ್ಚು ಇದೆ. ಸ್ವಲ್ಪ ನೀರು ಕುಡಿಯಿರಿ, ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ, ಸಾಧ್ಯವಾದರೆ ಕೀಟೋನ್ ಪರೀಕ್ಷೆ ಮಾಡಿ. ಸಕ್ಕರೆ 300 ಕ್ಕಿಂತ ಹೆಚ್ಚೇ ಇದ್ದರೆ, ಅಥವಾ ವಾಂತಿ, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ ತುಂಬಾ ಮಂಪರು ಇದ್ದರೆ, 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಇಂದೇ ವೈದ್ಯರನ್ನು ಕಾಣಿ. ವೈದ್ಯರನ್ನು ಕೇಳದೆ ಯಾವುದೇ ಔಷಧ ಬದಲಿಸಬೇಡಿ.",
    },
    "reading_noted": {
        "en-IN": "I have added this reading to your twin.",
        "hi-IN": "मैंने यह रीडिंग आपके ट्विन में जोड़ दी है।",
        "bn-IN": "এই রিডিংটা আপনার টুইনে যোগ করেছি।",
        "kn-IN": "ಈ ರೀಡಿಂಗ್ ಅನ್ನು ನಿಮ್ಮ ಟ್ವಿನ್‌ಗೆ ಸೇರಿಸಿದ್ದೇನೆ.",
    },
    "reading_pending": {
        "en-IN": "Confirm below if you want me to add this reading to your twin.",
        "hi-IN": "अगर आप चाहते हैं कि मैं यह रीडिंग आपके ट्विन में जोड़ूँ, तो नीचे पुष्टि करें।",
        "bn-IN": "এই রিডিংটা আপনার টুইনে যোগ করতে চাইলে নিচে নিশ্চিত করুন।",
        "kn-IN": "ಈ ರೀಡಿಂಗ್ ಅನ್ನು ನಿಮ್ಮ ಟ್ವಿನ್‌ಗೆ ಸೇರಿಸಬೇಕಾದರೆ ಕೆಳಗೆ ಖಚಿತಪಡಿಸಿ.",
    },
    "high": {
        "en-IN": "A reading of {value} is high (above 250). Drink some water, avoid sugary food and drinks, and check again in 2 to 4 hours. If your readings stay above 250, tell your doctor.",
        "hi-IN": "{value} की रीडिंग ज़्यादा है (250 से ऊपर)। थोड़ा पानी पिएँ, मीठा खाना और मीठे पेय न लें, और 2 से 4 घंटे बाद फिर जाँचें। अगर रीडिंग 250 से ऊपर ही रहे, तो अपने डॉक्टर को बताएँ।",
        "bn-IN": "{value} রিডিংটা বেশি (250-এর ওপরে)। একটু জল খান, মিষ্টি খাবার ও মিষ্টি পানীয় এড়িয়ে চলুন, আর 2 থেকে 4 ঘণ্টা পরে আবার মাপুন। রিডিং 250-এর ওপরে থাকলে আপনার ডাক্তারকে জানান।",
        "kn-IN": "{value} ರೀಡಿಂಗ್ ಹೆಚ್ಚಾಗಿದೆ (250 ಕ್ಕಿಂತ ಹೆಚ್ಚು). ಸ್ವಲ್ಪ ನೀರು ಕುಡಿಯಿರಿ, ಸಿಹಿ ಆಹಾರ ಮತ್ತು ಸಿಹಿ ಪಾನೀಯ ಬೇಡ, ಮತ್ತು 2 ರಿಂದ 4 ಗಂಟೆಗಳ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ. ರೀಡಿಂಗ್ 250 ಕ್ಕಿಂತ ಹೆಚ್ಚೇ ಇದ್ದರೆ ನಿಮ್ಮ ವೈದ್ಯರಿಗೆ ತಿಳಿಸಿ.",
    },
    "ok": {
        "en-IN": "No urgent action is needed for this reading.",
        "hi-IN": "इस रीडिंग के लिए तुरंत कुछ करने की ज़रूरत नहीं है।",
        "bn-IN": "এই রিডিংয়ের জন্য এখনই কিছু করার দরকার নেই।",
        "kn-IN": "ಈ ರೀಡಿಂಗ್‌ಗಾಗಿ ತಕ್ಷಣ ಏನೂ ಮಾಡಬೇಕಾಗಿಲ್ಲ.",
    },
}

# Titles and short action lists of the shared reading-safety policy (``assess_reading``), per level.
READING_TITLES = {
    "ok": {"en-IN": "Reading recorded", "hi-IN": "रीडिंग दर्ज हुई", "bn-IN": "রিডিং নেওয়া হয়েছে",
           "kn-IN": "ರೀಡಿಂಗ್ ದಾಖಲಾಗಿದೆ"},
    "low": {"en-IN": "Low glucose", "hi-IN": "शुगर कम है", "bn-IN": "সুগার কম", "kn-IN": "ಸಕ್ಕರೆ ಕಡಿಮೆ ಇದೆ"},
    "very_low": {"en-IN": "Very low glucose: possible emergency", "hi-IN": "शुगर बहुत कम है: आपातकाल हो सकता है",
                 "bn-IN": "সুগার খুব কম: জরুরি অবস্থা হতে পারে", "kn-IN": "ಸಕ್ಕರೆ ತುಂಬಾ ಕಡಿಮೆ: ತುರ್ತು ಸ್ಥಿತಿ ಇರಬಹುದು"},
    "high": {"en-IN": "High glucose", "hi-IN": "शुगर ज़्यादा है", "bn-IN": "সুগার বেশি", "kn-IN": "ಸಕ್ಕರೆ ಹೆಚ್ಚಾಗಿದೆ"},
    "very_high": {"en-IN": "Very high glucose", "hi-IN": "शुगर बहुत ज़्यादा है", "bn-IN": "সুগার খুব বেশি",
                  "kn-IN": "ಸಕ್ಕರೆ ತುಂಬಾ ಹೆಚ್ಚಾಗಿದೆ"},
    "emergency": {"en-IN": "Possible emergency", "hi-IN": "आपातकाल हो सकता है", "bn-IN": "জরুরি অবস্থা হতে পারে",
                  "kn-IN": "ತುರ್ತು ಸ್ಥಿತಿ ಇರಬಹುದು"},
}
READING_ACTIONS = {
    "low": {"en-IN": ["Take something sugary now (half a glass of juice or a spoon of sugar in water)",
                      "Check again in 15 minutes", "Call 108 if it stays low or you feel unwell"],
            "hi-IN": ["अभी कुछ मीठा लें (आधा गिलास जूस या पानी में एक चम्मच चीनी)", "15 मिनट बाद फिर जाँचें",
                      "शुगर कम ही रहे या तबीयत ठीक न लगे तो 108 पर कॉल करें"],
            "bn-IN": ["এখনই মিষ্টি কিছু খান (আধ গ্লাস রস বা জলে এক চামচ চিনি)", "15 মিনিট পরে আবার মাপুন",
                      "কম থাকলে বা শরীর খারাপ লাগলে 108-এ ফোন করুন"],
            "kn-IN": ["ಈಗಲೇ ಸಿಹಿ ಏನಾದರೂ ಸೇವಿಸಿ (ಅರ್ಧ ಲೋಟ ರಸ ಅಥವಾ ನೀರಿನಲ್ಲಿ ಒಂದು ಚಮಚ ಸಕ್ಕರೆ)",
                      "15 ನಿಮಿಷದ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ", "ಕಡಿಮೆಯೇ ಇದ್ದರೆ ಅಥವಾ ಹುಷಾರಿಲ್ಲದಿದ್ದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ"]},
    "emergency": {"en-IN": ["Call 108 or go to the nearest hospital now",
                            "If awake and able to swallow, take something sugary", "Do not stay alone"],
                  "hi-IN": ["अभी 108 पर कॉल करें या नज़दीकी अस्पताल जाएँ", "होश में हों और निगल सकें तो कुछ मीठा लें",
                            "अकेले न रहें"],
                  "bn-IN": ["এখনই 108-এ ফোন করুন বা কাছের হাসপাতালে যান", "সজাগ থাকলে ও গিলতে পারলে মিষ্টি কিছু খান",
                            "একা থাকবেন না"],
                  "kn-IN": ["ಈಗಲೇ 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ",
                            "ಎಚ್ಚರವಾಗಿದ್ದು ನುಂಗಬಲ್ಲಿರಾದರೆ ಸಿಹಿ ಏನಾದರೂ ಸೇವಿಸಿ", "ಒಬ್ಬರೇ ಇರಬೇಡಿ"]},
    "high": {"en-IN": ["Drink some water", "Check again in 2 to 4 hours", "Tell your doctor if it stays above 250"],
             "hi-IN": ["थोड़ा पानी पिएँ", "2 से 4 घंटे बाद फिर जाँचें", "250 से ऊपर ही रहे तो डॉक्टर को बताएँ"],
             "bn-IN": ["একটু জল খান", "2 থেকে 4 ঘণ্টা পরে আবার মাপুন", "250-এর ওপরে থাকলে ডাক্তারকে জানান"],
             "kn-IN": ["ಸ್ವಲ್ಪ ನೀರು ಕುಡಿಯಿರಿ", "2 ರಿಂದ 4 ಗಂಟೆಗಳ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ",
                       "250 ಕ್ಕಿಂತ ಹೆಚ್ಚೇ ಇದ್ದರೆ ವೈದ್ಯರಿಗೆ ತಿಳಿಸಿ"]},
    "very_high": {"en-IN": ["Drink some water", "Test for ketones if you can",
                            "Call 108 or see a doctor today if you are vomiting, breathless or drowsy"],
                  "hi-IN": ["थोड़ा पानी पिएँ", "हो सके तो कीटोन जाँचें",
                            "उल्टी, साँस की तकलीफ़ या बहुत नींद हो तो 108 पर कॉल करें या आज ही डॉक्टर को दिखाएँ"],
                  "bn-IN": ["একটু জল খান", "পারলে কিটোন পরীক্ষা করুন",
                            "বমি, শ্বাসকষ্ট বা খুব ঘুম ঘুম ভাব হলে 108-এ ফোন করুন বা আজই ডাক্তার দেখান"],
                  "kn-IN": ["ಸ್ವಲ್ಪ ನೀರು ಕುಡಿಯಿರಿ", "ಸಾಧ್ಯವಾದರೆ ಕೀಟೋನ್ ಪರೀಕ್ಷೆ ಮಾಡಿ",
                            "ವಾಂತಿ, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ ಮಂಪರು ಇದ್ದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಇಂದೇ ವೈದ್ಯರನ್ನು ಕಾಣಿ"]},
}

# Reading levels of the shared policy (International Consensus / ADA glucose levels):
# level 2 hypoglycaemia < 54, level 1 < 70; level 2 hyperglycaemia > 250; > 300 very high (ketone check).
VERY_LOW_BELOW = 54.0
LOW_BELOW = 70.0
HIGH_ABOVE = 250.0
VERY_HIGH_ABOVE = 300.0


def _norm(s: str, lower: bool = True) -> str:
    """Drop nukta and zero-width joiners, fold Devanagari chandrabindu into anusvara (काँप == कांप,
    डोज़ == डोज), unify Indic digits; lowercase text.

    Patterns are normalised with ``lower=False`` (lowercasing would turn ``\\S`` into ``\\s``)."""
    t = unicodedata.normalize("NFD", s.lower() if lower else s)
    t = t.replace("़", "").replace("়", "").replace("಼", "")
    t = t.replace("ँ", "ं")  # Devanagari chandrabindu -> anusvara (Bengali ঁ is kept: কাঁপ != কাপ)
    t = t.replace("‌", "").replace("‍", "")
    return normalise_digits(unicodedata.normalize("NFC", t))


@lru_cache(maxsize=512)
def _compiled(p: str) -> re.Pattern[str]:
    return re.compile(_norm(p, lower=False), re.I)


def _any(patterns: list[str], text: str, normalised: bool = False) -> bool:
    t = text if normalised else _norm(text)
    return any(_compiled(p).search(t) for p in patterns)


_NUM_RE = re.compile(r"(?<![\d.:,/])" + _NUM + r"(?![\d.,/]\d)")
_WORD_RE = re.compile(GLUCOSE_WORDS, re.I)
_UNIT_AFTER = re.compile(r"^\s*(mg\s*/?\s*dl|mgdl|mg%|mmol)", re.I)
_BARE = re.compile(r"^\s*(?:it'?s|its|is)?\s*" + _NUM + r"\s*(?:mg\s*/?\s*dl|mgdl|mmol(?:\s*/\s*l)?)?\s*[.!?।]?\s*$", re.I)


def glucose_values(text: str) -> list[float]:
    """Glucose values (mg/dL) the user reports in ``text``, in order.

    Counted: a number with mg/dL or mmol/L after it; a number up to ~25 characters after a
    sugar / glucose / reading / meter word in any of the four languages (but not "above 180",
    "in 30 minutes", "70 to 180", "180 से ऊपर" ...); a message that is only a number. mmol/L
    values (with the unit, or a decimal below 35) are converted (x 18)."""
    t = _norm(text)
    bare = _BARE.match(t)
    if bare:
        v0 = _to_mgdl(bare.group(1), t[bare.end(1):])
        return [v0] if v0 is not None else []
    out: list[float] = []
    for m in _NUM_RE.finditer(t):
        after = t[m.end():m.end() + 30]
        if _UNIT_AFTER.match(after):
            v = _to_mgdl(m.group(1), after)
        else:
            if _NOT_A_READING_AFTER.match(after):
                continue
            window = t[max(0, m.start() - 40):m.start()]
            words = list(_WORD_RE.finditer(window))
            if not words:
                continue
            gap = window[words[-1].end():]
            if len(gap) > 25 or re.search(r"[\d\n]", gap) or _NOT_A_READING_BEFORE.search(gap):
                continue
            v = _to_mgdl(m.group(1), after)
        if v is not None:
            out.append(v)
    return out


def _to_mgdl(num: str, context: str) -> float | None:
    v = float(num)
    if "mmol" in context[:12] or ("." in num and v < 35):
        v = round(v * 18.0, 0)
    return v if 20 <= v <= 700 else None


def _low_groups(t: str) -> set[str]:
    return {g for g, pats in LOW_SYMPTOMS.items() if _any(pats, t, normalised=True)}


@dataclass
class Assessment:
    """Deterministic safety verdict for one user message (rules only, before any LLM)."""

    kind: str | None = None          # "emergency" | "dose" | "diagnosis" | None
    reason: str | None = None        # why (e.g. "glucose_below_54", "low_with_symptoms", "symptoms")
    glucose: float | None = None     # first reported glucose value (mg/dL), if any
    glycaemia: str | None = None     # "hypo" (< 70) | "hyper" (> 250) | None
    values: list[float] = field(default_factory=list)


def assess(text: str, use_values: bool = True) -> Assessment:
    """Emergency first (reported values + symptoms), then dose, then diagnosis.

    * any reported glucose < 54, or < 70 with a low-sugar symptom, or > 400 with vomiting /
      breathing / ketone / drowsiness words -> emergency;
    * severe symptoms alone (fainting, seizure, chest pain, can't breathe, trembling, or two
      different low-sugar symptoms such as sweating + dizziness) -> emergency;
    * otherwise a reading < 70 or > 250 is flagged as ``glycaemia`` so the agent always shows the
      shared reading-safety message (``assess_reading``) with it.

    ``use_values=False`` ignores numbers (for prompt-injection text, whose numbers are not readings)."""
    t = _norm(text)
    vals = glucose_values(text) if use_values else []
    g = vals[0] if vals else None
    a = Assessment(glucose=g, values=vals)
    low = _low_groups(t)
    if any(v < 54 for v in vals):
        a.kind, a.reason = "emergency", "glucose_below_54"
    elif any(v < 70 for v in vals) and low:
        a.kind, a.reason = "emergency", "low_with_symptoms"
    elif any(v > 400 for v in vals) and _any(HIGH_SYMPTOMS, t, normalised=True):
        a.kind, a.reason = "emergency", "high_with_symptoms"
    elif _any(EMERGENCY_PATTERNS, t, normalised=True):
        a.kind, a.reason = "emergency", "symptoms"
    elif low & set(SINGLE_LOW_GROUPS) or len(low) >= 2:
        a.kind, a.reason = "emergency", "low_symptoms"
    elif _any(DOSE_PATTERNS, t, normalised=True):
        a.kind, a.reason = "dose", "dose"
    elif _any(DIAGNOSIS_PATTERNS, t, normalised=True):
        a.kind, a.reason = "diagnosis", "diagnosis"
    if vals:
        lo, hi = min(vals), max(vals)
        a.glycaemia = "hypo" if lo < LOW_BELOW else "hyper" if hi > HIGH_ABOVE else None
    return a


def classify(text: str) -> str | None:
    """Return 'emergency' | 'dose' | 'diagnosis' | None (rules only, run before any LLM)."""
    return assess(text).kind


def is_injection(text: str) -> bool:
    return _any(INJECTION_PATTERNS, text)


# ----------------------------------------------------------------------------- output policy
# Constrained medication policy for GENERATED text (LLM drafts): medication content may appear only
# in the fixed, reviewed sentences of this module (e.g. "Do not change any medicine without your
# doctor."). Any other mention of a medicine, insulin, a dose or a dose-like amount - in English,
# romanised Hindi/Bengali/Kannada or Indic script, negated or not - makes the draft unsafe, and the
# agent falls back to a deterministic template.
MED_TERMS = [
    # English drug names (generic / Indian brands) and generic medication words
    r"\b(?:insulin\w*|insul[ie]n|inslin|metformin\w*|glycomet|glucophage|glimepiride|amaryl|gliclazide|glipizide|"
    r"glibenclamide|sulfonylureas?|sitagliptin|januvia|vildagliptin|galvus|teneligliptin|linagliptin|"
    r"empagliflozin|jardiance|dapagliflozin|forxiga|canagliflozin|pioglitazone|acarbose|voglibose|semaglutide|"
    r"ozempic|rybelsus|wegovy|liraglutide|dulaglutide|trulicity|tirzepatide|mounjaro|lantus|levemir|tresiba|"
    r"basalog|glargine|degludec|novorapid|humalog|humulin|mixtard|actrapid|ryzodeg|statins?|atorvastatin|"
    r"rosuvastatin|telmisartan|amlodipine|aspirin)\b",
    r"\b(?:medicines?|medications?|meds|drugs?|tablets?|tabs?|pills?|capsules?|doses?|dosage|dosing|injections?|"
    r"inject\w*|jabs?|syringe|insulin pen|pen needle)\b",
    # romanised Hindi / Bengali / Kannada
    r"\b(?:dawa|dawai|davai|dawaai|davaai|dawaiyan|davaiyan|goli|goliyan|golee|khuraak|khurak|injection|"
    r"suee|oshudh|osudh|oshud|oushodh|aushadh|oshudher|aushadha|ausadha|maathre|maatre|matre|injekshan)\b",
    # Devanagari / Bengali / Kannada script
    r"(?:इंसुलिन|इन्सुलिन|दवा|दवाई|दवाइयां|दवाइयाँ|गोली|गोलियां|खुराक|डोज|मेटफॉर्मिन|मेटफोर्मिन|इंजेक्शन|टैबलेट|यूनिट)",
    r"(?:ইনসুলিন|ওষুধ|ঔষধ|ট্যাবলেট|ডোজ|মেটফরমিন|মেটফর্মিন|ইউনিট|ইনজেকশন|ইঞ্জেকশন)",
    r"(?:ಇನ್ಸುಲಿನ್|ಔಷಧ|ಮಾತ್ರೆ|ಡೋಸ್|ಮೆಟ್ಫಾರ್ಮಿನ್|ಮೆಟ್‌ಫಾರ್ಮಿನ್|ಯೂನಿಟ್|ಇಂಜೆಕ್ಷನ್)",
]
# A dose-like amount even without a drug word ("add 4 u", "10 IU", "500 mg" - but not "180 mg/dL").
DOSE_AMOUNT = (r"\d+(?:[.,]\d+)?\s*(?:(?:more|extra|additional|fewer|less|और|আরও|ಹೆಚ್ಚು)\s+)?"
               r"(?:units?\b|u\b|iu\b|i\.u\.|mcg\b|µg|mg\b(?!\s*/?\s*d\s*l)(?!\s*%)|"
               r"यूनिट|ইউনিট|ಯೂನಿಟ್|मिलीग्राम|মিলিগ্রাম|ಮಿಲಿಗ್ರಾಂ)")
# Physiology terms that contain a drug word but are not medication content.
_PHYSIOLOGY = [r"\binsulin (?:sensitivity|resistance|response|action)\b", r"इंसुलिन (?:संवेदनशीलता|प्रतिरोध)",
               r"ইনসুলিন (?:সংবেদনশীলতা|প্রতিরোধ)", r"ಇನ್ಸುಲಿನ್ (?:ಸಂವೇದನೆ|ಪ್ರತಿರೋಧ)"]
# Reviewed referral phrasings (English) that may mention medicine without advising on it.
_SAFE_REFERRALS = [
    r"(?:please )?(?:ask|talk to|check with|consult|speak (?:to|with)) (?:your |a )?doctor (?:before|about) "
    r"(?:changing|stopping|starting|skipping|adjusting) (?:any|your) (?:medicines?|medications?|insulin)",
    r"(?:do not|don'?t|never) (?:change|stop|skip|start|adjust|alter) (?:any|your) (?:medicines?|medications?|"
    r"insulin|tablets?) without (?:asking |talking to )?(?:your |a )?doctor",
    r"i can'?t advise on (?:insulin|medicine)(?: or (?:insulin|medicine))? doses",
    r"i cannot advise on (?:insulin|medicine)(?: or (?:insulin|medicine))? doses",
]
_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+")


@lru_cache(maxsize=1)
def _safe_sentence_res() -> tuple[re.Pattern[str], ...]:
    """Every sentence of the fixed safety messages (all languages), as normalised regexes."""
    out: list[re.Pattern[str]] = []
    for msgs in MESSAGES.values():
        for txt in msgs.values():
            for sent in _SENT_SPLIT.split(txt):
                sent = sent.strip()
                if not sent:
                    continue
                pat = re.escape(_norm(sent)).replace(re.escape("{value}"), r"\d+(?:\.\d+)?")
                out.append(re.compile(pat))
    out += [_compiled(p) for p in _SAFE_REFERRALS + _PHYSIOLOGY]
    return tuple(out)


def medication_mentions(text: str) -> list[str]:
    """Medication terms / dose amounts left in ``text`` after removing reviewed safe sentences."""
    t = _norm(text)
    for rx in _safe_sentence_res():
        t = rx.sub(" ", t)
    hits = [m.group(0) for p in MED_TERMS for m in _compiled(p).finditer(t)]
    hits += [m.group(0) for m in _compiled(DOSE_AMOUNT).finditer(t)]
    return hits


def output_unsafe(text: str) -> bool:
    """Last line of defence on generated text: medication content only in reviewed wording."""
    return bool(medication_mentions(text))


# ----------------------------------------------------------------------------- reading policy
def reading_level(value: float) -> str:
    v = float(value)
    if v < VERY_LOW_BELOW:
        return "very_low"
    if v < LOW_BELOW:
        return "low"
    if v > VERY_HIGH_ABOVE:
        return "very_high"
    if v > HIGH_ABOVE:
        return "high"
    return "ok"


def assess_reading(value: float, symptoms_text: str | None = None, lang: str = "en-IN") -> dict:
    """THE shared safety policy for a measured glucose value (mg/dL), used by manual entry, chat,
    chat confirmations and the replay reveal.

    Returns ``{level, emergency, title, message, actions, reason}`` localised to ``lang``.
    ``emergency``: a value below 54; below 70 with a low-sugar symptom; above 400 with vomiting /
    breathing / ketone / drowsiness words; or severe symptoms on their own in ``symptoms_text``."""
    lang = lang if lang in ("en-IN", "hi-IN", "bn-IN", "kn-IN") else "en-IN"
    v = float(value)
    level = reading_level(v)
    t = _norm(symptoms_text or "")
    low_sym = bool(_low_groups(t)) if t else False
    emergency, reason = False, None
    if level == "very_low":
        emergency, reason = True, "glucose_below_54"
    elif level == "low" and low_sym:
        emergency, reason = True, "low_with_symptoms"
    elif v > 400 and t and _any(HIGH_SYMPTOMS, t, normalised=True):
        emergency, reason = True, "high_with_symptoms"
    elif t and _any(EMERGENCY_PATTERNS, t, normalised=True):
        emergency, reason = True, "symptoms"
    vr = int(round(v))
    if emergency:
        msg_kind, title_kind, act_kind = "emergency", ("very_low" if level == "very_low" else "emergency"), "emergency"
    else:
        msg_kind = {"low": "hypo", "very_high": "hyper", "high": "high", "ok": "ok"}[level]
        title_kind, act_kind = level, level
    msg = message(msg_kind, lang, value=vr) if msg_kind in ("hypo", "hyper", "high") else message(msg_kind, lang)
    acts = READING_ACTIONS.get(act_kind, {})
    return {"level": level, "emergency": emergency, "title": READING_TITLES[title_kind][lang], "message": msg,
            "actions": list(acts.get(lang, acts.get("en-IN", []))), "reason": reason or (None if level == "ok" else f"{level}_reading"),
            "value": round(v, 1)}


def message(kind: str, lang: str, **kw: object) -> str:
    tpl = MESSAGES[kind].get(lang, MESSAGES[kind]["en-IN"])
    return tpl.format(**kw) if kw else tpl
