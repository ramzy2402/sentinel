"""
Détecte et masque les données personnelles (noms, IBAN, emails,
téléphones) AVANT tout passage en mémoire vectorielle ou au LLM.
Défense en profondeur : même en local, un cabinet CIF manipule des
données patrimoniales ultra-sensibles.
"""
import re
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

_nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "fr", "model_name": "fr_core_news_sm"}],
}
_provider = NlpEngineProvider(nlp_configuration=_nlp_config)
_nlp_engine = _provider.create_engine()

_analyzer = AnalyzerEngine(nlp_engine=_nlp_engine, supported_languages=["fr"])
_anonymizer = AnonymizerEngine()

IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")


def anonymize(text: str) -> str:
    text = IBAN_REGEX.sub("[IBAN_MASQUÉ]", text)
    results = _analyzer.analyze(text=text, language="fr")
    anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text
