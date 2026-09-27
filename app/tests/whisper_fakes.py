"""
Doublures minimales de faster-whisper pour les tests.

Reproduit uniquement le contrat réellement consommé par le code de production :

    segments, info = model.transcribe(str(audio_path))
    segments, info = model.transcribe(str(audio_path), language="en")

    segment.start / segment.end / segment.text
    info.language

Aucun modèle n'est chargé, aucun fichier n'est téléchargé, aucune transcription
réelle n'est effectuée.
"""

from __future__ import annotations

from pathlib import Path


class FakeWhisperSegment:
    """Segment retourné par model.transcribe()."""

    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text

    def __repr__(self) -> str:
        return f"FakeWhisperSegment({self.start}, {self.end}, {self.text!r})"


class FakeWhisperInfo:
    """Objet 'info' retourné par model.transcribe()."""

    def __init__(self, language: str):
        self.language = language


def _as_segments(raw) -> list[FakeWhisperSegment]:
    out = []
    for item in raw:
        if isinstance(item, FakeWhisperSegment):
            out.append(item)
        else:
            start, end, text = item
            out.append(FakeWhisperSegment(start, end, text))
    return out


class FakeWhisperModel:
    """
    Remplace WhisperModel dans les tests.

    Args:
        segments:         segments retournés par défaut, sous forme
                          [(start, end, text), ...].
        language:         langue rapportée par info.language.
        segments_by_name: segments spécifiques par nom de fichier audio
                          (ex. {"part_002.mp3": [(0, 8, "B")]}).
        fail_on:          noms de fichiers audio pour lesquels transcribe()
                          lève une exception (erreur récupérable).
        interrupt_on:     noms de fichiers audio pour lesquels transcribe() lève
                          KeyboardInterrupt — simule un arrêt brutal du processus,
                          non rattrapé par les `except Exception` du service.

    Instrumentation :
        model.calls        -> [(nom_fichier, kwargs), ...] dans l'ordre d'appel
        model.call_count   -> nombre total d'appels à transcribe()
        model.names_called -> liste des noms de fichiers transcrits
    """

    def __init__(
        self,
        segments=(),
        language: str = "fr",
        segments_by_name: dict | None = None,
        fail_on=(),
        interrupt_on=(),
    ):
        self._default = list(segments)
        self._by_name = dict(segments_by_name or {})
        self.language = language
        self.fail_on = set(fail_on)
        self.interrupt_on = set(interrupt_on)
        self.calls: list[tuple[str, dict]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def names_called(self) -> list[str]:
        return [name for name, _ in self.calls]

    def transcribe(self, audio_path, **kwargs):
        name = Path(audio_path).name
        self.calls.append((name, kwargs))

        if name in self.interrupt_on:
            raise KeyboardInterrupt(f"process interrupted on {name}")

        if name in self.fail_on:
            raise RuntimeError(f"fake whisper failure on {name}")

        raw = self._by_name.get(name, self._default)
        info_language = "en" if kwargs.get("language") == "en" else self.language

        return iter(_as_segments(raw)), FakeWhisperInfo(info_language)


class ExplodingIterationModel:
    """
    Modèle dont transcribe() réussit mais dont l'itération des segments échoue.

    Permet de figer le comportement V1 lorsque Whisper casse en cours de route.
    """

    def __init__(self, segments_before_error=(), language: str = "fr"):
        self._before = list(segments_before_error)
        self.language = language
        self.calls: list[tuple[str, dict]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def transcribe(self, audio_path, **kwargs):
        self.calls.append((Path(audio_path).name, kwargs))

        def _generator():
            for segment in _as_segments(self._before):
                yield segment
            raise RuntimeError("whisper crashed mid-iteration")

        return _generator(), FakeWhisperInfo(self.language)
