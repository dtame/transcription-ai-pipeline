# PHASE 4B.2.34.4 — FIRST REAL COVER IMAGE

RESULT = OUTCOME_UNKNOWN
REAL PROVIDER CALLS = 0
PROVIDER = OpenAI
MODEL = gpt-image-2
ART DIRECTION = The Door Already Open
POLICY = EXPERIMENTAL_AUTHORIZED
USER AUTHORIZATION = VERIFIED
AUTHORIZATION USE = CONSUMED
IMAGE COUNT REQUESTED = 1
IMAGE COUNT RECEIVED = None
RESOLUTION REQUESTED = 1024 × 1536
RESOLUTION RECEIVED = None
QUALITY = medium
FORMAT = PNG
IMAGE SHA256 = None
IMAGE PATH = None
ESTIMATED COST = unknown; published image-output cell 0.041 USD is not a total
OBSERVED COST = None
COST RECONCILIATION = COST_RECONCILIATION_PENDING
AUTOMATIC RETRIES = 0
FALLBACK CALLS = 0
SECOND PAID CALL = NO
TECHNICAL IMAGE VALIDATION = NOT_RUN
HUMAN VISUAL REVIEW = NOT_APPLICABLE
FRONT COVER GENERATED = NO
BACK COVER GENERATED = NO
COVER DOCX GENERATED = NO
COVER PDF GENERATED = NO
CANONICAL HASHES = MATCH
NEXT STEP = STOP

## Déroulement

L'autorisation a été réservée et marquée soumise, puis le transport a levé `NetworkSealed` avant `urlopen`. Aucun socket n'a été ouvert. Aucune requête HTTP n'a été transmise à OpenAI. Il n'y a pas de statut HTTP et pas d'identifiant de requête fournisseur. L'architecture classe ce `NetworkSealed`, survenu après l'intention de soumission, comme `OUTCOME_UNKNOWN`. L'autorisation `063a16a7ea284329b944339265d26e8c` est consommée. Un second essai local a été refusé sans réseau. Aucun nouvel appel payant n'a été fait.

La cause locale est un drapeau lu trop tôt : le transport avait copié `LIVE_HTTP_ENABLED = False` à l'import, alors que le processus ne levait le drapeau du module qu'au moment de l'appel. Cette lecture est corrigée pour une autorisation future. Cette correction n'a pas été suivie d'un appel.

## Soumission

- Intention de soumission enregistrée : True
- Requête HTTP transmise : NON
- Socket ouvert : False
- Statut HTTP : aucun, la connexion n'a pas été ouverte
- Provider request ID : None
- Statut d'autorisation : OUTCOME_UNKNOWN
- Identifiant d'autorisation : 063a16a7ea284329b944339265d26e8c
- Facturation connue : False
- Type d'exception : NetworkSealed
- Statut d'exception : None

## Coût

Aucune requête n'a quitté la machine, donc cette tentative n'a pas atteint la facturation d'OpenAI. `observed_cost_usd` reste null : aucun montant, y compris zéro, n'est inventé. 0.041 USD est seulement la cellule publiée de sortie image pour 1024 × 1536 en qualité medium. Ce n'est pas une facture et ce n'est pas un plafond garanti par OpenAI. 0.10 USD est le budget de planification de Transcriptor-ia.

- estimated_cost_usd = None
- observed_cost_usd = None
- verified_maximum_cost_usd = None
- documented_image_output_estimate_usd = 0.041

## Image

Aucun titre, sous-titre, nom d'auteur, dos, code-barres ou fichier de couverture n'a été produit. L'examen artistique reste humain.

Signal dimension : None

Arrêt après cette tentative. Aucun second appel payant n'a été effectué.
