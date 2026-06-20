# TranscriptionAI

Pipeline Python de transcription audio et de production documentaire.

Transforme des enregistrements audio en documents structurés (Markdown, DOCX, PDF) via Faster-Whisper et un modèle IA local (Ollama).

---

## Fonctionnalités

- Transcription automatique `.ogg`, `.mp3`, `.wav`, `.m4a`
- Correction et restructuration du texte via IA locale (Ollama)
- Export DOCX et PDF prêts à l'impression
- Interface Streamlit locale avec suivi en temps réel
- Reprise automatique après interruption
- Gestion multi-projets
- Logs JSONL et rapports JSON par projet

---

## Installation Windows

### Prérequis

1. **Installer Python 3.11**
   Téléchargez depuis [python.org](https://www.python.org/downloads/)
   Cochez **"Add Python to PATH"** lors de l'installation.

2. **Installer Ollama**
   Téléchargez depuis [ollama.com](https://ollama.com/download)
   Lancez Ollama après installation.

3. **Télécharger le modèle IA recommandé**

   ```
   ollama pull qwen3:8b
   ```

4. **Lancer l'installation**

   Double-cliquez sur `install_windows.bat` ou exécutez dans un terminal :

   ```
   install_windows.bat
   ```

   Ce script crée un environnement virtuel `.venv` et installe toutes les dépendances.

5. **Vérifier le système**

   ```
   check_system.bat
   ```

6. **Démarrer l'interface**

   ```
   start_ui.bat
   ```

---

## Utilisation

### Déposer les fichiers audio

Créez un dossier par projet dans `depot/` :

```
depot/nom_du_projet/
```

Exemple :

```
depot/demo_conference/audio1.m4a
depot/demo_conference/audio2.m4a
```

Le nom du dossier devient le nom du projet.

### Lancer le traitement

- **Interface Streamlit** : double-cliquez sur `start_ui.bat`, ouvrez http://localhost:8501, cliquez sur **Traiter le projet**.
- **Console** : lancez `start_console.bat`, choisissez le projet dans le menu.

### Récupérer les fichiers générés

Les fichiers finaux se trouvent dans :

```
sortie/nom_du_projet/final/
```

---

## Fichiers générés

| Fichier | Description |
|---|---|
| `document_final.md` | Transcription corrigée et structurée (Markdown) |
| `document_final.docx` | Document Word mis en forme |
| `document_final.pdf` | PDF prêt à l'impression |
| `document_publication.md` | Version publication (ton éditorial) |
| `document_publication.docx` | Version publication Word |
| `document_publication.pdf` | Version publication PDF |
| `report.json` | Rapport d'exécution du pipeline |

---

## Configuration IA

Le fichier de configuration se trouve dans `app/config.py`.

### Changer de moteur IA

```python
# app/config.py

AI_PROVIDER = "ollama"    # moteur principal (recommandé)
OLLAMA_MODEL = "qwen3:8b"
```

**Options disponibles :**

| Valeur | Description |
|---|---|
| `"ollama"` | Ollama local — moteur principal recommandé |
| `"lmstudio"` | LM Studio (API compatible OpenAI) |
| `"openai"` | API OpenAI cloud (nécessite une clé API) |
| `"fake"` | Simulation locale pour les tests |

### Changer de modèle Ollama

```python
OLLAMA_MODEL = "qwen3:8b"      # recommandé (16 Go RAM)
OLLAMA_MODEL = "llama3.1:8b"   # alternatif stable
OLLAMA_MODEL = "mistral:7b"    # plus léger
```

Télécharger un modèle :

```
ollama pull llama3.1:8b
```

---

## Scripts disponibles

| Script | Rôle |
|---|---|
| `install_windows.bat` | Installation complète (venv + dépendances + dossiers) |
| `start_ui.bat` | Lancer l'interface Streamlit |
| `start_console.bat` | Lancer le menu console |
| `check_system.bat` | Vérifier la configuration du système |

---

## Problèmes fréquents

**Ollama n'est pas lancé**
Démarrez Ollama (icône dans la barre des tâches), puis relancez `check_system.bat`.

**Modèle absent**
```
ollama pull qwen3:8b
```

**Streamlit ne se lance pas**
Relancez `install_windows.bat` pour réinstaller les dépendances.

**Le traitement est lent**
Utilisez un modèle plus léger :
```python
# app/config.py
OLLAMA_MODEL = "llama3.1:8b"
# ou
OLLAMA_MODEL = "mistral:7b"
```

**Erreur "Python introuvable"**
Réinstallez Python 3.11 en cochant **"Add Python to PATH"**.

---

## Structure du projet

```
TranscriptionAI/
├── main.py                  # Point d'entrée console
├── streamlit_app.py         # Interface Streamlit
├── app/                     # Modules du pipeline
│   ├── config.py            # Configuration principale
│   ├── pipeline_runner.py
│   ├── transcription_service.py
│   ├── ai_engine.py
│   └── ...
├── book/                    # Modules de production livre
├── depot/                   # Projets audio à traiter
├── sortie/                  # Résultats générés
├── logs/                    # Journaux d'exécution
├── temp/                    # Fichiers temporaires
├── rejets/                  # Fichiers rejetés
└── archives/                # Archives de projets terminés
```

---

## Version

Voir le fichier `VERSION`.
