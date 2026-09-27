"""
Source Analyzer — Phase 3.

Répond à « que contient et que signifie cette source ? », à partir de la seule
source de vérité V2 : transcripts/transcript_data.json. Ne répond jamais à
« comment en faire un livre ? » — c'est la Phase 4 (Editorial Planner).

    transcript_data.json  ->  Source Analyzer  ->  analysis/source_map.json

IMPORTS VOLONTAIREMENT LÉGERS

Ce __init__ n'importe PAS analyzer.py, donc ni app.ai, ni le registre de
fournisseurs. Deux raisons :

1. app/report_service.py importe app.source_analysis.state pour sa section de
   rapport ; générer un rapport ne doit pas charger la couche IA ;
2. un import de confort ne doit pas pouvoir rendre un appel payant accessible
   par accident depuis un chemin V1.

Pour lancer une analyse, l'import est donc explicite :

    from app.source_analysis.analyzer import analyze_source
"""

from app.source_analysis.errors import (
    SourceAnalysisContextExceeded,
    SourceAnalysisError,
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    SourceTranscriptError,
    SourceTranscriptNotSubstantial,
    SourceTranscriptProvenanceError,
)
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    SourceMap,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION

__all__ = [
    "SOURCE_ANALYZER_PROMPT_VERSION",
    "SOURCE_MAP_SCHEMA_VERSION",
    "SourceAnalysisContextExceeded",
    "SourceAnalysisError",
    "SourceMap",
    "SourceMapEditorialLeakError",
    "SourceMapValidationError",
    "SourceTranscriptError",
    "SourceTranscriptNotSubstantial",
    "SourceTranscriptProvenanceError",
]
