"""UI labels. Answers themselves are written by the agent in any supported language;
these are only the app's buttons/headings. Missing keys fall back to English."""

T = {
    "en": {
        "tagline": "Your farm advisor — live weather, soil, mandi prices and official crop guides",
        "tab_ask": "🎤 Ask", "tab_farm": "🌦️ My farm", "tab_mandi": "💰 Mandi", "tab_profile": "👤 Profile",
        "ask_voice": "Speak your question", "ask_text": "…or type it here", "ask_btn": "Get advice",
        "examples": "Try asking", "thinking": "Checking weather, crop stage, prices and guides…",
        "verified": "Verified against live data", "not_verified": "Data-only answer",
        "sources": "Sources", "how": "How I got this answer", "english": "English translation",
        "listen": "Listen", "stage": "Crop stage", "days_after": "days after sowing", "to_harvest": "days to harvest",
        "risk_cal": "7-day risk calendar", "no_risks": "No weather risks found for this week.",
        "windows": "What to do this week", "best_spray": "Best spray window", "no_spray": "No good spray day in the next 5 days",
        "water": "Water", "water_need": "Crop will use about {need} mm this week; forecast rain gives about {eff} mm.",
        "harvest": "Dry days for harvest", "soil": "Your soil", "forecast": "Forecast",
        "mandi_today": "Today's mandi prices", "nearest": "Top market", "state_avg": "State average",
        "markets": "Markets reporting", "trend": "Price trend (our daily records)", "history_since": "Records since {d} ({n} days)",
        "no_history": "We save prices every day; the trend appears after a few days of records.",
        "ask_sell": "Should I sell now?", "per_q": "₹/quintal",
        "profile_new": "Set up your farm", "name": "Name (optional)", "language": "Language",
        "place": "Village / town / district", "find": "Find", "use_gps": "Use my location",
        "crops": "Crops", "sowing": "Sowing / transplant date of", "save": "Save profile", "saved": "Saved!",
        "pick_place": "Choose your place", "status": "System status", "usage": "Usage so far",
        "choose_farmer": "Farmer profile", "new_farmer": "➕ New farmer", "data_as_of": "data as of",
        "cached": "cached", "unavailable": "unavailable", "queries": "questions answered", "farmers": "farmers",
    },
    "hi": {
        "tagline": "आपका खेती सलाहकार — लाइव मौसम, मिट्टी, मंडी भाव और सरकारी फसल गाइड",
        "tab_ask": "🎤 पूछें", "tab_farm": "🌦️ मेरा खेत", "tab_mandi": "💰 मंडी", "tab_profile": "👤 प्रोफ़ाइल",
        "ask_voice": "अपना सवाल बोलें", "ask_text": "…या यहाँ लिखें", "ask_btn": "सलाह लें",
        "examples": "ऐसे पूछें", "thinking": "मौसम, फसल की अवस्था, भाव और गाइड देख रहे हैं…",
        "verified": "लाइव डेटा से जाँचा गया", "not_verified": "सिर्फ़ डेटा आधारित उत्तर",
        "sources": "स्रोत", "how": "यह उत्तर कैसे बना", "english": "अंग्रेज़ी अनुवाद",
        "listen": "सुनें", "stage": "फसल की अवस्था", "days_after": "दिन बुवाई के बाद", "to_harvest": "दिन कटाई तक",
        "risk_cal": "7 दिन का जोखिम कैलेंडर", "no_risks": "इस हफ्ते मौसम का कोई जोखिम नहीं मिला।",
        "windows": "इस हफ्ते क्या करें", "best_spray": "छिड़काव का सबसे अच्छा समय", "no_spray": "अगले 5 दिनों में छिड़काव के लिए अच्छा दिन नहीं",
        "water": "पानी", "water_need": "इस हफ्ते फसल लगभग {need} मिमी पानी लेगी; बारिश से लगभग {eff} मिमी मिलेगा।",
        "harvest": "कटाई के लिए सूखे दिन", "soil": "आपकी मिट्टी", "forecast": "मौसम पूर्वानुमान",
        "mandi_today": "आज के मंडी भाव", "nearest": "सबसे ऊँचा बाज़ार", "state_avg": "राज्य औसत",
        "markets": "बाज़ार", "trend": "भाव का रुझान (हमारे रोज़ के रिकॉर्ड)", "history_since": "{d} से रिकॉर्ड ({n} दिन)",
        "no_history": "हम रोज़ भाव सहेजते हैं; कुछ दिनों बाद रुझान दिखेगा।",
        "ask_sell": "क्या अभी बेचूं?", "per_q": "₹/क्विंटल",
        "profile_new": "अपना खेत जोड़ें", "name": "नाम (वैकल्पिक)", "language": "भाषा",
        "place": "गाँव / कस्बा / ज़िला", "find": "खोजें", "use_gps": "मेरी लोकेशन लें",
        "crops": "फसलें", "sowing": "बुवाई / रोपाई की तारीख —", "save": "सेव करें", "saved": "सेव हो गया!",
        "pick_place": "अपनी जगह चुनें", "status": "सिस्टम स्थिति", "usage": "अब तक",
        "choose_farmer": "किसान प्रोफ़ाइल", "new_farmer": "➕ नया किसान", "data_as_of": "डेटा समय",
        "cached": "पुराना सहेजा डेटा", "unavailable": "उपलब्ध नहीं", "queries": "सवालों के जवाब", "farmers": "किसान",
    },
    "mr": {
        "tagline": "तुमचा शेती सल्लागार — थेट हवामान, माती, बाजारभाव आणि अधिकृत पीक मार्गदर्शक",
        "tab_ask": "🎤 विचारा", "tab_farm": "🌦️ माझे शेत", "tab_mandi": "💰 बाजारभाव", "tab_profile": "👤 प्रोफाइल",
        "ask_voice": "तुमचा प्रश्न बोला", "ask_text": "…किंवा इथे लिहा", "ask_btn": "सल्ला घ्या",
        "examples": "असे विचारा", "thinking": "हवामान, पिकाची अवस्था, भाव आणि मार्गदर्शक पाहत आहोत…",
        "verified": "थेट माहितीशी पडताळलेले", "not_verified": "फक्त माहितीवर आधारित उत्तर",
        "sources": "स्रोत", "how": "हे उत्तर कसे तयार झाले", "english": "इंग्रजी भाषांतर",
        "listen": "ऐका", "stage": "पिकाची अवस्था", "days_after": "दिवस पेरणीनंतर", "to_harvest": "दिवस काढणीपर्यंत",
        "risk_cal": "7 दिवसांचे धोका कॅलेंडर", "no_risks": "या आठवड्यात हवामानाचा धोका आढळला नाही.",
        "windows": "या आठवड्यात काय करावे", "best_spray": "फवारणीची सर्वोत्तम वेळ", "no_spray": "पुढील 5 दिवसांत फवारणीसाठी योग्य दिवस नाही",
        "water": "पाणी", "water_need": "या आठवड्यात पिकाला सुमारे {need} मिमी पाणी लागेल; पावसातून सुमारे {eff} मिमी मिळेल.",
        "harvest": "काढणीसाठी कोरडे दिवस", "soil": "तुमची माती", "forecast": "हवामान अंदाज",
        "mandi_today": "आजचे बाजारभाव", "nearest": "सर्वोच्च बाजार", "state_avg": "राज्य सरासरी",
        "markets": "बाजार", "trend": "भावाचा कल (आमच्या दैनिक नोंदी)", "history_since": "{d} पासून नोंदी ({n} दिवस)",
        "no_history": "आम्ही दररोज भाव जतन करतो; काही दिवसांनी कल दिसेल.",
        "ask_sell": "आत्ता विकू का?", "per_q": "₹/क्विंटल",
        "profile_new": "तुमचे शेत जोडा", "name": "नाव (ऐच्छिक)", "language": "भाषा",
        "place": "गाव / शहर / जिल्हा", "find": "शोधा", "use_gps": "माझे स्थान वापरा",
        "crops": "पिके", "sowing": "पेरणी / लागवड तारीख —", "save": "जतन करा", "saved": "जतन झाले!",
        "pick_place": "तुमचे ठिकाण निवडा", "status": "सिस्टम स्थिती", "usage": "आतापर्यंत",
        "choose_farmer": "शेतकरी प्रोफाइल", "new_farmer": "➕ नवीन शेतकरी", "data_as_of": "माहिती वेळ",
        "cached": "जतन केलेली जुनी माहिती", "unavailable": "उपलब्ध नाही", "queries": "प्रश्नांची उत्तरे", "farmers": "शेतकरी",
    },
}

# Risk names shown in the My Farm calendar (rule `type` ids in data/rules.yaml).
RISK = {
    "en": {},
    "hi": {"disease_anthracnose": "एन्थ्रेक्नोज़", "disease_false_smut": "आभासी कंडुआ", "disease_late_blight": "पछेती झुलसा",
           "disease_purple_blotch": "पर्पल ब्लॉच", "disease_rust": "रतुआ", "disease_stemphylium": "स्टेमफिलियम झुलसा",
           "dry_spell": "सूखा दौर", "frost": "पाला", "harvest_rain": "कटाई पर बारिश", "heat_stress": "गर्मी का तनाव",
           "heavy_rain": "भारी बारिश", "lodging_risk": "फसल गिरने का खतरा", "no_spray_rain": "बारिश: छिड़काव न करें",
           "no_spray_wind": "तेज़ हवा: छिड़काव न करें", "poor_fruit_set": "फल कम लगना",
           "rain_skip_irrigation": "बारिश: सिंचाई छोड़ें", "stage_advice": "अवस्था सलाह"},
    "mr": {"disease_anthracnose": "अँथ्रॅक्नोज", "disease_false_smut": "खोटा काजळी रोग", "disease_late_blight": "करपा (लेट ब्लाइट)",
           "disease_purple_blotch": "जांभळा करपा", "disease_rust": "तांबेरा", "disease_stemphylium": "स्टेमफिलियम करपा",
           "dry_spell": "कोरडा काळ", "frost": "दंव", "harvest_rain": "काढणीवेळी पाऊस", "heat_stress": "उष्णतेचा ताण",
           "heavy_rain": "मुसळधार पाऊस", "lodging_risk": "पीक लोळण्याचा धोका", "no_spray_rain": "पाऊस: फवारणी नको",
           "no_spray_wind": "जोरदार वारा: फवारणी नको", "poor_fruit_set": "फळधारणा कमी",
           "rain_skip_irrigation": "पाऊस: पाणी देणे टाळा", "stage_advice": "अवस्था सल्ला"},
}


def risk_name(lang: str, rule_type: str) -> str:
    return RISK.get(lang, {}).get(rule_type) or rule_type.replace("_", " ")


EXAMPLES = {
    "en": ["Should I spray my {crop} this week?", "Should I sell {crop} now or wait?", "Do I need to irrigate this week?"],
    "hi": ["क्या इस हफ्ते {crop} पर छिड़काव करूं?", "{crop} अभी बेचूं या रुकूं?", "क्या इस हफ्ते सिंचाई करनी चाहिए?"],
    "mr": ["या आठवड्यात {crop} वर फवारणी करू का?", "{crop} आत्ता विकू की थांबू?", "या आठवड्यात पाणी द्यावे का?"],
}


def t(lang: str, key: str, **kw) -> str:
    s = T.get(lang, T["en"]).get(key) or T["en"][key]
    return s.format(**kw) if kw else s
