# Demo script (2:30, live system)

Before going on stage: open the app, run `python scripts/probe_apis.py`, open the sidebar *System status* (all green),
and ask one warm-up question (free-tier hosts sleep).

| Time | Do | Say |
|---|---|---|
| 0:00 | Title screen | "86% of Indian farm holdings are small and marginal. Advice reaches them late, in the wrong language, without local weather or prices." |
| 0:15 | Profile tab: type *Lasalgaon* → pick → onion + sowing date → Save (Hindi) | "Village name or GPS. Everything after this is hyper-local." |
| 0:35 | Ask tab → 🎤 *"इस हफ्ते प्याज पर छिड़काव करूं?"* | — |
| 0:50 | Play the audio reply; open **How I got this** | "It heard Hindi, planned tools, called the live forecast, worked out the crop stage, applied PAU's rule *repeat the spray if it rains within 24 h*, drafted, and the **verifier** checked every number against the data." |
| 1:10 | Open **Sources** | "Every claim links to a source: forecast fetched at …, PAU Package of Practices page 65, ICAR-DOGR page 52." |
| 1:20 | Ask *"प्याज अभी बेचूं या रुकूं?"* → Mandi tab | "Today's Agmarknet prices for Maharashtra mandis, plus the trend from our own daily snapshots, since data.gov.in only gives today." |
| 1:50 | My farm tab | "A 7-day risk calendar: rain wash-off, Stemphylium blight weather from ICAR-DOGR's 18–25 °C + 16 h wetness rule, the best spray window, and crop water need from FAO-56." |
| 2:10 | Robustness: set `WEATHER_URL=http://invalid` (or show sidebar 🔴) and ask again | "An API went down. It falls back to the last saved forecast, labelled cached with its timestamp. No crash, no invented numbers." |
| 2:30 | Architecture slide | "LangGraph agent, verifier loop, cited rules, own price history. Next: WhatsApp/IVR for feature phones." |
