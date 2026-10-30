"""The KisanSaathi agent as a LangGraph state machine.

  [transcribe] -> understand -> plan -> execute -> assess -> synthesize -> verify -> speak
                     |                                          ^            |
                     +-> direct (clarify / out of scope)        +-- retry ---+ (max 3 drafts)
                                                                             +-> fallback (data-only answer)

CLI:  python -m kisansaathi.agent.graph "इस हफ्ते प्याज पर छिड़काव करूं?" --farmer tests/demo_farmer.json
"""
from __future__ import annotations

import argparse
import json
import re
import time
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from .. import db
from ..models import Answer, FarmerProfile
from . import nodes as n
from .state import AgentState


@lru_cache
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("transcribe", n.node_transcribe)
    g.add_node("understand", n.node_understand)
    g.add_node("direct", n.node_direct)
    g.add_node("plan", n.node_plan)
    g.add_node("execute", n.node_execute)
    g.add_node("assess", n.node_assess)
    g.add_node("synthesize", n.node_synthesize)
    g.add_node("verify", n.node_verify)
    g.add_node("fallback", n.node_fallback)
    g.add_node("speak", n.node_speak)

    g.add_conditional_edges(START, lambda s: "transcribe" if s.get("audio") else "understand",
                            {"transcribe": "transcribe", "understand": "understand"})
    g.add_edge("transcribe", "understand")
    g.add_conditional_edges("understand", n.route_after_understand, {"direct": "direct", "plan": "plan"})
    g.add_edge("direct", "speak")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "assess")
    g.add_edge("assess", "synthesize")
    g.add_edge("synthesize", "verify")
    g.add_conditional_edges("verify", n.route_after_verify,
                            {"speak": "speak", "retry": "synthesize", "fallback": "fallback"})
    g.add_edge("fallback", "speak")
    g.add_edge("speak", END)
    return g.compile()


def _cited(final: dict) -> list:
    """Only the sources the answer actually cites (all of them if the answer cites none)."""
    text = final.get("answer_local", "") + " " + final.get("answer_en", "")
    ids = {i.strip() for grp in re.findall(r"\[(S\d+(?:\s*,\s*S\d+)*)\]", text) for i in grp.split(",")}
    cites = final.get("citations", [])
    return [c for c in cites if c.id in ids] or cites


def run(farmer: FarmerProfile, question: str = "", audio: bytes | None = None, audio_mime: str = "audio/wav",
        speak: bool = True) -> Answer:
    t0 = time.time()
    state: AgentState = {"farmer": farmer, "question_raw": question, "audio": audio, "audio_mime": audio_mime,
                         "language": farmer.language, "trace": [], "llm_used": [], "skip_speech": not speak}
    final = build_graph().invoke(state, {"recursion_limit": 30})
    ms = int((time.time() - t0) * 1000)
    ans = Answer(answer_local=final.get("answer_local", ""), answer_en=final.get("answer_en", ""),
                 language=final.get("language", farmer.language), citations=_cited(final),
                 risks=final.get("risks", []), verified=bool(final.get("verified")), trace=final.get("trace", []),
                 audio_bytes=final.get("audio_out"), clarification=bool(final.get("clarification")),
                 latency_ms=ms, llm_used=", ".join(dict.fromkeys(final.get("llm_used", []))) or "none")
    db.log_query(farmer_id=farmer.id, question=final.get("question_raw", question)[:2000], language=ans.language,
                 intents=final.get("intents", []), tools_used=final.get("plan", []), verified=ans.verified,
                 llm_used=ans.llm_used[:60], latency_ms=ms)
    return ans


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--farmer", required=True, help="path to a FarmerProfile JSON file")
    ap.add_argument("--speak", action="store_true")
    a = ap.parse_args()
    farmer = FarmerProfile.model_validate(json.loads(open(a.farmer).read()))
    ans = run(farmer, a.question, speak=a.speak)
    print("\n".join(ans.trace))
    print("\n" + ans.answer_local + "\n\n[EN] " + ans.answer_en)
    print("\nSources:")
    for c in ans.citations:
        print(f"  [{c.id}] {c.label} {c.detail}")
    print(f"\nverified={ans.verified} latency={ans.latency_ms} ms llm={ans.llm_used}")


if __name__ == "__main__":
    main()
