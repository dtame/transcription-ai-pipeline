# TranscriptionAI — Installation Windows détaillée

Ce guide décrit l'installation complète de TranscriptionAI sur un PC Windows à partir de zéro.

---

## Prérequis système

| Composant | Version minimale | Recommandé |
|---|---|---|
| Windows | 10 (64 bits) | Windows 11 |
| Python | 3.10 | 3.11 |
| RAM | 8 Go | 16 Go |
| Espace disque | 10 Go libres | 20 Go libres |
| Ollama | dernière version | dernière version |

---

## Étape 1 — Installer Python 3.11

1. Ouvrez [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Téléchargez **Python 3.11.x** (version Windows 64 bits)
3. Lancez l'installateur
4. **Important** : cochez **"Add Python to PATH"** en bas de la première fenêtre
5. Cliquez sur **Install Now**
6. Vérification dans un terminal PowerShell :
   ```
   python --version
   ```
   Résultat attendu : `Python 3.11.x`

---

## Étape 2 — Installer Ollama

Ollama est le moteur IA local qui fait tourner les modèles de langage.

1. Ouvrez [https://ollama.com/download](https://ollama.com/download)
2. Téléchargez **OllamaSetup.exe** (Windows)
3. Lancez l'installateur
4. Ollama démarrera automatiquement et apparaîtra dans la barre des tâches (icône de lama)

Vérification dans un terminal :
```
ollama list
```

---

## Étape 3 — Télécharger un modèle IA

Ouvrez un terminal PowerShell ou Invite de commandes et tapez :

```
ollama pull qwen3:8b
```

Le téléchargement peut prendre 5 à 15 minutes selon votre connexion.

**Modèles alternatifs :**

| Modèle | RAM requise | Usage |
|---|---|---|
| `qwen3:8b` | 8-10 Go | Recommandé — bon équilibre qualité/vitesse |
| `llama3.1:8b` | 8-10 Go | Alternatif stable |
| `mistral:7b` | 6-8 Go | Plus léger, plus rapide |
| `gemma3:12b` | 12-14 Go | Qualité supérieure, RAM importante |

---

## Étape 4 — Copier le projet

Copiez le dossier `TranscriptionAI/` sur votre PC (via clé USB, réseau, GitHub, etc.).

Structure minimale attendue :
```
TranscriptionAI/
├── main.py
├── streamlit_app.py
├── requirements.txt
├── install_windows.bat
├── start_ui.bat
├── start_console.bat
├── check_system.bat
├── check_system.py
└── app/
    ├── config.py
    └── ...
```

---

## Étape 5 — Lancer l'installation

Dans l'explorateur Windows, double-cliquez sur :

```
install_windows.bat
```

Ce script effectue automatiquement :
1. Vérification de Python
2. Création de l'environnement virtuel `.venv`
3. Mise à jour de pip
4. Installation de toutes les dépendances Python
5. Création des dossiers de travail (`depot/`, `sortie/`, `logs/`, `temp/`, `rejets/`, `archives/`)

L'installation prend généralement 3 à 10 minutes.

---

## Étape 6 — Vérifier la configuration

Double-cliquez sur :

```
check_system.bat
```

Le script vérifie :
- Version Python
- Présence des fichiers principaux
- Existence des dossiers de travail
- Droits d'écriture
- Espace disque disponible
- Connexion à Ollama
- Présence du modèle configuré

**Résultat attendu :** aucune ligne `[FAIL]`, avertissements `[WARN]` optionnels.

---

## Étape 7 — Démarrer l'interface

Double-cliquez sur :

```
start_ui.bat
```

Un terminal s'ouvre. Après quelques secondes, votre navigateur par défaut s'ouvre sur :

```
http://localhost:8501
```

Si le navigateur ne s'ouvre pas automatiquement, tapez cette adresse manuellement.

---

## Déposer des fichiers audio

Créez un sous-dossier par projet dans `depot/` :

```
depot/
└── mon_projet/
    ├── audio1.m4a
    ├── audio2.mp3
    └── audio3.wav
```

Formats supportés : `.ogg`, `.mp3`, `.wav`, `.m4a`

Dans l'interface Streamlit, sélectionnez le projet et cliquez sur **Traiter**.

---

## Récupérer les résultats

Les fichiers générés se trouvent dans :

```
sortie/mon_projet/final/
├── document_final.md
├── document_final.docx
├── document_final.pdf
├── document_publication.md
├── document_publication.docx
└── document_publication.pdf
```

---

## Configuration avancée

Ouvrez `app/config.py` dans un éditeur texte pour modifier :

```python
AI_PROVIDER = "ollama"       # moteur IA
OLLAMA_MODEL = "qwen3:8b"    # modèle à utiliser
```

Après modification, relancez `start_ui.bat` pour appliquer les changements.

---

## Désinstallation

Pour désinstaller proprement :

1. Supprimez le dossier `.venv/` (contient toutes les dépendances Python)
2. Optionnel : supprimez les dossiers `sortie/`, `logs/`, `temp/`, `rejets/`, `archives/`
3. Optionnel : désinstallez Python et Ollama via **Ajout/Suppression de programmes**

---

## Problèmes courants

### "Python n'est pas reconnu comme commande"

Python n'est pas dans le PATH. Solutions :
- Réinstaller Python en cochant **"Add Python to PATH"**
- Ou ajouter manuellement `C:\Users\<nom>\AppData\Local\Programs\Python\Python311\` au PATH système

### Ollama non accessible au démarrage

Ollama doit être lancé avant d'utiliser TranscriptionAI.
- Vérifiez la barre des tâches (icône de lama)
- Ou lancez manuellement : recherchez **Ollama** dans le menu Démarrer

### Erreur lors de l'installation des dépendances

Causes fréquentes :
- Connexion internet instable → relancez `install_windows.bat`
- Antivirus bloquant pip → ajoutez une exception pour le dossier du projet
- Droits insuffisants → faites un clic droit sur `install_windows.bat` → **Exécuter en tant qu'administrateur**

### Streamlit se ferme immédiatement

Vérifiez que `.venv` est correctement installé. Relancez `install_windows.bat`.

### Transcription très lente

- Vérifiez que vous avez assez de RAM disponible (fermez les applications inutiles)
- Utilisez un modèle plus léger dans `app/config.py` :
  ```python
  OLLAMA_MODEL = "mistral:7b"
  ```

---

## Support

En cas de problème persistant, vérifiez :
1. `check_system.bat` — pour diagnostiquer l'environnement
2. `logs/transcription_log.jsonl` — pour les erreurs détaillées
3. `sortie/<projet>/report.json` — pour le rapport du dernier traitement
