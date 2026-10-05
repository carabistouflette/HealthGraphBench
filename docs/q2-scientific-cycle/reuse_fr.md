# Réutilisation raw → fits → scores → évaluation

## Migration API Part D

La nouvelle interface Part D ne charge plus des rankings de model-gate en guise de `fit_predict`. `PartDTask.from_model_gate` et `load_task(..., model_gate_dir=...)` ne sont plus des chemins actifs. Les runs historiques et le benchmarkv0.2.0 déposé restent conservés; ils ne sont pas réécrits ou réentraînés par cette migration. Le README utilisateur reste intentionnellement inchangé; ses exemples basés sur le replay sont historiques, pas les commandes de cette API.

```python
from pathlib import Path
from healthgraphbench import load_task
from healthgraphbench.models import TabularLogistic

task = load_task(
    "partd",
    Path("/home/arobin/healthgraphbench-data/partd-v0_2-lookback"),
    manifest_path=Path("data/manifests/partd_feasibility_v0_2_lookback.json"),
    preparation_dir=Path("results/generated/q2-cycle-20261003/sdk-raw-001"),
)
train, validation, test = (task.get_split(name) for name in ("train", "validation", "test"))
predictions = TabularLogistic().fit_predict(train, validation, test)
metrics = task.evaluate(predictions)
```

Le répertoire doit être nouveau. Les sixCSV sont vérifiés, les cohortes et edges préparés, puis le modèle demandé est réellement ajusté et ses scores/rangs évalués. Les métriques ne sont pas récupérées d’un `report.test` conservé. `PartDTask.from_prepared_input` accepte une préparation vérifiée; ce niveau est déclaré, pas présenté comme un nouveau parcours raw. Pour les nouvelles comparaisons scientifiques, une entrée préparée exige un protocole verrouillant explicitement `input_level="prepared"`; la campagne principale utilise raw.

`TabularLogistic` SDK conserve son algorithme historique public: ce n’est pas automatiquement le gagnant LBFGS/C de la nouvelle grille. Les résultats de ce witness2023/24 sont exploratoires et servent à prouver le parcours logiciel, pas à ajouter une nouvelle comparaison réglée.

## Ajouter un modèle sans whitelist du paquet

`task.history_view(split)` expose uniquement le passé strict: `target_year`, `prior_years`, `provider_drugs`, `drug_providers`, `latest_specialties`, `candidate_ids(npi)`, support global et règle de tie. Mappings et ensembles sont immuables; la vue n’expose pas les labels du target. Un scorer reçoit `(view, npi, candidate_ids)` et doit retourner un score fini pour **chaque** candidat, sans modifier la liste. Le nom passé à `task.predict_ranker` ne nécessite pas une entrée dans la liste des modèles builtin.

Le fichier **hors paquet** `examples/q2_external_reuse/neighbor_cosine.py` implémente `NeighborCosineTop50.fit(view)` et le parcours `fit_predict(train, validation, test, checkpoint_dir=...)`. Il n’utilise pas les internals du Task pour son modèle. Son fit est une incidence binaire provider×generic_drug, normalisée pour la similarité cosine; cinquante voisins au maximum, soi exclu, ties parNPI. Les scores somment les similarités des voisins ayant le drug. Aucune sélection de paramètre ou seed; les fits de validation et test ont leurs propres cutoffs. C’est un fit non supervisé dérivé des données, pas une optimisation dont une perte pourrait être inventée.

Les checkpointsNPZ retiennent ids, incidence et indices/poids des voisins. Le driver les recharge et vérifie l’identité des scores. Il exporte nouvelle préparation, prédictions et métriques recalculées via `task.evaluate`; il exécute aussi le véritable builtin logistique public. Le nouveau modèle n’est pas importé ou ajouté à une whitelist de `healthgraphbench`.

## Démonstration technique en wheel propre

Le coordinator `healthgraphbench.q2.reuse.run_demonstration` acquiert le verrou Git/protocole **dans le repo parent**, puis appelle un Python wheel séparé. Le wheel est construit depuis un clone du commit, pas depuis les quatre documents utilisateur dirty. La version de distribution0.2.0 seule n’identifie pas ce code des comparaisons renforcées: commit, SHA du wheel et SHA des sources le distinguent du package/DOI historiques. Ce wheel de développement n’est pas une nouvelle publication Zenodo.

Le driver est copié dans sa phase; `python -I` depuis cette phase n’utilise ni cwd de repo, ni `PYTHONPATH`, ni installation editable. Le prévol vérifie `site-packages` et l’identité de **tous les fichiers de package verrouillés** avant un fit. Manifest et contrat sont passés par chemins absolus; ils ne sont pas cherchés dans un contexte repo implicite. `execve` remplace le worker supervisé: RSS, timeout et fin du processus portent sur le Python effectif. Stdout, stderr, statut worker et traceback sont conservés. Le niveau de preuve reste technique, non humain.

Entrée:

```text
scripts/run_q2_reuse.py
  --source-root /home/arobin/healthgraphbench-data/partd-v0_2-lookback
  --protocol configs/q2_scientific_protocol_20261003.json
  --protocol-sha256 SHA256 exact du protocole committé
  --output-dir un nouveau répertoire de sortie
  --reuse-python Python de l’environnement wheel propre
```

Le SHA fourni est un argument réel calculé sur les bytes du protocole, pas un identifiant de résultats historiques. Un package/source modifié ou une phase incomplète n’est pas accepté comme un witness réussi.

## Parcours d’un participant humain extérieur

Une exécution par assistant/agent ne prouve pas la réutilisation par un utilisateur humain extérieur. La gate nécessite un participant réel ne faisant pas partie de cette exécution, sans intervention cachée dans ses étapes:

1. Conserver son identité/rôle, la version exacte reçue, son OS/Python et la date du début; obtenir les autorisations nécessaires sans inventer son affiliation.
2. Installer le wheel de source vérifiée dans son propre environnement et récupérer/valider les raw à partir des sources publiques; conserver URL, sizes et SHA.
3. Exécuter préparation → fit demandé → scores → évaluation avec les commandes documentées, en notant toute erreur, intervention, changement de paramètres ou code.
4. Ajouter son propre modèle via l’API publique ou modifier réellement le modèle hors paquet; documenter le delta, le cutoff, le traitement des candidats et les résultats produits sans patch de whitelist.
5. Fournir journaux, provenance et outputs qu’il a lui-même obtenus; distinguer réussite autonome, réussite avec assistance, échec et étapes non réalisées.

Aucun nom de participant, durée d’apprentissage humain, satisfaction, succès autonome ou validation externe n’est déduit de la démonstration automatique. Ces informations ne sont pas disponibles dans le repo et restent à recueillir. Auteurs, approbation, déclarations et soumission du manuscrit demeurent des gates séparées.
