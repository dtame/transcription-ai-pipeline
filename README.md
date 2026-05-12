# TranscriptionAI

Pipeline Python de transcription audio basé sur Faster-Whisper.

## Fonctionnalités

- Transcription automatique `.ogg`, `.mp3`, `.wav`, `.m4a`
- Détection automatique de langue
- Barre de progression temps réel
- Gestion des gros fichiers
- Découpage automatique
- Journalisation JSONL
- Reprise après erreur
- Prévention de mise en veille Windows
- Archivage automatique

## Utilisation

```powershell
py -3.11 transcribe.py