"""
Phase 1 — Construction du contrat Transcript V2.

Couvre app.transcript_builder et app.file_utils.natural_sort_key :

- tri naturel déterministe des sources audio (16, 39) ;
- identifiants AUDIO et SRC (10, 11, 38) ;
- provenance SRC → AUDIO → timestamp (40) ;
- langues : fr, en, hors fr/en, projet multilingue (19, 41) ;
- timestamps précis, relatifs au fichier source, offsets techniques (12, 13, 42) ;
- règle d'ownership aux frontières d'overlap (21, 22, 43) ;
- segments techniques invisibles comme sources éditoriales (20) ;
- statistiques (34).

Aucun accès disque, aucun Whisper : le builder travaille sur des captures.
"""

from __future__ import annotations

import pytest

from app.file_utils import natural_sort_key
from app.transcript_builder import (
    build_transcript_document,
    order_captures,
    resolve_owned_segments,
)
from app.transcript_models import (
    CAPTURE_MODE_DIRECT,
    CAPTURE_MODE_SEGMENTED,
    AudioCapture,
    CapturedPart,
    CapturedSegment,
)

OVERLAP = 10.0
SEGMENT = 900.0


def direct_capture(filename, segments, language="fr", duration=600.0):
    """Capture d'un fichier audio court : une seule partie technique."""
    return AudioCapture(
        filename=filename,
        duration_seconds=duration,
        mode=CAPTURE_MODE_DIRECT,
        parts=[
            CapturedPart(
                id="part_001",
                start_seconds=0.0,
                end_seconds=duration,
                effective_start_local=0.0,
                detected_language=language,
                segments=[CapturedSegment(*item) for item in segments],
            )
        ],
    )


def segmented_capture(filename, parts, duration=1900.0):
    """
    Capture d'un fichier audio long.

    `parts` : liste de (start_seconds, end_seconds, language, segments locaux).
    effective_start_local vaut 0 pour la première partie, OVERLAP ensuite.
    """
    captured_parts = []

    for index, (start, end, language, segments) in enumerate(parts):
        captured_parts.append(
            CapturedPart(
                id=f"part_{index + 1:03d}",
                start_seconds=start,
                end_seconds=end,
                effective_start_local=0.0 if index == 0 else OVERLAP,
                detected_language=language,
                segments=[CapturedSegment(*item) for item in segments],
            )
        )

    return AudioCapture(
        filename=filename,
        duration_seconds=duration,
        mode=CAPTURE_MODE_SEGMENTED,
        parts=captured_parts,
    )


def texts(document, source_id=None):
    segments = (
        document.segments_for(source_id) if source_id else document.segments
    )
    return [segment.text for segment in segments]


# ---------------------------------------------------------------------------
# 16 — Tri naturel
# ---------------------------------------------------------------------------

class TestNaturalSortKey:

    def test_numbers_are_compared_numerically(self):
        names = ["audio 10", "audio 2", "audio 1"]

        assert sorted(names, key=natural_sort_key) == ["audio 1", "audio 2", "audio 10"]

    def test_explicit_numeric_prefixes_are_respected(self):
        names = ["03-conclusion", "01-introduction", "02-session", "10-annexe"]

        assert sorted(names, key=natural_sort_key) == [
            "01-introduction",
            "02-session",
            "03-conclusion",
            "10-annexe",
        ]

    def test_sort_is_case_insensitive(self):
        names = ["Retreat 2.mp3", "retreat 10.mp3", "RETREAT 1.mp3"]

        assert sorted(names, key=natural_sort_key) == [
            "RETREAT 1.mp3",
            "Retreat 2.mp3",
            "retreat 10.mp3",
        ]

    def test_sort_is_stable_and_total_even_for_case_only_differences(self):
        names = ["a.mp3", "A.mp3"]

        first = sorted(names, key=natural_sort_key)
        second = sorted(reversed(names), key=natural_sort_key)

        assert first == second, "L'ordre doit être total et déterministe."

    def test_sort_does_not_depend_on_input_order(self):
        names = ["audio 1", "audio 2", "audio 10", "audio 21", "audio 3"]

        expected = ["audio 1", "audio 2", "audio 3", "audio 10", "audio 21"]

        assert sorted(names, key=natural_sort_key) == expected
        assert sorted(reversed(names), key=natural_sort_key) == expected

    def test_long_numbers_do_not_break_the_order(self):
        names = ["part 100", "part 99", "part 1000"]

        assert sorted(names, key=natural_sort_key) == [
            "part 99",
            "part 100",
            "part 1000",
        ]


# ---------------------------------------------------------------------------
# 39 — Multi-audios : ordre canonique
# ---------------------------------------------------------------------------

class TestMultipleAudioOrder:

    @pytest.fixture
    def document(self):
        captures = [
            direct_capture("audio 10.mp3", [(0.0, 4.0, "dix")]),
            direct_capture("audio 1.mp3", [(0.0, 4.0, "un")]),
            direct_capture("audio 2.mp3", [(0.0, 4.0, "deux")]),
        ]
        return build_transcript_document("retreat", captures)

    def test_audio_ids_follow_the_natural_order(self, document):
        assert [(s.source_id, s.filename) for s in document.sources] == [
            ("AUDIO001", "audio 1.mp3"),
            ("AUDIO002", "audio 2.mp3"),
            ("AUDIO003", "audio 10.mp3"),
        ]

    def test_source_order_matches_the_audio_id(self, document):
        assert [(s.source_id, s.order) for s in document.sources] == [
            ("AUDIO001", 1),
            ("AUDIO002", 2),
            ("AUDIO003", 3),
        ]

    def test_src_ids_follow_the_source_order(self, document):
        assert [(s.id, s.source_id, s.text) for s in document.segments] == [
            ("SRC000001", "AUDIO001", "un"),
            ("SRC000002", "AUDIO002", "deux"),
            ("SRC000003", "AUDIO003", "dix"),
        ]

    def test_order_does_not_depend_on_the_capture_input_order(self):
        names = ["audio 10.mp3", "audio 1.mp3", "audio 2.mp3"]
        captures = [direct_capture(name, [(0.0, 1.0, name)]) for name in names]

        forward = build_transcript_document("retreat", captures)
        backward = build_transcript_document("retreat", list(reversed(captures)))

        assert forward.to_dict() == backward.to_dict()

    def test_single_audio_project(self):
        document = build_transcript_document(
            "solo", [direct_capture("unique.mp3", [(0.0, 3.0, "seul")])]
        )

        assert [s.source_id for s in document.sources] == ["AUDIO001"]
        assert [s.id for s in document.segments] == ["SRC000001"]

    def test_two_audio_project(self):
        document = build_transcript_document(
            "duo",
            [
                direct_capture("b.mp3", [(0.0, 3.0, "b")]),
                direct_capture("a.mp3", [(0.0, 3.0, "a")]),
            ],
        )

        assert [(s.source_id, s.filename) for s in document.sources] == [
            ("AUDIO001", "a.mp3"),
            ("AUDIO002", "b.mp3"),
        ]

    def test_ten_audio_project_keeps_numeric_order(self):
        captures = [
            direct_capture(f"session {i}.mp3", [(0.0, 1.0, f"s{i}")])
            for i in (7, 10, 1, 4, 2, 9, 3, 8, 5, 6)
        ]

        document = build_transcript_document("dix", captures)

        assert [s.filename for s in document.sources] == [
            f"session {i}.mp3" for i in range(1, 11)
        ]
        assert [s.text for s in document.segments] == [f"s{i}" for i in range(1, 11)]

    def test_order_captures_is_exposed_and_pure(self):
        captures = [
            direct_capture("audio 10.mp3", []),
            direct_capture("audio 2.mp3", []),
        ]

        ordered = order_captures(captures)

        assert [c.filename for c in ordered] == ["audio 2.mp3", "audio 10.mp3"]
        assert [c.filename for c in captures] == ["audio 10.mp3", "audio 2.mp3"]


# ---------------------------------------------------------------------------
# 10 / 38 — Identifiants SRC
# ---------------------------------------------------------------------------

class TestSrcIdentifiers:

    @pytest.fixture
    def document(self):
        captures = [
            direct_capture("a.mp3", [(0.0, 2.0, "a1"), (2.0, 4.0, "a2")]),
            direct_capture("b.mp3", [(0.0, 2.0, "b1"), (2.0, 4.0, "b2"), (4.0, 6.0, "b3")]),
        ]
        return build_transcript_document("projet", captures)

    def test_ids_start_at_one_and_are_continuous(self, document):
        assert [s.id for s in document.segments] == [
            "SRC000001",
            "SRC000002",
            "SRC000003",
            "SRC000004",
            "SRC000005",
        ]

    def test_ids_are_unique(self, document):
        ids = [s.id for s in document.segments]
        assert len(set(ids)) == len(ids)

    def test_ids_continue_across_audio_files(self, document):
        assert [(s.id, s.source_id) for s in document.segments] == [
            ("SRC000001", "AUDIO001"),
            ("SRC000002", "AUDIO001"),
            ("SRC000003", "AUDIO002"),
            ("SRC000004", "AUDIO002"),
            ("SRC000005", "AUDIO002"),
        ]

    def test_ids_are_deterministic_across_rebuilds(self):
        captures = [
            direct_capture("a.mp3", [(0.0, 2.0, "a1")]),
            direct_capture("b.mp3", [(0.0, 2.0, "b1")]),
        ]

        first = build_transcript_document("projet", captures).to_dict()
        second = build_transcript_document("projet", captures).to_dict()

        assert first == second

    def test_ids_are_independent_of_technical_segments(self):
        """Trois parties techniques ne décalent pas la numérotation des SRC."""
        capture = segmented_capture(
            "long.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un")]),
                (900.0, 1810.0, "fr", [(20.0, 30.0, "deux")]),
                (1800.0, 1900.0, "fr", [(20.0, 30.0, "trois")]),
            ],
        )

        document = build_transcript_document("projet", [capture])

        assert [s.id for s in document.segments] == [
            "SRC000001",
            "SRC000002",
            "SRC000003",
        ]


# ---------------------------------------------------------------------------
# 20 — Segments techniques invisibles
# ---------------------------------------------------------------------------

class TestTechnicalSegmentsAreInvisible:

    def test_a_segmented_file_produces_exactly_one_audio_source(self):
        capture = segmented_capture(
            "Retreat 1.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un")]),
                (900.0, 1810.0, "fr", [(20.0, 30.0, "deux")]),
                (1800.0, 1900.0, "fr", [(20.0, 30.0, "trois")]),
            ],
        )

        document = build_transcript_document("retreat", [capture])

        assert [s.source_id for s in document.sources] == ["AUDIO001"]
        assert document.stats.source_count == 1
        assert {s.source_id for s in document.segments} == {"AUDIO001"}

    def test_no_part_identifier_leaks_into_the_contract(self):
        capture = segmented_capture(
            "Retreat 1.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un")]),
                (900.0, 1810.0, "fr", [(20.0, 30.0, "deux")]),
            ],
        )

        payload = build_transcript_document("retreat", [capture]).to_dict()

        assert "part_001" not in str(payload)
        assert "part_002" not in str(payload)

    def test_source_duration_is_the_original_file_duration(self):
        capture = segmented_capture(
            "Retreat 1.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un")]),
                (900.0, 1900.0, "fr", [(20.0, 30.0, "deux")]),
            ],
            duration=1900.0,
        )

        document = build_transcript_document("retreat", [capture])

        assert document.sources[0].duration_seconds == 1900.0


# ---------------------------------------------------------------------------
# 40 — Provenance
# ---------------------------------------------------------------------------

class TestProvenance:

    @pytest.fixture
    def document(self):
        captures = [
            direct_capture("01-intro.mp3", [(0.0, 11.42, "intro")], duration=300.0),
            segmented_capture(
                "02-session.mp3",
                [
                    (0.0, 910.0, "fr", [(12.37, 18.94, "session début")]),
                    (900.0, 1810.0, "fr", [(20.0, 30.5, "session suite")]),
                ],
            ),
        ]
        return build_transcript_document("retreat", captures)

    def test_every_segment_points_to_an_existing_source(self, document):
        known = {source.source_id for source in document.sources}

        for segment in document.segments:
            assert segment.source_id in known

    def test_every_segment_carries_the_right_source_order(self, document):
        by_id = {source.source_id: source for source in document.sources}

        for segment in document.segments:
            assert segment.source_order == by_id[segment.source_id].order

    def test_a_segment_answers_which_file_and_which_moment(self, document):
        segment = document.segments[1]

        assert segment.id == "SRC000002"
        assert segment.source_id == "AUDIO002"
        assert document.source_by_id("AUDIO002").filename == "02-session.mp3"
        assert (segment.start, segment.end) == (12.37, 18.94)

    def test_timestamps_of_a_later_technical_part_stay_relative_to_the_file(
        self, document
    ):
        segment = document.segments[2]

        assert segment.source_id == "AUDIO002"
        assert (segment.start, segment.end) == (920.0, 930.5)

    def test_texts_are_attached_to_the_right_source(self, document):
        assert texts(document, "AUDIO001") == ["intro"]
        assert texts(document, "AUDIO002") == ["session début", "session suite"]


# ---------------------------------------------------------------------------
# 12 / 13 / 42 — Timestamps
# ---------------------------------------------------------------------------

class TestTimestamps:

    def test_precision_is_preserved_exactly(self):
        capture = direct_capture("a.mp3", [(12.37, 18.94, "précis")])

        segment = build_transcript_document("p", [capture]).segments[0]

        assert segment.start == 12.37
        assert segment.end == 18.94

    def test_technical_offset_is_added_to_local_timestamps(self):
        capture = segmented_capture(
            "long.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un")]),
                (900.0, 1810.0, "fr", [(428.37 - 900.0, 441.92 - 900.0, "deux")]),
            ],
        )

        segment = build_transcript_document("p", [capture]).segments[1]

        assert (segment.start, segment.end) == (428.37, 441.92)

    def test_no_global_multi_file_timeline_is_fabricated(self):
        """Le second fichier redémarre à zéro : la provenance prime."""
        captures = [
            direct_capture("a.mp3", [(0.0, 300.0, "a")], duration=300.0),
            direct_capture("b.mp3", [(0.0, 12.5, "b")], duration=300.0),
        ]

        document = build_transcript_document("p", captures)

        assert document.segments[1].source_id == "AUDIO002"
        assert document.segments[1].start == 0.0, (
            "Aucune addition de la durée des fichiers précédents."
        )

    def test_timestamps_beyond_one_hour_stay_numeric(self):
        capture = segmented_capture(
            "long.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un")]),
                (3600.0, 4510.0, "fr", [(12.37, 18.94, "après une heure")]),
            ],
            duration=4510.0,
        )

        segment = build_transcript_document("p", [capture]).segments[1]

        assert (segment.start, segment.end) == (3612.37, 3618.94)

    def test_no_negative_timestamp_is_produced(self):
        capture = segmented_capture(
            "long.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 5.0, "un"), (900.0, 908.0, "deux")]),
                (900.0, 1810.0, "fr", [(0.0, 8.0, "deux"), (20.0, 30.0, "trois")]),
            ],
        )

        document = build_transcript_document("p", [capture])

        for segment in document.segments:
            assert segment.start >= 0.0
            assert segment.end >= segment.start

    def test_chronology_is_monotonic_within_a_source(self):
        capture = segmented_capture(
            "long.mp3",
            [
                (0.0, 910.0, "fr", [(10.0, 20.0, "a"), (800.0, 810.0, "b")]),
                (900.0, 1810.0, "fr", [(30.0, 40.0, "c"), (700.0, 710.0, "d")]),
                (1800.0, 1900.0, "fr", [(50.0, 60.0, "e")]),
            ],
        )

        starts = [s.start for s in build_transcript_document("p", [capture]).segments]

        assert starts == sorted(starts)
        assert starts == [10.0, 800.0, 930.0, 1600.0, 1850.0]


# ---------------------------------------------------------------------------
# 21 / 22 / 43 — Ownership de l'overlap
# ---------------------------------------------------------------------------

class TestOverlapOwnership:
    """
    Scénario du bug Phase 0A : une phrase commençant dans l'overlap entrant et
    finissant après la frontière était écrite deux fois.
    """

    def _owned(self, parts, duration=1900.0):
        capture = segmented_capture("long.mp3", parts, duration=duration)
        return [(o.start, o.end, o.text) for o in resolve_owned_segments(capture)]

    def test_duplicated_sentence_in_the_incoming_overlap_is_dropped_once(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A"), (900.0, 908.0, "B")]),
            (900.0, 1810.0, "fr", [(0.0, 8.0, "B"), (20.0, 30.0, "C")]),
        ])

        assert [text for _, _, text in owned] == ["A", "B", "C"]

    def test_sentence_straddling_the_boundary_is_owned_by_the_previous_part(self):
        """
        La phrase B est vue tronquée par la partie précédente (son audio s'arrête
        à la frontière + overlap) et complète par la partie suivante. Une seule
        version est retenue, sans perte de contenu.
        """
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A"), (905.0, 910.0, "B")]),
            (900.0, 1810.0, "fr", [(5.0, 15.0, "B"), (20.0, 30.0, "C")]),
        ])

        assert [text for _, _, text in owned] == ["A", "B", "C"]
        assert owned[1][:2] == (905.0, 910.0), "La version de la partie précédente gagne."

    def test_a_genuinely_new_sentence_right_after_the_boundary_is_kept(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A"), (900.0, 908.0, "B")]),
            (900.0, 1810.0, "fr", [(0.0, 8.0, "B"), (10.5, 20.0, "C juste après")]),
        ])

        assert [text for _, _, text in owned] == ["A", "B", "C juste après"]
        assert owned[2][0] == 910.5

    def test_content_in_the_overlap_not_produced_by_the_previous_part_is_kept(self):
        """
        Priorité n° 1 : aucune perte. Si la partie précédente n'a rien émis sur la
        plage d'overlap (silence détecté, segment refait), le contenu vu par la
        partie suivante est conservé.
        """
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A")]),
            (900.0, 1810.0, "fr", [(2.0, 8.0, "B dans overlap"), (20.0, 30.0, "C")]),
        ])

        assert [text for _, _, text in owned] == ["A", "B dans overlap", "C"]

    def test_content_ending_exactly_on_the_boundary_is_not_lost(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A")]),
            (900.0, 1810.0, "fr", [(2.0, 10.0, "pile sur la frontière")]),
        ])

        assert [text for _, _, text in owned] == ["A", "pile sur la frontière"]

    def test_first_part_never_drops_anything(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 1.0, "tout"), (1.0, 2.0, "est"), (2.0, 3.0, "gardé")]),
        ])

        assert [text for _, _, text in owned] == ["tout", "est", "gardé"]

    def test_duplication_is_removed_across_three_parts(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A"), (900.0, 908.0, "B")]),
            (900.0, 1810.0, "fr", [
                (0.0, 8.0, "B"),
                (20.0, 30.0, "C"),
                (895.0, 905.0, "D"),
            ]),
            (1800.0, 1900.0, "fr", [(0.0, 5.0, "D"), (12.0, 20.0, "E")]),
        ])

        assert [text for _, _, text in owned] == ["A", "B", "C", "D", "E"]

    def test_empty_text_segments_are_ignored(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A"), (5.0, 6.0, "   "), (6.0, 8.0, "B")]),
        ])

        assert [text for _, _, text in owned] == ["A", "B"]

    def test_text_is_stripped(self):
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "\t  A  \n")]),
        ])

        assert owned[0][2] == "A"

    def test_ownership_is_deterministic(self):
        parts = [
            (0.0, 910.0, "fr", [(0.0, 5.0, "A"), (900.0, 908.0, "B")]),
            (900.0, 1810.0, "fr", [(0.0, 8.0, "B"), (20.0, 30.0, "C")]),
        ]

        assert self._owned(parts) == self._owned(parts)


# ---------------------------------------------------------------------------
# Phase 3B.1 — §16 : fenêtre d'ownership, comportement explicite aux bornes
# ---------------------------------------------------------------------------

class TestOwnershipWindowBoundaryBehavior:
    """
    Une partie technique a une fenêtre d'ownership exclusive [own_start,
    own_end) fixée par la géométrie du découpage (jamais par la longueur que
    Whisper décide spontanément de produire). Ces tests couvrent explicitement
    les deux bornes, comme demandé par Phase 3B.1 §16.
    """

    def _owned(self, parts, duration=1900.0):
        capture = segmented_capture("long.mp3", parts, duration=duration)
        return [(o.start, o.end, o.text) for o in resolve_owned_segments(capture)]

    def test_segment_starting_inside_ownership_but_ending_after_is_kept_whole(self):
        """
        Un segment qui commence dans la fenêtre d'ownership de sa partie mais
        se termine bien après la frontière suivante n'est jamais tronqué :
        seul le DÉBUT gouverne la décision d'ownership (Phase 1, §9).
        """
        owned = self._owned([
            (0.0, 910.0, "fr", [(0.0, 5.0, "A")]),
            (900.0, 1810.0, "fr", [(15.0, 1000.0, "phrase qui déborde largement")]),
        ])

        assert owned[-1][:2] == (915.0, 1900.0)
        assert owned[-1][2] == "phrase qui déborde largement"

    def test_segment_starting_at_or_after_end_of_ownership_is_dropped(self):
        """
        Un segment qui démarre à la frontière suivante (incluse) ou au-delà
        n'appartient pas à cette partie : cette position est déjà celle de la
        partie suivante, quelle que soit la longueur produite par Whisper.
        """
        owned = self._owned([
            (0.0, 910.0, "fr", [
                (0.0, 5.0, "A"),
                (910.0, 915.0, "pile sur la frontière suivante"),
                (920.0, 925.0, "après la frontière suivante"),
            ]),
            (900.0, 1810.0, "fr", [(10.0, 20.0, "B")]),
        ])

        texts = [text for _, _, text in owned]

        assert "pile sur la frontière suivante" not in texts
        assert "après la frontière suivante" not in texts
        assert texts == ["A", "B"]


# ---------------------------------------------------------------------------
# Phase 3B.1 — §11 : reproduction réduite des deux anomalies réelles
# (pastoral_retreat_v2_validation, AUDIO002 ~2710 s et AUDIO003 ~4510 s)
# ---------------------------------------------------------------------------

class TestHallucinatedTailPastCaptureWindow:
    """
    Bug réel découvert par Phase 3B : en fin de tampon long (~900 s), Whisper
    peut dégénérer en une répétition dont les timestamps dépassent la fenêtre
    technique réellement découpée pour cette partie. Cette queue ne doit ni
    étendre l'ownership de la partie qui l'a produite, ni masquer le contenu
    légitime de la partie suivante.
    """

    def _owned(self, parts, duration=4700.0):
        capture = segmented_capture("long.mp3", parts, duration=duration)
        return [(o.start, o.end, o.text) for o in resolve_owned_segments(capture)]

    def test_case_a_repeated_hallucination_past_the_window_does_not_shadow_next_part(self):
        """
        Reproduction réduite du cas AUDIO002 : la partie N (own_end ≈ 2710)
        hallucine une répétition ("Hallelujah.") jusqu'à 2728, bien après sa
        fenêtre technique ; la partie N+1 contient une phrase réelle qui
        commence dans l'overlap entrant (2700, avant 2710) et se poursuit
        jusqu'à 2730.
        """
        owned = self._owned([
            (1800.0, 2710.0, "en", [
                (899.2, 900.46, "He was not particularly praying."),
                # Queue hallucinée : dépasse la fenêtre technique de cette
                # partie (own_end = 2710).
                (924.94, 925.92, "Hallelujah."),
                (925.92, 927.06, "Hallelujah."),
                (927.06, 928.02, "Hallelujah."),
            ]),
            (2700.0, 3610.0, "en", [
                (0.0, 24.24, "He was not particularly praying for the unity of the church."),
                (24.24, 25.12, "from here."),
                (28.40, 30.74, "It is an inference, which is okay."),
            ]),
        ])

        starts = [start for start, _, _ in owned]
        texts = [text for _, _, text in owned]

        assert starts == sorted(starts), "chronologie non monotone"
        assert "Hallelujah." not in texts, (
            "la queue hallucinée hors fenêtre technique ne doit pas survivre"
        )
        assert "He was not particularly praying for the unity of the church." in texts
        assert "from here." in texts
        assert "It is an inference, which is okay." in texts

    def test_case_b_repeated_hallucination_past_the_window_is_dropped_once(self):
        """
        Reproduction réduite du cas AUDIO003 : la partie N (own_end ≈ 4510)
        hallucine une répétition ("this one is here in Nigeria") jusqu'à
        4521 ; la partie N+1 repart correctement à 4510 avec un contenu réel
        distinct.
        """
        owned = self._owned([
            (3600.0, 4510.0, "en", [
                (899.38, 900.38, "if I told you I know a white man"),
                (909.38, 910.38, "this one is here in Nigeria"),
                # Queue hallucinée : dépasse la fenêtre technique (own_end = 4510).
                (910.38, 911.38, "this one is here in Nigeria"),
                (920.38, 921.38, "this one is here in Nigeria"),
            ]),
            (4500.0, 4700.0, "en", [
                (10.28, 12.44, "So he's not like, he happens to see this man."),
                (12.70, 14.60, "If you go to internet, the man is still preaching."),
            ]),
        ])

        starts = [start for start, _, _ in owned]
        texts = [text for _, _, text in owned]

        assert starts == sorted(starts), "chronologie non monotone"
        assert texts.count("this one is here in Nigeria") == 1, (
            "la queue hallucinée hors fenêtre technique ne doit pas être dupliquée"
        )
        assert "So he's not like, he happens to see this man." in texts
        assert "If you go to internet, the man is still preaching." in texts


# ---------------------------------------------------------------------------
# Phase 3B.1 — §12 / §13 : contenu différent vs vrai doublon dans l'overlap
# ---------------------------------------------------------------------------

class TestOverlapTextConflictResolution:
    """
    La déduplication d'overlap ne doit jamais se fonder uniquement sur le
    chevauchement des timestamps (§12). Une comparaison textuelle minimale et
    déterministe (normalisation simple, sans similarité floue) départage un
    doublon réel (§13) d'un contenu réellement différent.
    """

    def _owned(self, parts, duration=1900.0):
        capture = segmented_capture("long.mp3", parts, duration=duration)
        return [(o.start, o.end, o.text) for o in resolve_owned_segments(capture)]

    def test_different_content_in_the_overlap_is_not_treated_as_a_duplicate(self):
        """
        §12 : même zone temporelle apparente, textes différents. Le système
        ne doit pas conclure à un doublon uniquement parce que les timestamps
        se chevauchent — le contenu réel de la partie suivante est conservé.

        Comme pour le bug réel, la partie précédente doit avoir une preuve
        structurelle de dégradation (une queue hors de sa propre fenêtre
        technique) pour que son contenu d'overlap puisse être supplanté par un
        texte différent — voir aussi le test
        `test_different_content_without_overrun_evidence_keeps_previous_part_default`
        ci-dessous pour le cas symétrique, sans preuve, où la partie
        précédente l'emporte toujours.
        """
        owned = self._owned([
            (0.0, 910.0, "en", [
                (895.0, 908.0, "Hallelujah."),
                # Queue hallucinée hors fenêtre technique (own_end = 910) :
                # preuve structurelle que cette partie s'est dégradée.
                (925.0, 926.0, "Hallelujah."),
            ]),
            (900.0, 1810.0, "en", [
                (0.0, 24.0, "he was not particularly praying for the unity of the church"),
                (30.0, 40.0, "next real sentence"),
            ]),
        ])

        starts = [start for start, _, _ in owned]
        texts = [text for _, _, text in owned]

        assert starts == sorted(starts)
        assert "he was not particularly praying for the unity of the church" in texts
        assert "next real sentence" in texts

    def test_different_content_without_overrun_evidence_keeps_previous_part_default(self):
        """
        Garde-fou contre une régression découverte pendant Phase 3B.1 : sans
        preuve structurelle de dégradation de la partie précédente, une simple
        différence de texte dans l'overlap est une variation normale entre
        deux appels Whisper indépendants — la politique par défaut de la
        Phase 1 s'applique (la partie précédente l'emporte). Appliquer la
        supersession ici effacerait à tort du contenu réel et légitime à
        chaque frontière technique du corpus, ce qui a été observé et corrigé.
        """
        owned = self._owned([
            (0.0, 910.0, "en", [
                (895.0, 902.0, "I was talking about the son of Matthew."),
                (904.0, 905.0, "Hallelujah."),
                (906.0, 907.0, "Thank you."),
                (908.0, 909.9, "But that's, that's, please."),
            ]),
            (900.0, 1810.0, "en", [(0.0, 1.26, "I was")]),
        ])

        texts = [text for _, _, text in owned]

        assert texts == [
            "I was talking about the son of Matthew.",
            "Hallelujah.",
            "Thank you.",
            "But that's, that's, please.",
        ], "sans preuve de dégradation, la partie précédente doit être intégralement conservée"

    def test_true_duplicate_in_the_overlap_is_still_deduplicated(self):
        """
        §13 : même passage réellement redit (texte identique après
        normalisation) dans l'overlap. Le mécanisme existant de
        déduplication continue à éviter une duplication artificielle.
        """
        owned = self._owned([
            (0.0, 910.0, "en", [(895.0, 908.0, "the kingdom of God")]),
            (900.0, 1810.0, "en", [
                (0.0, 8.0, "the kingdom of God"),
                (20.0, 30.0, "next real sentence"),
            ]),
        ])

        texts = [text for _, _, text in owned]

        assert texts.count("the kingdom of God") == 1
        assert texts == ["the kingdom of God", "next real sentence"]

    def test_duplicate_detection_ignores_case_and_punctuation_only(self):
        """
        La normalisation reste minimale et déterministe : casse et
        ponctuation n'empêchent pas de reconnaître un doublon réel, mais un
        texte différent au fond n'est jamais assimilé à un doublon.
        """
        owned = self._owned([
            (0.0, 910.0, "en", [(895.0, 908.0, "The Kingdom of God!")]),
            (900.0, 1810.0, "en", [(0.0, 8.0, "the kingdom of god")]),
        ])

        assert [text for _, _, text in owned] == ["The Kingdom of God!"]


# ---------------------------------------------------------------------------
# 18 / 19 / 41 — Langues
# ---------------------------------------------------------------------------

class TestLanguages:

    def test_french_only_project(self):
        document = build_transcript_document(
            "p",
            [
                direct_capture("a.mp3", [(0.0, 10.0, "bonjour")], language="fr"),
                direct_capture("b.mp3", [(0.0, 10.0, "salut")], language="fr"),
            ],
        )

        assert document.primary_language == "fr"
        assert document.detected_languages == ["fr"]
        assert [s.detected_language for s in document.sources] == ["fr", "fr"]

    def test_english_only_project(self):
        document = build_transcript_document(
            "p", [direct_capture("a.mp3", [(0.0, 10.0, "hello")], language="en")]
        )

        assert document.primary_language == "en"
        assert document.detected_languages == ["en"]

    @pytest.mark.parametrize("language", ["de", "es", "sw", "ja"])
    def test_language_outside_fr_en_is_preserved_and_not_translated(self, language):
        """
        Contrat V2 : une langue hors fr/en n'entraîne plus de retranscription
        forcée en anglais, et aucun contenu n'est traduit.
        """
        document = build_transcript_document(
            "p",
            [direct_capture("a.mp3", [(0.0, 10.0, "contenu original")], language=language)],
        )

        assert document.sources[0].detected_language == language
        assert document.primary_language == language
        assert document.detected_languages == [language]
        assert document.segments[0].text == "contenu original"

    def test_multilingual_project_is_representable(self):
        document = build_transcript_document(
            "p",
            [
                direct_capture("a.mp3", [(0.0, 100.0, "fr un")], language="fr"),
                direct_capture("b.mp3", [(0.0, 100.0, "fr deux")], language="fr"),
                direct_capture("c.mp3", [(0.0, 40.0, "english")], language="en"),
            ],
        )

        assert [s.detected_language for s in document.sources] == ["fr", "fr", "en"]
        assert document.detected_languages == ["en", "fr"]
        assert document.primary_language == "fr"

    def test_primary_language_is_the_longest_transcribed_duration(self):
        document = build_transcript_document(
            "p",
            [
                direct_capture("a.mp3", [(0.0, 20.0, "court fr")], language="fr"),
                direct_capture("b.mp3", [(0.0, 500.0, "long en")], language="en"),
            ],
        )

        assert document.primary_language == "en"

    def test_primary_language_tie_is_broken_alphabetically(self):
        document = build_transcript_document(
            "p",
            [
                direct_capture("a.mp3", [(0.0, 100.0, "fr")], language="fr"),
                direct_capture("b.mp3", [(0.0, 100.0, "en")], language="en"),
            ],
        )

        assert document.primary_language == "en"
        assert build_transcript_document(
            "p",
            [
                direct_capture("b.mp3", [(0.0, 100.0, "en")], language="en"),
                direct_capture("a.mp3", [(0.0, 100.0, "fr")], language="fr"),
            ],
        ).primary_language == "en"

    def test_source_language_is_the_dominant_language_of_its_parts(self):
        capture = segmented_capture(
            "long.mp3",
            [
                (0.0, 910.0, "fr", [(0.0, 600.0, "beaucoup de français")]),
                (900.0, 1810.0, "en", [(20.0, 60.0, "a little english")]),
            ],
        )

        document = build_transcript_document("p", [capture])

        assert document.sources[0].detected_language == "fr"

    def test_source_without_any_segment_falls_back_to_the_detected_language(self):
        document = build_transcript_document(
            "p", [direct_capture("muet.mp3", [], language="sw")]
        )

        assert document.sources[0].detected_language == "sw"
        assert document.detected_languages == ["sw"]
        assert document.primary_language == "sw"


# ---------------------------------------------------------------------------
# 34 — Statistiques
# ---------------------------------------------------------------------------

class TestStats:

    @pytest.fixture
    def document(self):
        captures = [
            direct_capture(
                "a.mp3", [(0.0, 5.0, "trois mots ici")], duration=300.5
            ),
            direct_capture(
                "b.mp3",
                [(0.0, 5.0, "deux mots"), (5.0, 10.0, "un")],
                duration=600.25,
            ),
        ]
        return build_transcript_document("p", captures)

    def test_counts_match_the_content(self, document):
        assert document.stats.source_count == 2
        assert document.stats.segment_count == 3

    def test_duration_is_the_sum_of_source_durations(self, document):
        assert document.stats.duration_seconds == 900.75

    def test_word_count_is_the_sum_of_segment_words(self, document):
        assert document.stats.word_count == 6

    def test_empty_project_produces_empty_stats(self):
        document = build_transcript_document("p", [])

        assert document.stats.source_count == 0
        assert document.stats.segment_count == 0
        assert document.stats.duration_seconds == 0.0
        assert document.segments == []
