"""
Cerveau décisionnel de Sentinel.
Boucle : Anonymiser -> Retrouver contexte -> Décider -> Proposer/Exécuter -> Mémoriser
"""
import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
import ollama

from backend.memory.vector_store import store_event, query_similar
from backend.actions.desktop_actions import ACTION_WHITELIST
from backend.security.anonymizer import anonymize


class SentinelState(TypedDict):
    raw_text: str
    window_title: str
    anonymized_text: str
    similar_context: list
    decision: Optional[dict]
    trial_phase: str  # "observation" ou "deployment"


def node_anonymize(state: SentinelState) -> SentinelState:
    state["anonymized_text"] = anonymize(state["raw_text"])
    return state


def node_retrieve_memory(state: SentinelState) -> SentinelState:
    state["similar_context"] = query_similar(state["anonymized_text"])
    return state


def node_decide(state: SentinelState) -> SentinelState:
    available_actions = ", ".join(ACTION_WHITELIST.keys())
    prompt = f"""Tu es Sentinel, un assistant qui observe le travail d'un
professionnel. Voici ce qui vient de se passer à l'écran :
"{state['anonymized_text']}"

Contexte similaire déjà observé : {state['similar_context']}

Actions que tu as le droit de proposer (UNIQUEMENT celles-ci, aucune autre) :
{available_actions}

Si tu identifies un pattern répétitif clair, réponds en JSON strict :
{{"suggest_action": "<nom_action_de_la_liste_ou_null>", "reason": "<courte explication>"}}
Sinon réponds {{"suggest_action": null, "reason": "observation seule"}}
"""
    response = ollama.chat(
        model="qwen2.5:3b", # Utilisation du modèle téléchargé lors du benchmark
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    state["decision"] = json.loads(response["message"]["content"])
    return state


def node_act_or_suggest(state: SentinelState) -> SentinelState:
    decision = state["decision"]
    action_name = decision.get("suggest_action")

    # Deuxième vérification : même si le LLM invente un nom d'action,
    # on ne fait confiance qu'au registre whitelist réel.
    if action_name and action_name in ACTION_WHITELIST:
        if state["trial_phase"] == "observation":
            print(f"[Sentinel] (mode observation) suggestion ignorée : {action_name}")
        else:
            print(f"[Sentinel] Suggestion à valider par l'utilisateur : {action_name}")
            # -> envoyer l'événement au frontend Tauri via WebSocket
            # pour demander confirmation humaine avant exécution réelle.
    return state


def node_memorize(state: SentinelState) -> SentinelState:
    store_event(state["anonymized_text"], state["window_title"])
    return state


def build_graph():
    graph = StateGraph(SentinelState)
    graph.add_node("anonymize", node_anonymize)
    graph.add_node("retrieve_memory", node_retrieve_memory)
    graph.add_node("decide", node_decide)
    graph.add_node("act_or_suggest", node_act_or_suggest)
    graph.add_node("memorize", node_memorize)

    graph.set_entry_point("anonymize")
    graph.add_edge("anonymize", "retrieve_memory")
    graph.add_edge("retrieve_memory", "decide")
    graph.add_edge("decide", "act_or_suggest")
    graph.add_edge("act_or_suggest", "memorize")
    graph.add_edge("memorize", END)

    return graph.compile()
