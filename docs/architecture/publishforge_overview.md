# PublishForge — Vue d'ensemble générale

## Identité du projet

| Champ | Valeur |
|-------|--------|
| Nom applicatif | **PublishForge** (anciennement TranscriptionAI) |
| Langage | Python 3.11 |
| Interface principale | Streamlit (UI web locale) |
| Interface secondaire | CLI (`main.py`) — menu interactif + argparse |
| Moteur de transcription | `faster-whisper` (modèle `large-v3`, CPU) |
| Moteurs IA | Ollama (`qwen3:8b`), LM Studio, OpenAI, Fake (tests) |
| Stockage | Fichiers locaux uniquement — aucune base de données |
| Export DOCX | `python-docx` |
| Export PDF | WeasyPrint / ReportLab |
| Version | Voir fichier `VERSION` à la racine |

---

## Mission

PublishForge transforme automatiquement des enregistrements audio bruts
en publications professionnelles prêtes à l'impression ou à la diffusion numérique.

**Pipeline fondamental :**

```
Audio → Transcription → Fusion → Chunks → IA → Révision → Document → DOCX → PDF → ZIP
```

---

## Deux modes de production

### MODE PUBLICATION _(actuel + en cours de complétion)_

```
Audio
  └─► Transcription
        └─► Fusion des transcriptions
              └─► Découpage en chunks
                    └─► Traitement IA (clean_transcript / book_chapter)
                          └─► Révision humaine (optionnelle)
                                └─► Document maître (document_final.md)
                                      ├─► Livre complet (DOCX + PDF)
                                      ├─► Livret résumé
                                      ├─► EPUB ← (roadmap)
                                      └─► Amazon KDP ← (roadmap)
```

### MODE FORMATION _(roadmap)_

```
Audio
  └─► [même pipeline commun jusqu'à document_final.md]
        └─► Training Mode Engine
              ├─► Manuel du participant
              ├─► Cahier d'exercices
              ├─► Guide du formateur
              ├─► Présentation PowerPoint
              └─► Quiz interactif
```

---

## Points d'entrée

| Fichier | Type | Usage principal |
|---------|------|-----------------|
| `streamlit_app.py` | UI Web Streamlit | Interface opérateur complète (8 pages) |
| `main.py` | CLI Python | Automatisation, serveurs sans tête, CI |
| `transcribe.py` | Script legacy | Ancien pipeline de transcription standalone |
| `build_book.py` | Script utilitaire | Construction document via modules `book/` |
| `check_system.py` | Diagnostic | Vérification des dépendances système |

---

## Arborescence complète du projet

```
C:\TranscriptionAI\
│
├── main.py                          ← Point d'entrée CLI principal
├── streamlit_app.py                 ← Point d'entrée UI Streamlit
├── transcribe.py                    ← Script transcription legacy (non utilisé par pipeline_runner)
├── build_book.py                    ← Construction livre via modules book/
├── check_system.py                  ← Diagnostic système
├── test_ai.py                       ← Test moteur IA
├── test_project_manager.py          ← Test project_manager
├── test_semantic_cleaner.py         ← Test semantic_cleaner
├── test_transcript_merger.py        ← Test transcript_merger
├── requirements.txt
├── VERSION
│
├── app/                             ← Modules applicatifs principaux
│   ├── config.py                    ← Configuration globale (Whisper, IA, Couvertures)
│   ├── paths.py                     ← Chemins système (DEPOT_DIR, SORTIE_DIR, etc.)
│   ├── logger.py                    ← Logger événements JSON
│   ├── sleep_guard.py               ← Garde veille Windows (prevent_sleep / allow_sleep_again)
│   │
│   ├── project_manager.py           ← Découverte projets dans depot/ → AudioProject
│   ├── project_state.py             ← Machine d'état JSON (project_state.json)
│   ├── project_metadata.py          ← Métadonnées YAML par projet (project.yaml)
│   ├── production_service.py        ← Façade haut niveau (process_all / process_project / rebuild)
│   ├── pipeline_runner.py           ← Exécuteur des 16 étapes du pipeline
│   ├── ui_status_service.py         ← Service statut projets pour l'UI
│   │
│   ├── transcription_service.py     ← Transcription directe faster-whisper
│   ├── segmented_transcription_service.py ← Transcription segmentée (longs fichiers + reprise)
│   ├── audio_utils.py               ← Utilitaires audio (ffmpeg, durée, split, timestamps)
│   ├── transcript_merger.py         ← Fusion *.txt → transcript_complet.txt
│   │
│   ├── chunk_service.py             ← Découpage transcript → chunks (8000 chars, PARTIE-aware)
│   │
│   ├── ai_engine.py                 ← Moteurs IA (BaseAIEngine + 4 implémentations)
│   ├── ai_processor.py              ← Orchestration traitement IA des chunks pending
│   ├── prompt_manager.py            ← 8 templates de prompts + prompts par projet
│   ├── prompt_utils.py              ← Rendu sécurisé {{TEXT}} (évite .format() dangereux)
│   ├── reprocess_chunk.py           ← Retraitement d'un chunk individuel
│   │
│   ├── correction_review_service.py ← Génération fichiers .corrections.md
│   ├── correction_apply_service.py  ← Application corrections humaines → reviewed/
│   │
│   ├── final_document_builder.py    ← Fusion chunks → document_final.md + document_clean.md
│   ├── global_editor_service.py     ← Harmonisation éditoriale globale (optionnel, LLM)
│   ├── editorial_transformer.py     ← Transformation éditoriale (pipeline orchestrator)
│   ├── editorial_structure.py       ← Structure éditoriale
│   ├── editorial_cleanup.py         ← Nettoyage éditorial
│   ├── editorial_finalizer.py       ← Finalisation éditoriale
│   ├── editorial_quality_guard.py   ← Garde qualité éditoriale
│   │
│   ├── publication_template_service.py  ← Template publication Markdown
│   ├── publication_orchestrator.py      ← Pipeline complet éditorial → livraison (8 étapes)
│   ├── publication_builder.py           ← Constructeur de publication
│   ├── publication_sanitizer.py         ← Nettoyeur publication
│   ├── publication_cleaner.py           ← Nettoyage Markdown publication
│   ├── publication_metadata.py          ← Métadonnées de publication
│   ├── publication_mode_engine.py       ← Moteur de mode publication
│   ├── publication_theme.py             ← Thème visuel publication
│   ├── publication_quality_service.py   ← Validation qualité publication
│   ├── document_language.py             ← Détection langue du document
│   ├── metadata_editor_service.py       ← Éditeur métadonnées (projet.yaml)
│   │
│   ├── docx_export_service.py       ← Export DOCX document final
│   ├── pdf_export_service.py        ← Export PDF document final
│   ├── publication_docx_engine.py   ← Moteur DOCX publication
│   ├── publication_pdf_engine.py    ← Moteur PDF publication
│   │
│   ├── cover_generation_service.py  ← Service couvertures (stratégie user/généré/typo)
│   ├── cover_builder.py             ← Constructeur couvertures
│   ├── cover_engine.py              ← Moteur couvertures
│   ├── cover_image_engine.py        ← Moteur images couvertures (DALL-E / SDXL / Fake)
│   ├── cover_layout_service.py      ← Dimensions standards (DPI, format lettre/A4/digest)
│   │
│   ├── client_export_service.py     ← Export ZIP client
│   ├── client_package.py            ← Construction package client
│   ├── report_service.py            ← Génération rapports JSON
│   ├── file_utils.py                ← Utilitaires fichiers (hash SHA256, sanitize, unique_path)
│   │
│   ├── image_engine/                ← Sous-module génération images IA
│   │   ├── image_config.py
│   │   ├── image_prompt_builder.py
│   │   ├── image_provider_base.py
│   │   ├── image_service.py
│   │   └── sdxl_provider.py
│   │
│   ├── ui/                          ← Pages Streamlit
│   │   ├── page_dashboard.py        ← Tableau de bord + statut global
│   │   ├── page_metadata.py         ← Édition métadonnées projet
│   │   ├── page_editorial.py        ← Lancement pipeline éditorial
│   │   ├── page_publication.py      ← Génération publication
│   │   ├── page_cover.py            ← Génération / sélection couverture
│   │   ├── page_docx_pdf.py         ← Exports DOCX / PDF
│   │   ├── page_client_package.py   ← Génération package client ZIP
│   │   ├── page_settings.py         ← Paramètres application
│   │   └── ui_utils.py              ← Utilitaires UI partagés
│   │
│   ├── book/                        ← Parser transcript pour mode livre
│   │   └── transcript_parser.py
│   │
│   └── tests/                       ← Tests unitaires
│       ├── test_chunking_idempotency.py
│       ├── test_partie_chunking.py
│       └── test_prompt_rendering.py
│
├── book/                            ← Modules construction livre (expérimental / legacy)
│   ├── markdown_builder.py
│   ├── outline_builder.py
│   ├── paragraph_builder.py
│   ├── paragraph_semantic_cleaner.py
│   ├── section_builder.py
│   ├── section_consolidator.py
│   ├── semantic_cleaner.py
│   ├── sentence_merger.py
│   ├── text_cleaner.py
│   ├── theme_renderer.py
│   ├── title_builder.py
│   ├── topic_group_builder.py
│   ├── topic_similarity.py
│   ├── transcript_parser.py
│   ├── hallucination_filter.py
│   ├── keyword_extractor.py
│   └── local_ai_service.py
│
├── depot/                           ← ENTRÉE : fichiers audio bruts
│   └── <projet>/                    ← Un dossier par projet
│       ├── *.mp3 / *.ogg / *.wav / *.m4a
│       └── prompt.md                ← Prompt IA personnalisé (optionnel)
│
├── sortie/                          ← SORTIE : documents générés
│   └── <projet>/
│       ├── project_state.json       ← Machine d'état du projet
│       ├── report.json              ← Rapport d'exécution
│       ├── transcripts/             ← Transcriptions individuelles (.txt horodatées)
│       ├── segment_transcripts/     ← Transcriptions par segment (longs fichiers)
│       │   └── <stem>/              ← Un sous-dossier par fichier audio long
│       │       ├── part_001.txt
│       │       └── part_NNN.txt
│       ├── audio_segments/          ← Segments audio MP3 découpés
│       │   └── <stem>/
│       │       ├── part_001.mp3
│       │       └── part_NNN.mp3
│       ├── merged/                  ← transcript_complet.txt fusionné
│       ├── chunks/                  ← Chunks bruts (.txt, 8000 chars max)
│       │   └── obsolete/            ← Chunks périmés déplacés ici
│       ├── processed/               ← Chunks traités par l'IA (.md Markdown)
│       │   └── obsolete/
│       ├── corrections/             ← Fichiers de révision humaine (.corrections.md)
│       ├── reviewed/                ← Chunks après application corrections (.md)
│       ├── errors/                  ← Fichiers d'erreur IA par chunk (.error.txt)
│       ├── final/                   ← Documents finaux fusionnés
│       │   ├── document_final.md    ← Version interne avec structure
│       │   ├── document_clean.md    ← Version publiable sans artefacts
│       │   ├── document_final.docx
│       │   └── document_publication.pdf
│       ├── harmonized/              ← document_harmonized.md (optionnel)
│       ├── cover/                   ← Couverture générée
│       │   ├── cover.jpg
│       │   └── cover_metadata.json
│       ├── publication/             ← Publication finale
│       │   ├── publication.md
│       │   ├── publication.docx
│       │   └── publication.pdf
│       └── client/                  ← Package ZIP livraison client
│           └── <projet>_CLIENT.zip
│
├── temp/                            ← Fichiers temporaires (ancien pipeline)
├── archives/                        ← Fichiers audio archivés après traitement
├── rejets/                          ← Fichiers audio rejetés (vides, corrompus)
├── logs/                            ← run_YYYYMMDD_HHMMSS.json par exécution
├── cache/                           ← Cache (non utilisé activement)
└── docs/                            ← Documentation
    └── architecture/                ← Ce dossier
```

---

## Dépendances externes clés

| Bibliothèque | Rôle |
|-------------|------|
| `faster-whisper` | Transcription audio locale (CTranslate2) |
| `streamlit` | Interface web locale |
| `python-docx` | Génération fichiers DOCX |
| `requests` | Appels HTTP vers Ollama et LM Studio |
| `openai` | SDK OpenAI (import différé, optionnel) |
| `Pillow` | Traitement images couvertures |
| `ffmpeg` (binaire) | Découpage et conversion audio |
| `av` (PyAV) | Utilitaires audio Python |

---

## Configuration globale (`app/config.py`)

| Section | Variables clés |
|---------|---------------|
| Transcription | `MODEL_NAME`, `DEVICE`, `SUPPORTED_EXTENSIONS`, `ALLOWED_LANGUAGES` |
| Segmentation | `LONG_AUDIO_THRESHOLD_MINUTES=30`, `AUDIO_SEGMENT_MINUTES=15`, `AUDIO_SEGMENT_OVERLAP_SECONDS=10` |
| IA | `AI_PROVIDER`, `AI_TASK`, `OLLAMA_MODEL="qwen3:8b"` |
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT_SECONDS=1200`, `OLLAMA_OPTIONS` |
| LM Studio | `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL="gpt-4o-mini"` |
| Couvertures | `COVER_PROVIDER`, `COVER_STYLE`, `DEFAULT_COVER_DPI=300` |
| Harmonisation | `GLOBAL_EDITOR_ENABLED`, `GLOBAL_EDITOR_MODE` |
