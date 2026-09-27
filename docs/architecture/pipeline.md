# Pipeline Global — PublishForge

## Vue d'ensemble des modes d'exécution

| Mode | Fonction | Étapes couvertes |
|------|----------|-----------------|
| Pipeline complet | `run_project_pipeline()` | 1 → 16 |
| Rebuild depuis chunks | `run_full_rebuild_pipeline()` | 3 → 16 |
| Exports uniquement | `run_exports_only()` | 8 → 16 |
| Rapport uniquement | `run_report_only()` | 16 |
| Publication orchestrée | `generate_complete_client_package()` | sous-pipeline dédié |

---

## Pipeline complet — 16 étapes

```mermaid
flowchart TD
    START(["🚀 Début\nproject_manager.discover_projects()"])

    START --> PRE["Pré-conditions\n• Chargement modèle Whisper\n• prevent_sleep()\n• write_execution_status(running)"]

    PRE --> STEP1

    subgraph STEP1["Étape 1 — Transcription"]
        direction TB
        T1{"Durée > 30 min ?"}
        T1 -->|Non| T2["transcription_service\ntranscribe_audio_to_txt()\ndirecte"]
        T1 -->|Oui| T3["segmented_transcription_service\ntranscribe_long_audio_with_segments()"]
        T3 --> T4["Segments 15min\n+ overlap 10s\nvia ffmpeg"]
        T4 --> T5["Whisper segment par segment\nSauvegarde state après chaque segment"]
        T5 --> T6["Fusion des segments\n_merge_segment_transcripts()"]
        T2 --> TOUT1["transcripts/<stem>.txt\nFormat: [HH:MM -> HH:MM] texte"]
        T6 --> TOUT1
        T1_SKIP{"Audio déjà transcrit ?\nis_audio_already_transcribed()"}
        T1_SKIP -->|Oui| SKIP1["SKIP — hash identique\n+ transcript présent"]
        T1_SKIP -->|Non| T1
    end

    STEP1 --> STEP2

    subgraph STEP2["Étape 2 — Fusion des transcriptions"]
        direction TB
        M1["transcript_merger\nmerge_project_transcripts()"]
        M1 --> M2["merged/transcript_complet.txt\nEn-têtes PARTIE N — NomFichier\nentre chaque fichier"]
    end

    STEP2 --> STEP3

    subgraph STEP3["Étape 3 — Génération des chunks"]
        direction TB
        C1["chunk_service\ncreate_project_chunks()\nmax_chars=8000"]
        C1 --> C2["parse_transcript_into_partie_blocks()\nDétection blocs PARTIE"]
        C2 --> C3["split_text_into_chunks()\nPriorité: === → timestamps → ¶ → lignes"]
        C3 --> C4["validate_chunk_content()\nmin 50 chars, 10 mots"]
        C4 --> C5["write_text_if_changed()\nÉcriture conditionnelle SHA256"]
        C5 --> C6["chunks/chunk_001.txt\n...\nchunks/chunk_NNN.txt"]
        C6 --> C7["update_chunk_state()\nStatuts: pending_ai | done | unchanged"]
    end

    STEP3 --> STEP4

    subgraph STEP4["Étape 4 — Traitement IA"]
        direction TB
        AI1["ai_processor\nprocess_project_chunks()"]
        AI1 --> AI2{"Status chunk ?"}
        AI2 -->|done + processed présent| AI3["SKIP — déjà traité"]
        AI2 -->|skipped_empty| AI4["SKIP — contenu vide"]
        AI2 -->|pending_ai / failed| AI5["get_ai_engine()\nOllama / LMStudio / OpenAI / Fake"]
        AI5 --> AI6["build_prompt()\nprompt_manager\nPriorité: prompt.md > AI_TASK > fallback"]
        AI6 --> AI7["send_prompt()\nAppel HTTP vers LLM"]
        AI7 --> AI8["processed/chunk_NNN.md\nMarkdown éditorial"]
        AI8 --> AI9["update chunk state → done\nsave_project_state()"]
        AI7 -->|Erreur| AI10["errors/chunk_NNN.error.txt\nTraceback complet\nChunk → failed"]
    end

    STEP4 --> STEP5

    subgraph STEP5["Étape 5 — Génération fichiers de révision"]
        direction TB
        R1["correction_review_service\ngenerate_review_files()"]
        R1 --> R2["Parse segments timestampés\ndu chunk source (.txt)"]
        R2 --> R3["corrections/chunk_NNN.corrections.md\n### Texte actuel\n### Texte corrigé [À COMPLÉTER]"]
        R3 -.->|"Révision humaine\n(optionnelle, hors pipeline)"| R4["Éditeur remplissent\nles sections 'Texte corrigé'"]
    end

    STEP5 --> STEP6

    subgraph STEP6["Étape 6 — Application des corrections"]
        direction TB
        A1["correction_apply_service\napply_corrections()"]
        A1 --> A2{"Fichier .corrections.md\nexiste ?"}
        A2 -->|Non| A3["reviewed/ = copie de processed/"]
        A2 -->|Oui| A4["_parse_corrections()\nFiltre [À COMPLÉTER]"]
        A4 --> A5["_apply_corrections_to_content()\nRemplacement première occurrence"]
        A5 --> A6["reviewed/chunk_NNN.md\nVersion corrigée"]
        A3 --> A6
    end

    STEP6 --> STEP7

    subgraph STEP7["Étape 7 — Construction document final"]
        direction TB
        F1["final_document_builder\nbuild_final_document()"]
        F1 --> F2["list_effective_chunks()\nreviewd/ prioritaire sur processed/"]
        F2 --> F3["compute_effective_signature()\nHash MD5 par fichier source"]
        F3 --> F4{"Signature inchangée ?"}
        F4 -->|Oui| F5["SKIP — document déjà à jour"]
        F4 -->|Non| F6["Fusion de tous les chunks"]
        F6 --> F7["final/document_final.md\n(version interne, structure visible)"]
        F6 --> F8["final/document_clean.md\n(version publiable sans artefacts)"]
    end

    STEP7 --> STEP8

    subgraph STEP8["Étape 8 — Harmonisation éditoriale (optionnelle)"]
        direction TB
        H1{"GLOBAL_EDITOR_ENABLED ?"}
        H1 -->|Non| H2["SKIP — config désactivé"]
        H1 -->|Oui| H3["global_editor_service\nharmonize_document()"]
        H3 --> H4["Mode: light / medium / aggressive"]
        H4 --> H5["Appel LLM avec prompt\nglobal_harmonization_*"]
        H5 --> H6["harmonized/document_harmonized.md"]
    end

    STEP8 --> STEP9

    subgraph STEP9["Étape 9 — Génération couverture"]
        direction TB
        COV1["cover_generation_service\ngenerate_cover()"]
        COV1 --> COV2["resolve_cover_strategy()"]
        COV2 --> COV3{"Stratégie ?"}
        COV3 -->|"Image utilisateur"| COV4["depot/<projet>/cover.jpg\ncopie directe"]
        COV3 -->|"Générée (DALL-E/SDXL)"| COV5["cover_image_engine\nAppel API image"]
        COV3 -->|"Typographique"| COV6["Couverture texte seul"]
        COV4 & COV5 & COV6 --> COV7["cover/cover.jpg\ncover/cover_metadata.json"]
    end

    STEP9 --> STEP10

    subgraph STEP10["Étape 10 — Publication Markdown"]
        direction TB
        P1["publication_template_service\nbuild_publication_markdown()"]
        P1 --> P2["publication/publication.md"]
    end

    STEP10 --> STEP11

    subgraph STEP11["Étapes 11-14 — Exports"]
        direction TB
        E1["docx_export_service\nexport_docx()"] --> E1O["final/document_final.docx"]
        E2["pdf_export_service\nexport_pdf()"] --> E2O["final/document_publication.pdf"]
        E3["publication_docx_engine\nexport_publication_docx()"] --> E3O["publication/publication.docx"]
        E4["publication_pdf_engine\nexport_publication_pdf()"] --> E4O["publication/publication.pdf"]
    end

    STEP11 --> STEP15

    subgraph STEP15["Étape 15 — Package client"]
        direction TB
        Z1["client_export_service\nexport_client_zip()"]
        Z1 --> Z2["client/<projet>_CLIENT.zip\n(PDF + DOCX + couverture)"]
    end

    STEP15 --> STEP16

    subgraph STEP16["Étape 16 — Rapport"]
        direction TB
        REP1["report_service\nbuild_project_report()"]
        REP1 --> REP2["sortie/<projet>/report.json"]
        REP1 --> REP3["logs/run_YYYYMMDD_HHMMSS.json"]
    end

    STEP16 --> POSTPIPE

    subgraph POSTPIPE["Post-pipeline"]
        direction TB
        QC["_check_publication_quality()\npublication_quality_service"]
        QC --> VD["_verify_deliverables()\ndocument_final.md + publication.pdf obligatoires"]
        VD --> STATUS["write_execution_status()\nsuccess | error | partial"]
        STATUS --> SLEEP["allow_sleep_again()"]
    end

    SLEEP --> END(["✅ Fin\nRésultat: success | error | partial"])

    style STEP1 fill:#1a3a5c,stroke:#4a9edd,color:#eee
    style STEP3 fill:#3a1a5c,stroke:#9a4add,color:#eee
    style STEP4 fill:#5c1a1a,stroke:#dd4a4a,color:#eee
    style STEP7 fill:#1a5c1a,stroke:#4add4a,color:#eee
    style STEP9 fill:#5c3a1a,stroke:#dd9a4a,color:#eee
    style STEP11 fill:#1a3a5c,stroke:#4a9edd,color:#eee
```

---

## Pipeline de transcription segmentée (détail)

```mermaid
flowchart TD
    A["Fichier audio .mp3/.ogg/.wav/.m4a"]
    A --> B["get_audio_duration_seconds()\nvia ffmpeg/av"]
    B --> C{"duration > LONG_AUDIO_THRESHOLD_MINUTES\n(30 minutes par défaut) ?"}

    C -->|Non| DIRECT["Transcription directe\ntranscription_service.transcribe_audio_to_txt()"]
    DIRECT --> TR_OUT["transcripts/<stem>.txt"]

    C -->|Oui| SEG

    subgraph SEG["Transcription segmentée"]
        direction TB
        S1["_get_segment_boundaries()\nSégments de AUDIO_SEGMENT_MINUTES=15 min\n+ AUDIO_SEGMENT_OVERLAP_SECONDS=10s"]
        S1 --> S2["_build_segment_list()\nCrée les descripteurs de segments\nDossiers: audio_segments/ + segment_transcripts/"]
        S2 --> S3["_restore_transcribed_segments()\nRestauration depuis project_state.json\nsi hash identique → reprise immédiate"]
        S3 --> S4{"Segments déjà\ntranscrits ?"}
        S4 -->|Oui| S5["SKIP — status=transcribed\nfichier .txt présent"]
        S4 -->|Non| S6["_create_missing_audio_segments()\nffmpeg -ss start -t duration\nlibmp3lame q:a 2"]
        S6 --> S7["Whisper model.transcribe(segment_audio)"]
        S7 --> S8["Ajout offset timestamps\nglobal = local + start_seconds"]
        S8 --> S9["Filtre overlap entrant\nseg.end <= effective_start_local → ignoré"]
        S9 --> S10["segment_transcripts/<stem>/part_NNN.txt"]
        S10 --> S11["update_segment_in_state()\nsave_project_state()\n← Sauvegarde immédiate"]
        S5 --> S12
        S11 --> S12["Segment suivant"]
        S12 --> S13{"Autres\nsegments ?"}
        S13 -->|Oui| S4
        S13 -->|Non| S14
    end

    SEG --> S14["_merge_segment_transcripts()\nConcaténation simple\n(timestamps déjà globaux)"]
    S14 --> TR_OUT2["transcripts/<stem>.txt\nTranscript final fusionné"]
    S14 -->|Erreur partielle| ERR["mark_audio_partial_error()\nSauvegarde segments OK\npour reprise ultérieure"]
```

---

## Pipeline de traitement IA (détail)

```mermaid
flowchart TD
    A["ai_processor.process_project_chunks()"]
    A --> B["get_ai_engine()\nSelon AI_PROVIDER dans config.py"]
    B --> C["Lecture project_state.json\nchunks_state"]
    C --> D["Pour chaque chunk dans chunks_state"]

    D --> E{"Status du chunk ?"}
    E -->|"skipped_empty"| SKIP1["SKIP\nContenu vide détecté"]
    E -->|"done + !needs_ai + processed présent"| SKIP2["SKIP\nDéjà traité, inchangé"]
    E -->|"pending_ai / done sans processed"| PROC

    subgraph PROC["Traitement du chunk"]
        direction TB
        P1["Lecture chunks/chunk_NNN.txt"]
        P1 --> P2["_strip_chunk_metadata_header()\nSupprime les lignes # Projet: # Chunk:"]
        P2 --> P3["is_real_transcript_content()\nGarde: ne pas envoyer vide à l'IA"]
        P3 -->|"Vide"| P4["Status → skipped_empty"]
        P3 -->|"OK"| P5["build_prompt()\nprompt_manager.build_prompt()"]
        P5 --> P6{"depot/<projet>/prompt.md\nexiste ?"}
        P6 -->|Oui| P7["Prompt personnalisé\nplaceholder {{TEXT}}"]
        P6 -->|Non| P8["Template AI_TASK\nclean_transcript (défaut)"]
        P7 & P8 --> P9["render_prompt()\nSubstitution sécurisée {{TEXT}}"]
        P9 --> P10["engine.send_prompt(prompt)"]
        P10 --> P11{"Moteur ?"}
        P11 -->|Ollama| P12["POST /api/generate\nqwen3:8b\ntimeout 1200s"]
        P11 -->|LMStudio| P13["POST /v1/chat/completions\nOpenAI-compatible"]
        P11 -->|OpenAI| P14["openai.ChatCompletions\ngpt-4o-mini"]
        P11 -->|Fake| P15["Réponse simulée\n(tests)"]
        P12 & P13 & P14 & P15 --> P16["processed/chunk_NNN.md\nMarkdown éditorial"]
        P16 --> P17["chunk status → done\nsave_project_state()"]
        P10 -->|Erreur| P18["errors/chunk_NNN.error.txt\nTraceback + extrait prompt\nchunk status → failed"]
    end
```

---

## Pipeline de révision humaine (détail)

```mermaid
flowchart TD
    subgraph AUTO["Automatique — correction_review_service"]
        direction TB
        R1["Pour chaque chunk status=done"]
        R1 --> R2["Parse chunks/chunk_NNN.txt\n_parse_segments()\nExtrait [HH:MM -> HH:MM] texte"]
        R2 --> R3["Génère corrections/chunk_NNN.corrections.md\nFormat:\n## Correction N\n### Timestamp: HH:MM → HH:MM\n### Texte actuel: ...\n### Texte corrigé: [À COMPLÉTER]"]
        R3 -->|"Si déjà présent"| R4["SKIP — ne jamais écraser"]
    end

    subgraph HUMAN["Manuel — hors pipeline"]
        direction TB
        H1["L'éditeur ouvre\ncorrections/chunk_NNN.corrections.md"]
        H1 --> H2["Remplace [À COMPLÉTER]\npar le texte corrigé"]
        H2 --> H3["Peut corriger : 0 / quelques / tous\nles segments"]
    end

    subgraph APPLY["Automatique — correction_apply_service"]
        direction TB
        A1["apply_corrections()"]
        A1 --> A2["_parse_corrections()\n• Lit les blocs ## Correction N\n• Ignore les [À COMPLÉTER]\n• Retourne (corrections_valides, total_blocks)"]
        A2 --> A3{"Corrections\nvalides ?"}
        A3 -->|"0 valide"| A4["reviewed/ = copie de processed/\nstatus: no_corrections"]
        A3 -->|"N valides"| A5["_apply_corrections_to_content()\nreplacement première occurrence\npar ordre de correction"]
        A5 --> A6{"Erreur de\nremplacement ?"}
        A6 -->|"Texte actuel\nintrouvable"| A7["Erreur loguée\nstatus: partial_error"]
        A6 -->|"OK"| A8["reviewed/chunk_NNN.md\nstatus: applied"]
        A4 & A7 & A8 --> A9["save_project_state()"]
    end

    subgraph USAGE["Dans final_document_builder"]
        direction TB
        U1["list_effective_chunks()\nPour chaque chunk:\n1. reviewed/chunk_NNN.md si présent\n2. processed/chunk_NNN.md sinon"]
        U1 --> U2["Préservation des timestamps\ndans les métadonnées du chunk source"]
    end

    AUTO --> HUMAN
    HUMAN --> APPLY
    APPLY --> USAGE
```

---

## Pipeline de génération documentaire (détail)

```mermaid
flowchart TD
    subgraph INPUT["Sources"]
        A["final/document_clean.md\n(version sans artefacts)"]
        B["final/document_final.md\n(version avec structure)"]
        C["cover/cover.jpg"]
        D["project.yaml\n(métadonnées: titre, auteur, ISBN...)"]
    end

    subgraph TEMPLATE["Application du template"]
        E["publication_template_service\nbuild_publication_markdown()"]
        E --> F["publication/publication.md\nMarkdown formaté avec\nmétadonnées et structure finale"]
    end

    subgraph DOCX_PIPELINE["Pipeline DOCX"]
        G1["docx_export_service.export_docx()"]
        G2["publication_docx_engine\ngenerate_publication_docx()"]
        G1 -->|"python-docx"| G3["final/document_final.docx\nExport basique"]
        G2 -->|"python-docx\n+ template style"| G4["publication/publication.docx\nExport éditorial"]
    end

    subgraph PDF_PIPELINE["Pipeline PDF"]
        H1["pdf_export_service.export_pdf()"]
        H2["publication_pdf_engine\ngenerate_publication_pdf()"]
        H1 --> H3["final/document_publication.pdf"]
        H2 --> H4["publication/publication.pdf\nAvec couverture intégrée"]
    end

    subgraph ZIP_PIPELINE["Package client ZIP"]
        Z1["client_export_service\nexport_client_zip()"]
        Z1 --> Z2["Collecte les livrables:\n• publication.pdf\n• publication.docx\n• cover.jpg"]
        Z2 --> Z3["client/<projet>_CLIENT.zip"]
    end

    subgraph QUALITY["Validation qualité"]
        Q1["publication_quality_service\nvalidate_and_update_state()"]
        Q1 --> Q2{"Statut ?"}
        Q2 -->|"passed"| Q3["✅ Pipeline success"]
        Q2 -->|"warning"| Q4["⚠️ Avertissement logué\nStatut inchangé"]
        Q2 -->|"failed"| Q5["❌ Pipeline → partial"]
    end

    A & B & D --> TEMPLATE
    TEMPLATE --> DOCX_PIPELINE
    TEMPLATE --> PDF_PIPELINE
    C --> PDF_PIPELINE
    G3 & G4 & H3 & H4 --> ZIP_PIPELINE
    C --> ZIP_PIPELINE
    G4 & H4 --> QUALITY
```

---

## Publication Orchestrator — sous-pipeline dédié

```mermaid
flowchart TD
    A["generate_complete_client_package()"]
    A --> B["Étapes séquentielles\navec _CRITICAL_STEPS"]

    B --> S1["1. editorial_transformer\neditorial_transformer.transform_editorial_manuscript()"]
    S1 --> S2["2. quality_guard\neditorial_quality_guard.run_editorial_quality_guard()"]
    S2 --> S3["3. publication_builder ⭐ CRITIQUE\npublication_builder.build_publication()"]
    S3 --> S4["4. publication_sanitizer\npublication_sanitizer.generate_sanitized_publication()"]
    S4 --> S5["5. cover_builder\ncover_builder.generate_cover()"]
    S5 --> S6["6. docx_engine\npublication_docx_engine.generate_publication_docx()"]
    S6 --> S7["7. pdf_engine ⭐ CRITIQUE\npublication_pdf_engine.generate_publication_pdf()"]
    S7 --> S8["8. client_package\nclient_package.build_client_package()"]

    S8 --> R["Rapport\nsorte/<projet>/orchestrator_report.md"]

    S1 -->|"ERREUR étape critique"| ABORT["Pipeline arrêté\nÉtapes suivantes → skipped"]

    style S3 fill:#5c1a1a,stroke:#dd4a4a,color:#eee
    style S7 fill:#5c1a1a,stroke:#dd4a4a,color:#eee
```

**Étapes critiques :** `editorial_transformer`, `publication_builder`, `pdf_engine`  
Si l'une d'elles échoue, le pipeline est arrêté immédiatement.
