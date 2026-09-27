"""
Budget de contexte et fenêtres techniques.

Deux garanties à tenir :

1. aucune constante de contexte codée en dur — le budget vient des capacités du
   couple (provider, modèle) et du ratio de sécurité de la configuration ;

2. les fenêtres techniques restent techniques. Elles découpent sur des
   frontières de SRC, n'en perdent aucun, et ne portent ni titre, ni thème, ni
   place dans un ordre éditorial. C'est la précaution qui empêche de refaire
   l'erreur de la V1, où un découpage de traitement est devenu un découpage de
   livre.
"""

from __future__ import annotations

import pytest

from app.ai.capabilities import ModelCapabilities, resolve_capabilities
from app.source_analysis.context_strategy import (
    AnalysisWindow,
    plan_context,
    plan_windows,
)
from app.source_analysis.models import STRATEGY_GLOBAL, STRATEGY_WINDOWED
from app.source_analysis.prompt import build_system_prompt, build_user_prompt
from app.source_analysis.transcript_input import (
    load_transcript_input,
    transcript_data_file,
)
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    build_transcript_document,
)


def _load(env):
    return load_transcript_input(
        transcript_data_file(env.transcripts_dir),
        project_name=env.project_name,
    )


def _plan(env, capabilities, *, safety_ratio=None):
    transcript = _load(env)

    return plan_context(
        transcript,
        capabilities,
        system_prompt=build_system_prompt(transcript.primary_language),
        user_prompt=build_user_prompt(transcript),
        safety_ratio=safety_ratio,
    )


def _capabilities(context_window: int, max_output_tokens: int) -> ModelCapabilities:
    return ModelCapabilities(
        provider="fake",
        model="fake-model",
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        supports_structured_output=True,
        known=True,
        source="builtin",
    )


class TestGlobalStrategy:
    """Un transcript qui tient est analysé d'un seul tenant."""

    def test_le_transcript_de_reference_tient_largement(self, analysis_env):
        plan = _plan(analysis_env, resolve_capabilities("fake", "fake-model"))

        assert plan.strategy == STRATEGY_GLOBAL
        assert plan.fits_globally is True
        assert plan.windows == ()

    def test_le_budget_est_calcule_depuis_les_capacites(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(100_000, 10_000), safety_ratio=0.70)

        assert plan.context_window == 100_000
        assert plan.max_output_tokens == 10_000
        assert plan.usable_input_context == int(100_000 * 0.70) - 10_000

    def test_le_ratio_de_securite_est_respecte(self, analysis_env):
        generous = _plan(analysis_env, _capabilities(100_000, 10_000), safety_ratio=0.9)
        strict = _plan(analysis_env, _capabilities(100_000, 10_000), safety_ratio=0.3)

        assert generous.usable_input_context > strict.usable_input_context

    def test_l_estimation_porte_sur_les_prompts_reellement_construits(
        self, analysis_env
    ):
        plan = _plan(analysis_env, resolve_capabilities("fake", "fake-model"))
        transcript = _load(analysis_env)
        text_only_chars = sum(len(segment.text) for segment in transcript.segments)

        # La consigne occupe elle aussi du contexte : l'ignorer donnerait une
        # estimation plus petite que le seul texte des segments.
        assert plan.estimated_input_tokens > text_only_chars / 4

    def test_l_estimation_est_marquee_comme_telle(self, analysis_env):
        plan = _plan(analysis_env, resolve_capabilities("fake", "fake-model"))

        assert plan.to_dict()["estimated"] is True
        assert plan.estimation_method in (
            "tiktoken",
            "heuristic_chars_per_token",
        )

    def test_des_capacites_de_repli_sont_signalees(self, analysis_env):
        unknown = resolve_capabilities("anthropic", "modele-inconnu-xyz")
        plan = _plan(analysis_env, unknown)

        assert unknown.known is False
        assert plan.capabilities_known is False

    def test_les_capacites_de_production_sont_connues(self):
        capabilities = resolve_capabilities("anthropic", "claude-sonnet-5")

        assert capabilities.known is True
        assert capabilities.context_window == 1_000_000
        assert capabilities.usable_input_context(0.70) == 700_000 - 128_000


class TestWindowedStrategy:
    """Un transcript trop grand est découpé, techniquement et seulement."""

    def test_un_budget_insuffisant_bascule_en_fenetres(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(2_000, 500))

        assert plan.strategy == STRATEGY_WINDOWED
        assert plan.fits_globally is False
        assert plan.window_count >= 2

    def test_aucun_segment_n_est_perdu(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(2_000, 500))
        transcript = _load(analysis_env)

        covered = {
            segment.src_id for window in plan.windows for segment in window.segments
        }

        assert covered == set(transcript.src_ids())

    def test_les_fenetres_coupent_sur_des_frontieres_de_src(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(2_000, 500))
        transcript = _load(analysis_env)
        originals = {segment.src_id: segment for segment in transcript.segments}

        for window in plan.windows:
            for segment in window.segments:
                assert segment == originals[segment.src_id]

    def test_le_decoupage_est_deterministe(self, analysis_env):
        first = _plan(analysis_env, _capabilities(2_000, 500))
        second = _plan(analysis_env, _capabilities(2_000, 500))

        assert [window.to_dict() for window in first.windows] == [
            window.to_dict() for window in second.windows
        ]

    def test_une_fenetre_ne_porte_ni_titre_ni_theme(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(2_000, 500))
        window = plan.windows[0]

        assert set(window.to_dict()) == {
            "index",
            "segment_count",
            "first_src",
            "last_src",
        }
        assert not hasattr(window, "label")
        assert not hasattr(window, "title")
        assert not hasattr(window, "topic")

    def test_un_recouvrement_est_possible(self, analysis_env):
        transcript = _load(analysis_env)

        windows = plan_windows(
            transcript,
            estimated_tokens=1_000,
            budget_tokens=250,
            overlap_segments=1,
        )

        assert len(windows) >= 2
        assert windows[0].segments[-1] == windows[1].segments[0]

    def test_sans_recouvrement_les_fenetres_sont_disjointes(self, analysis_env):
        transcript = _load(analysis_env)

        windows = plan_windows(
            transcript,
            estimated_tokens=1_000,
            budget_tokens=250,
            overlap_segments=0,
        )
        seen: list[str] = []

        for window in windows:
            seen.extend(segment.src_id for segment in window.segments)

        assert len(seen) == len(set(seen))

    def test_un_budget_nul_produit_une_fenetre_par_segment(self, analysis_env):
        transcript = _load(analysis_env)

        windows = plan_windows(
            transcript,
            estimated_tokens=1_000,
            budget_tokens=0,
        )

        assert len(windows) == transcript.segment_count

    def test_les_fenetres_sont_numerotees_a_partir_de_un(self, analysis_env):
        transcript = _load(analysis_env)

        windows = plan_windows(
            transcript,
            estimated_tokens=1_000,
            budget_tokens=250,
        )

        assert [window.index for window in windows] == list(
            range(1, len(windows) + 1)
        )

    def test_une_fenetre_expose_ses_bornes_src(self, analysis_env):
        transcript = _load(analysis_env)
        window = AnalysisWindow(index=1, segments=transcript.segments[:3])

        assert window.first_src == "SRC000001"
        assert window.last_src == "SRC000003"


class TestBudgetSummary:
    """Le résumé de budget doit être lisible dans un message d'erreur."""

    def test_le_resume_contient_les_chiffres_utiles(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(2_000, 500))
        summary = plan.budget_summary()

        assert "tokens estimés" in summary
        assert "budget d'entrée utilisable" in summary
        assert "fake:fake-model" in summary
        assert "context_window=2000" in summary
        assert "capabilities_known=True" in summary

    def test_aucune_constante_de_contexte_codee_en_dur(self):
        """
        Le module ne doit contenir aucune limite universelle : les seules
        valeurs numériques admissibles sont le recouvrement par défaut et des
        bornes de calcul.

        Le docstring du module est retiré avant l'inspection : il cite
        justement ces valeurs pour dire de ne pas les employer.
        """
        import inspect

        import app.source_analysis.context_strategy as module

        source = inspect.getsource(module).replace(module.__doc__ or "", "")

        for forbidden in ("4096", "8000", "100000", "128000", "32768"):
            assert forbidden not in source


class TestPlanSerialization:
    """Le plan est journalisable sans fuiter de contenu."""

    def test_le_plan_ne_contient_aucun_texte_de_segment(self, analysis_env):
        plan = _plan(analysis_env, _capabilities(2_000, 500))
        serialized = str(plan.to_dict())
        transcript = _load(analysis_env)

        for segment in transcript.segments:
            assert segment.text not in serialized

    def test_le_plan_expose_la_strategie_et_le_modele(self, analysis_env):
        plan = _plan(analysis_env, resolve_capabilities("fake", "fake-model"))
        data = plan.to_dict()

        assert data["strategy"] == STRATEGY_GLOBAL
        assert data["provider"] == "fake"
        assert data["model"] == "fake-model"
        assert data["window_count"] == 0
