# Pitch deck (6 slides)

1. **KisanSaathi** — your farm advisor in your language. Team names. One-line: *voice advice grounded in live weather, soil, mandi prices and official guides, with every fact cited.*
2. **Problem** — climate volatility (unseasonal rain, heat at grain filling), price swings, and advice that is generic, late and English-first. Small/marginal farmers are 86% of holdings (Agriculture Census 2015-16; verify latest figure before presenting). Cite any extension-reach figure only from an official source.
3. **Solution** — ask by voice in 9 languages → spoken answer + 7-day risk calendar + mandi panel. Demo screenshot.
4. **Architecture & innovation** — LangGraph agent with verifier/self-correction loop; deterministic rules engine with page-level citations (PAU, ICAR-DOGR, ICAR-IISR, FAO-56); hybrid RAG (multilingual embeddings + BM25); own price-history DB from daily Agmarknet snapshots; graceful degradation at every layer.
5. **Impact & USP** — vs generic chatbots: no hallucinated numbers (verifier), sources shown, hyper-local. Vs existing advisory apps: conversational and voice-first, combines weather + stage + market in one answer, "sell or hold" reasoning.
6. **Roadmap** — WhatsApp & IVR for feature phones; Bhashini for more languages; IMD district agromet bulletins; Telegram/SMS proactive alerts; KVK/FPO dashboard; crop-photo diagnosis cross-checked with guides.
