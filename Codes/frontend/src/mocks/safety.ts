// Offline stand-in for the backend's shared safety policy (pratifalan/agent/safety.py
// assess_reading). Same thresholds as the chat rules: < 54 is an emergency, < 70 is low,
// > 300 is high and > 400 very high. Used only in offline mock mode.
import type { Lang, Safety, SafetyLevel } from "@/api/types";

const TEXT: Record<SafetyLevel, Record<Lang, { title: string; message: string; actions: string[] }>> = {
  ok: {
    "en-IN": { title: "Reading added", message: "This reading is not in a danger zone.", actions: [] },
    "hi-IN": { title: "रीडिंग जुड़ गई", message: "यह रीडिंग खतरे वाले दायरे में नहीं है।", actions: [] },
    "bn-IN": { title: "রিডিং যোগ হয়েছে", message: "এই রিডিং বিপদের সীমায় নেই।", actions: [] },
    "kn-IN": { title: "ರೀಡಿಂಗ್ ಸೇರಿಸಲಾಗಿದೆ", message: "ಈ ರೀಡಿಂಗ್ ಅಪಾಯದ ಮಟ್ಟದಲ್ಲಿ ಇಲ್ಲ.", actions: [] },
  },
  low: {
    "en-IN": { title: "This reading is low", message: "A reading of {v} is below 70. Take something sugary now, like half a glass of fruit juice, and check again in 15 minutes. If it stays low or you feel unwell, call 108.", actions: ["Take 15 g of fast sugar", "Check again in 15 minutes", "Tell your doctor about low readings"] },
    "hi-IN": { title: "यह रीडिंग कम है", message: "{v} की रीडिंग 70 से नीचे है। अभी कुछ मीठा लें, जैसे आधा गिलास फलों का जूस, और 15 मिनट बाद फिर जाँचें। शुगर कम ही रहे या तबीयत ठीक न लगे तो 108 पर कॉल करें।", actions: ["15 ग्राम जल्दी असर करने वाली मीठी चीज़ लें", "15 मिनट बाद फिर जाँचें", "कम रीडिंग के बारे में डॉक्टर को बताएँ"] },
    "bn-IN": { title: "এই রিডিং কম", message: "{v} রিডিংটা 70-এর নিচে। এখনই মিষ্টি কিছু খান, যেমন আধ গ্লাস ফলের রস, আর 15 মিনিট পরে আবার মাপুন। সুগার কম থাকলে বা শরীর খারাপ লাগলে 108-এ ফোন করুন।", actions: ["15 গ্রাম দ্রুত চিনি খান", "15 মিনিট পরে আবার মাপুন", "কম রিডিংয়ের কথা ডাক্তারকে জানান"] },
    "kn-IN": { title: "ಈ ರೀಡಿಂಗ್ ಕಡಿಮೆ ಇದೆ", message: "{v} ರೀಡಿಂಗ್ 70 ಕ್ಕಿಂತ ಕೆಳಗಿದೆ. ಈಗಲೇ ಸಿಹಿ ಏನಾದರೂ ಸೇವಿಸಿ, ಉದಾಹರಣೆಗೆ ಅರ್ಧ ಲೋಟ ಹಣ್ಣಿನ ರಸ, ಮತ್ತು 15 ನಿಮಿಷದ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ. ಕಡಿಮೆಯೇ ಇದ್ದರೆ ಅಥವಾ ಹುಷಾರಿಲ್ಲ ಎನಿಸಿದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ.", actions: ["15 ಗ್ರಾಂ ಬೇಗ ಕೆಲಸ ಮಾಡುವ ಸಕ್ಕರೆ ಸೇವಿಸಿ", "15 ನಿಮಿಷದ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ", "ಕಡಿಮೆ ರೀಡಿಂಗ್ ಬಗ್ಗೆ ವೈದ್ಯರಿಗೆ ತಿಳಿಸಿ"] },
  },
  very_low: {
    "en-IN": { title: "This may be an emergency", message: "A reading of {v} is dangerously low. Get help now: call 108. If you are awake and can swallow, take something sugary like juice. Do not stay alone.", actions: ["Call 108", "Take something sugary if you can swallow", "Do not stay alone"] },
    "hi-IN": { title: "यह आपातकाल हो सकता है", message: "{v} की रीडिंग खतरनाक रूप से कम है। तुरंत मदद लें: 108 पर कॉल करें। अगर आप होश में हैं और निगल सकते हैं, तो जूस जैसी कोई मीठी चीज़ लें। अकेले न रहें।", actions: ["108 पर कॉल करें", "निगल सकें तो कुछ मीठा लें", "अकेले न रहें"] },
    "bn-IN": { title: "এটা জরুরি অবস্থা হতে পারে", message: "{v} রিডিংটা বিপজ্জনকভাবে কম। এখনই সাহায্য নিন: 108-এ ফোন করুন। সজাগ থাকলে এবং গিলতে পারলে জুসের মতো মিষ্টি কিছু খান। একা থাকবেন না।", actions: ["108-এ ফোন করুন", "গিলতে পারলে মিষ্টি কিছু খান", "একা থাকবেন না"] },
    "kn-IN": { title: "ಇದು ತುರ್ತು ಸ್ಥಿತಿ ಆಗಿರಬಹುದು", message: "{v} ರೀಡಿಂಗ್ ಅಪಾಯಕಾರಿಯಾಗಿ ಕಡಿಮೆ ಇದೆ. ಈಗಲೇ ಸಹಾಯ ಪಡೆಯಿರಿ: 108 ಗೆ ಕರೆ ಮಾಡಿ. ಎಚ್ಚರವಾಗಿದ್ದು ನುಂಗಬಲ್ಲಿರಾದರೆ ಜ್ಯೂಸ್‌ನಂತಹ ಸಿಹಿ ಸೇವಿಸಿ. ಒಬ್ಬರೇ ಇರಬೇಡಿ.", actions: ["108 ಗೆ ಕರೆ ಮಾಡಿ", "ನುಂಗಬಲ್ಲಿರಾದರೆ ಸಿಹಿ ಸೇವಿಸಿ", "ಒಬ್ಬರೇ ಇರಬೇಡಿ"] },
  },
  high: {
    "en-IN": { title: "This reading is very high", message: "A reading of {v} is above 300. Drink some water, check again in a while and test for ketones if you can. If it stays above 300, or you have vomiting, trouble breathing or drowsiness, call 108 or see a doctor today.", actions: ["Drink water", "Check again in a while", "See a doctor today if it stays high"] },
    "hi-IN": { title: "यह रीडिंग बहुत ज़्यादा है", message: "{v} की रीडिंग 300 से ऊपर है। थोड़ा पानी पिएँ, कुछ देर बाद फिर जाँचें और हो सके तो कीटोन जाँचें। 300 से ऊपर ही रहे, या उल्टी, साँस की तकलीफ़ या बहुत नींद आए, तो 108 पर कॉल करें या आज ही डॉक्टर को दिखाएँ।", actions: ["पानी पिएँ", "कुछ देर बाद फिर जाँचें", "ज़्यादा ही रहे तो आज डॉक्टर को दिखाएँ"] },
    "bn-IN": { title: "এই রিডিং খুব বেশি", message: "{v} রিডিংটা 300-এর ওপরে। একটু জল খান, কিছুক্ষণ পরে আবার মাপুন আর পারলে কিটোন পরীক্ষা করুন। 300-এর ওপরে থাকলে, বা বমি, শ্বাসকষ্ট বা ঝিমুনি হলে 108-এ ফোন করুন বা আজই ডাক্তার দেখান।", actions: ["জল খান", "কিছুক্ষণ পরে আবার মাপুন", "বেশি থাকলে আজই ডাক্তার দেখান"] },
    "kn-IN": { title: "ಈ ರೀಡಿಂಗ್ ತುಂಬಾ ಹೆಚ್ಚು", message: "{v} ರೀಡಿಂಗ್ 300 ಕ್ಕಿಂತ ಹೆಚ್ಚು. ಸ್ವಲ್ಪ ನೀರು ಕುಡಿಯಿರಿ, ಸ್ವಲ್ಪ ಹೊತ್ತಿನ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ, ಸಾಧ್ಯವಾದರೆ ಕೀಟೋನ್ ಪರೀಕ್ಷಿಸಿ. 300 ಮೀರಿಯೇ ಇದ್ದರೆ, ಅಥವಾ ವಾಂತಿ, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ ಮಂಪರು ಇದ್ದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಇಂದೇ ವೈದ್ಯರನ್ನು ಕಾಣಿ.", actions: ["ನೀರು ಕುಡಿಯಿರಿ", "ಸ್ವಲ್ಪ ಹೊತ್ತಿನ ನಂತರ ಮತ್ತೆ ಪರೀಕ್ಷಿಸಿ", "ಹೆಚ್ಚೇ ಇದ್ದರೆ ಇಂದೇ ವೈದ್ಯರನ್ನು ಕಾಣಿ"] },
  },
  very_high: {
    "en-IN": { title: "This reading is dangerously high", message: "A reading of {v} is above 400. Call 108 or go to a hospital now if you have vomiting, trouble breathing or drowsiness; otherwise see a doctor today. Do not change any medicine without your doctor.", actions: ["Call 108 if you have vomiting, trouble breathing or drowsiness", "See a doctor today", "Drink water"] },
    "hi-IN": { title: "यह रीडिंग खतरनाक रूप से ज़्यादा है", message: "{v} की रीडिंग 400 से ऊपर है। उल्टी, साँस की तकलीफ़ या बहुत नींद हो तो अभी 108 पर कॉल करें या अस्पताल जाएँ; नहीं तो आज ही डॉक्टर को दिखाएँ। डॉक्टर से पूछे बिना कोई दवा न बदलें।", actions: ["उल्टी, साँस की तकलीफ़ या नींद हो तो 108 पर कॉल करें", "आज ही डॉक्टर को दिखाएँ", "पानी पिएँ"] },
    "bn-IN": { title: "এই রিডিং বিপজ্জনকভাবে বেশি", message: "{v} রিডিংটা 400-এর ওপরে। বমি, শ্বাসকষ্ট বা ঝিমুনি থাকলে এখনই 108-এ ফোন করুন বা হাসপাতালে যান; না হলে আজই ডাক্তার দেখান। ডাক্তারকে না জিজ্ঞেস করে কোনো ওষুধ বদলাবেন না।", actions: ["বমি, শ্বাসকষ্ট বা ঝিমুনি হলে 108-এ ফোন করুন", "আজই ডাক্তার দেখান", "জল খান"] },
    "kn-IN": { title: "ಈ ರೀಡಿಂಗ್ ಅಪಾಯಕಾರಿಯಾಗಿ ಹೆಚ್ಚು", message: "{v} ರೀಡಿಂಗ್ 400 ಕ್ಕಿಂತ ಹೆಚ್ಚು. ವಾಂತಿ, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ ಮಂಪರು ಇದ್ದರೆ ಈಗಲೇ 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ; ಇಲ್ಲದಿದ್ದರೆ ಇಂದೇ ವೈದ್ಯರನ್ನು ಕಾಣಿ. ವೈದ್ಯರನ್ನು ಕೇಳದೆ ಯಾವುದೇ ಔಷಧ ಬದಲಿಸಬೇಡಿ.", actions: ["ವಾಂತಿ, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ ಮಂಪರು ಇದ್ದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ", "ಇಂದೇ ವೈದ್ಯರನ್ನು ಕಾಣಿ", "ನೀರು ಕುಡಿಯಿರಿ"] },
  },
};

export function levelFor(mgdl: number): SafetyLevel {
  if (mgdl < 54) return "very_low";
  if (mgdl < 70) return "low";
  if (mgdl > 400) return "very_high";
  if (mgdl > 300) return "high";
  return "ok";
}

export function assessReading(mgdl: number, lang: Lang): Safety {
  const level = levelFor(mgdl);
  const tx = TEXT[level][lang] ?? TEXT[level]["en-IN"];
  const v = String(Math.round(mgdl));
  return { level, emergency: level === "very_low", title: tx.title, message: tx.message.replace("{v}", v), actions: tx.actions };
}
