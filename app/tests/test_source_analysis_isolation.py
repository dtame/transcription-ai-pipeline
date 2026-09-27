"""
Isolation de la Phase 3 vis-à-vis de la V1.

Enjeu très concret : `python main.py` sur un projet existant ne doit pas se
mettre, du jour au lendemain, à appeler une API payante. L'étape source_analysis
est routée vers Anthropic ; le pipeline V1 tourne sur Ollama en local. Tant que
les deux pipelines n'ont pas convergé (Phase 9), le Source Analyzer reste un
service autonome qu'on appelle explicitement.

Ces tests sont des garde-fous d'architecture, pas des tests de comportement :
ils échoueront le jour où quelqu'un branchera le Source Analyzer dans main.py
sans le décider.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _module_bodies() -> dict[str, str]:
    """
    Code de chaque module du paquet, docstring de module RETIRÉE.

    Les docstrings citent volontairement ce qui est interdit (« aucun
    `import anthropic` ici ») ; les inclure ferait échouer les garde-fous sur
    les phrases mêmes qui posent la règle.
    """
    import inspect
    import pkgutil

    import app.source_analysis as package

    bodies: dict[str, str] = {}

    for module_info in pkgutil.iter_modules(package.__path__):
        module = __import__(
            f"app.source_analysis.{module_info.name}", fromlist=["_"]
        )
        source = inspect.getsource(module)
        bodies[module_info.name] = source.replace(module.__doc__ or "", "")

    return bodies


def _run_python(code: str) -> subprocess.CompletedProcess:
    """
    Exécute un script dans un interpréteur NEUF.

    Indispensable ici : la suite de tests a déjà importé le paquet
    source_analysis, donc un contrôle sur sys.modules dans le processus courant
    ne prouverait rien.
    """
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestMainDoesNotTriggerAnalysis:
    """Les chemins V1 n'importent ni le Source Analyzer, ni un SDK cloud."""

    def test_importer_main_ne_charge_pas_l_analyseur(self):
        result = _run_python(
            "import sys; import main; "
            "print('analyzer' if 'app.source_analysis.analyzer' in sys.modules "
            "else 'clean')"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "clean"

    def test_importer_main_ne_charge_aucun_sdk_cloud(self):
        result = _run_python(
            "import sys; import main; "
            "print(sorted(m for m in sys.modules "
            "if m in ('anthropic', 'openai')))"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[]"

    def test_importer_le_pipeline_ne_charge_pas_l_analyseur(self):
        result = _run_python(
            "import sys; import app.pipeline_runner; "
            "print('analyzer' if 'app.source_analysis.analyzer' in sys.modules "
            "else 'clean')"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "clean"

    def test_le_rapport_n_importe_pas_l_analyseur(self):
        """
        report_service lit la section source_analysis de l'état projet ; il ne
        doit pas pour autant charger la couche capable de déclencher un appel.
        """
        result = _run_python(
            "import sys; import app.report_service; "
            "print('analyzer' if 'app.source_analysis.analyzer' in sys.modules "
            "else 'clean')"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "clean"

    def test_le_paquet_source_analysis_n_expose_pas_l_analyseur_a_l_import(self):
        result = _run_python(
            "import sys; import app.source_analysis; "
            "print('analyzer' if 'app.source_analysis.analyzer' in sys.modules "
            "else 'clean')"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "clean"

    @pytest.mark.parametrize(
        "module_name",
        ["main", "app.pipeline_runner", "app.production_service"],
    )
    def test_aucun_chemin_v1_ne_mentionne_source_analysis(self, module_name):
        path = (
            REPO_ROOT / "main.py"
            if module_name == "main"
            else REPO_ROOT / Path(*module_name.split(".")).with_suffix(".py")
        )
        source = path.read_text(encoding="utf-8")

        assert "source_analysis" not in source
        assert "analyze_source" not in source
        assert "source_map" not in source


class TestNoDirectProviderSdk:
    """Le paquet passe exclusivement par app.ai."""

    @pytest.mark.parametrize(
        "forbidden",
        [
            "import anthropic",
            "import openai",
            "import requests",
            "from anthropic",
            "from openai",
        ],
    )
    def test_aucun_import_de_sdk_fournisseur(self, forbidden):
        offenders = [
            name for name, body in _module_bodies().items() if forbidden in body
        ]

        assert offenders == []

    @pytest.mark.parametrize("forbidden", ["cost_per_1m", "input_cost", "price_per"])
    def test_aucune_infrastructure_de_cout_locale(self, forbidden):
        """Le seul compteur de coût autorisé est le CostTracker de la Phase 2."""
        # real_run / phase3b_report relisent le bloc CostTracker déjà persisté
        # (clés du record) pour le rapport 3B : ils ne calculent aucun tarif.
        report_echo = {"real_run", "phase3b_report"}
        offenders = [
            name
            for name, body in _module_bodies().items()
            if forbidden in body and name not in report_echo
        ]

        assert offenders == []

    @pytest.mark.parametrize(
        "forbidden", ["embedding", "faiss", "chroma", "pinecone", "vector_store"]
    )
    def test_aucune_base_vectorielle_ni_rag(self, forbidden):
        offenders = [
            name
            for name, body in _module_bodies().items()
            if forbidden in body.lower()
        ]

        assert offenders == []

    @pytest.mark.parametrize("forbidden", ["urllib", "http://", "https://", "urlopen"])
    def test_aucun_acces_web(self, forbidden):
        offenders = [
            name for name, body in _module_bodies().items() if forbidden in body
        ]

        assert offenders == []

    def test_la_couche_ia_est_la_seule_porte_de_sortie(self):
        """Tous les appels passent par app.ai, et par rien d'autre."""
        bodies = _module_bodies()

        assert "from app.ai.registry import get_engine_for_stage" in bodies["analyzer"]
        assert "from app.ai.contracts import AIRequest" in bodies["analyzer"]
        assert "from app.ai.cost import CostTracker" in bodies["analyzer"]


class TestOutputLocation:
    """Le Source Map n'est pas rangé parmi les artefacts V1."""

    def test_le_chemin_est_sous_analysis(self, tmp_path, monkeypatch):
        import app.source_analysis.writer as writer

        monkeypatch.setattr(writer, "SORTIE_DIR", tmp_path)

        path = writer.source_map_path("demo")

        assert path == tmp_path / "demo" / "analysis" / "source_map.json"

    @pytest.mark.parametrize(
        "v1_dir", ["processed", "chunks", "final", "merged", "reviewed", "publication"]
    )
    def test_le_chemin_n_est_dans_aucun_repertoire_v1(
        self, tmp_path, monkeypatch, v1_dir
    ):
        import app.source_analysis.writer as writer

        monkeypatch.setattr(writer, "SORTIE_DIR", tmp_path)

        assert v1_dir not in writer.source_map_path("demo").parts

    def test_l_entree_reste_le_repertoire_transcripts(self, tmp_path, monkeypatch):
        import app.source_analysis.writer as writer

        monkeypatch.setattr(writer, "SORTIE_DIR", tmp_path)

        assert writer.transcripts_dir("demo") == tmp_path / "demo" / "transcripts"


class TestRealProjectsUntouched:
    """
    Aucune publication sémantique / canonique non autorisée sur un projet réel.

    Intention historique (Phase 3) : la Phase 3 est validée sur des fixtures.
    `analysis/` n'existait alors que pour accueillir `source_map.json`. Le
    test `test_aucun_repertoire_analysis_dans_le_sortie_reel` traitait donc
    l'existence du répertoire comme proxy d'une publication Source Analyzer.

    Réalité 3B.7.7A.5+ : un appel provider explicitement autorisé persiste
    des forensics sous analysis/provider_forensics/ et
    analysis/structured_output_forensics/. Ce sont des FORENSIC_ARTIFACT,
    pas un SourceMap, pas un transport validé, pas un result de fenêtre.

    L'invariant réel : pas de PUBLISHED_CANONICAL_ARTIFACT
    (source_map.json) ni de SEMANTIC_ANALYSIS_ARTIFACT non autorisé
    (windows/transport.json, result.json, consolidation, reconstruction).
    analysis/ seul n'implique plus une publication.
    """

    def test_aucun_source_map_dans_le_repertoire_de_sortie_reel(self):
        sortie = REPO_ROOT / "sortie"

        if not sortie.exists():
            pytest.skip("aucun répertoire de sortie réel dans ce dépôt")

        assert list(sortie.glob("*/analysis/source_map.json")) == []

    def test_aucun_artefact_semantique_ou_canonique_non_autorise_dans_analysis(
        self,
    ):
        """
        Remplace le proxy « analysis/ existe ⇒ publication ».

        Les forensics provider/structured sont autorisées. Un SourceMap,
        un transport validé ou un result de fenêtre ne le sont pas.
        """
        from app.source_analysis.publication_isolation import inspect_sortie_isolation

        sortie = REPO_ROOT / "sortie"

        if not sortie.exists():
            pytest.skip("aucun répertoire de sortie réel dans ce dépôt")

        report = inspect_sortie_isolation(sortie)

        assert report["source_maps"] == []
        assert report["ok"] is True
        assert report["violations"] == []

    def test_forensics_provider_et_structured_sont_autorises(self, tmp_path):
        from app.source_analysis.publication_isolation import (
            CLASS_FORENSIC,
            inspect_analysis_directory,
        )

        analysis = tmp_path / "analysis"
        (analysis / "provider_forensics" / "WIN001" / "abc").mkdir(parents=True)
        (analysis / "structured_output_forensics" / "WIN001" / "abc").mkdir(
            parents=True
        )
        (
            analysis
            / "provider_forensics"
            / "WIN001"
            / "abc"
            / "provider_raw_response.bin"
        ).write_bytes(b"{}")
        (
            analysis
            / "structured_output_forensics"
            / "WIN001"
            / "abc"
            / "provider_raw_content.txt"
        ).write_text("{", encoding="utf-8")

        report = inspect_analysis_directory(analysis)

        assert report["ok"] is True
        assert sorted(report["forensic_dirs"]) == [
            "provider_forensics",
            "structured_output_forensics",
        ]
        assert report["published_canonical_present"] is False
        assert report["semantic_artifact_present"] is False
        assert CLASS_FORENSIC == "FORENSIC_ARTIFACT"

    def test_source_map_interdit_sans_autorisation(self, tmp_path):
        from app.source_analysis.publication_isolation import inspect_analysis_directory

        analysis = tmp_path / "analysis"
        analysis.mkdir()
        (analysis / "source_map.json").write_text("{}", encoding="utf-8")

        report = inspect_analysis_directory(analysis)

        assert report["ok"] is False
        assert report["published_canonical_present"] is True

    def test_result_semantique_interdit_sans_autorisation(self, tmp_path):
        from app.source_analysis.publication_isolation import inspect_analysis_directory

        analysis = tmp_path / "analysis"
        window = analysis / "windows" / "WIN001"
        window.mkdir(parents=True)
        (window / "result.json").write_text("{}", encoding="utf-8")

        report = inspect_analysis_directory(analysis)

        assert report["ok"] is False
        assert report["semantic_artifact_present"] is True

    def test_transport_valide_n_est_pas_un_forensic(self, tmp_path):
        from app.source_analysis.publication_isolation import (
            CLASS_FORENSIC,
            CLASS_SEMANTIC,
            inspect_analysis_directory,
        )

        analysis = tmp_path / "analysis"
        forensic = analysis / "provider_forensics" / "WIN001" / "abc"
        forensic.mkdir(parents=True)
        (forensic / "provider_raw_response.bin").write_bytes(b"{}")
        semantic = analysis / "windows" / "WIN001"
        semantic.mkdir(parents=True)
        (semantic / "transport.json").write_text("{}", encoding="utf-8")

        report = inspect_analysis_directory(analysis)

        assert report["ok"] is False
        assert report["semantic_artifact_present"] is True
        assert "provider_forensics" in report["forensic_dirs"]
        classes = {item["class"] for item in report["violations"]}
        assert CLASS_SEMANTIC in classes
        assert CLASS_FORENSIC not in classes

    def test_aucun_module_de_phase_3_ne_nomme_un_projet_reel(self):
        for body in _module_bodies().values():
            assert "pastoral" not in body.lower()

    def test_les_fixtures_de_test_utilisent_un_projet_jetable(self):
        from app.tests.source_analysis_fixtures import build_transcript_document

        document = build_transcript_document()

        assert document.project_name == "demo_analysis"
