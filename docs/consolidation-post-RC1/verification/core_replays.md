# Rejeux du noyau RC1 — preuve pour le lot B

## Résultat observé

Le **2 octobre 2026**, une seule invocation de `scripts/verify_rc1_replays.py`, avec l’environnement propre `analysis-env`, a terminé en **4,539 s**, code retour **0**, stderr de l’orchestrateur vide, sans erreur ni relance observée. Les **10 contrôles** de `replays/checks.json` sont passés : 2 rejeux bootstrap, 2 comparaisons CMS, 5 comparaisons octet par octet du bundle MAUDE B et 1 comparaison octet par octet de la synthèse de couverture.

Depuis la racine du run `results/generated/consolidation-post-RC1/core-verification-20261002/`, l’invocation portable équivalente est :

```sh
analysis-env/bin/python inputs/HealthGraphBench_RC1/scripts/verify_rc1_replays.py --output-dir replays
```

Répertoire courant effectif : `inputs/HealthGraphBench_RC1/`. Environnement : Python 3.13.5, NumPy 2.3.5, Matplotlib 3.10.8, scikit-learn 1.8.0, selon `requirements-review.txt` (SHA-256 `b118afc3e5fa1fc05de103ad3336d12a26095a2bccb632f7c847c7ffa3e27bc0`). Variables appliquées : `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `PYTHONDONTWRITEBYTECODE=1`.

Le suivi `/proc` du processus et de ses descendants, échantillonné toutes les 50 ms, a mesuré un pic RSS agrégé de **182 068 KiB (177,8 MiB)**; plus grand `VmHWM` de processus : **162 372 KiB**. CPU via `wait4` : **4,376125 s utilisateur + 0,117194 s système**. Limites : 900 s, 768 MiB RSS, 512 MiB de nouvelles sorties. Les 19 fichiers de `replays/` occupent **7 619 114 octets**. Le rapport machine-readable contient argv exact, horodatages, environnement, ressources, sorties stdout/stderr, checks et SHA-256 : `results/generated/consolidation-post-RC1/core-verification-20261002/replay_execution.json`. `replays/orchestrator.stdout.log` est identique à `checks.json`; `orchestrator.stderr.log` est vide. Les cinq logs de tâches sont conservés; le script RC1 concatène stdout puis stderr de chaque sous-processus dans son log, donc ces flux internes ne sont pas séparables après coup.

## Contrôles exécutés

- **MAUDE bootstrap R2** — 49 champs numériques, tolérance absolue `1e-12`, 1 000 resamples, seed `20260929`; 6 370 product-quarters positifs (2 026 clusters produit, 13 174 edges positifs). Rejeu de contributions compactes conservées, conditionnel aux prédictions gelées.
- **Part D bootstrap R2** — 91 champs, même tolérance/resamples/seed; cohorte générique 2024 éligible : 2 000 prescripteurs/observations, dont 1 019 observations positives (5 476 positifs).
- **CMS R4** — 284 champs numériques comparés séparément aux arbres conservés `cms_replayed.json` et `cms_ties_exact.json`; égalité exacte des arbres pour les deux comparaisons, en plus de la tolérance `1e-12`.
- **MAUDE B1/B2** — rejeu à partir des snapshots préparés conservés. Les cinq fichiers `prepared_snapshots.json.gz`, `descriptors.json`, `training_tabular.csv`, `training_graph.csv` et `coverage_quarterly.csv` correspondent octet pour octet aux fichiers de référence; leurs SHA-256 figurent dans `checks.json` et le manifeste.
- **Couverture MAUDE R6** — agrégation des comptes existants et vérification de 12 trimestres et 9 853 lignes de membership détaillées; `maude_coverage_periods.json` est identique octet pour octet à la référence.

Les nouveaux résultats sont dans `results/generated/consolidation-post-RC1/core-verification-20261002/replays/` : `maude_replayed.json`, `partd_replayed.json`, `cms_replayed.json`, `maude_B/` (bundle complet), `maude_coverage_periods.json`, `checks.json` et logs. Le fichier `replay_execution.json` donne les hashes des scripts, exigences, entrées/références et de chacun des nouveaux fichiers. Les sources et entrées RC1 utilisées ont été re-hashées après l’exécution : les SHA-256 pré/post sont identiques.

## Portée et limites à retenir

Ce sont des **analyses rejouées sur sorties compactes ou snapshots préparés conservés**, pas des confirmations indépendantes. Les rejoueurs bootstrap déclarent `original_input_not_rechecked_in_replay=true` : la provenance est vérifiée depuis les métadonnées compactes, pas en relisant les sorties originales complètes. Le rejeu MAUDE B ne refait pas la collecte brute; la provenance incluse décrit une collecte antérieure et non cette exécution. **Aucune donnée brute FDA/MAUDE ou CMS n’a été acquise/reconstruite; aucun modèle n’a été entraîné, aucune nouvelle prédiction calculée, aucun checkpoint ni état optimizer récupéré.** Les scripts RC1 eux-mêmes sont utilisés : il n’y a pas d’implémentation indépendante ni de validation humaine des auteurs. Les descripteurs B sont des reconstructions, pas des logs d’optimiseur. La provenance embarquée ne doit pas être présentée comme une preuve nouvellement produite.

## Sources RC1 portables

Archive canonique : `results/generated/manuscript-rc1/HealthGraphBench_FAIA_LaTeX_RC1.zip`, SHA-256 `2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be`. Les chemins ci-dessous sont des membres de cette archive (`archive.zip!/membre`), pas des chemins locaux permanents :

- `scripts/verify_rc1_replays.py`, `scripts/compact_replay.py`, `scripts/paired_revision_analysis.py`, `scripts/cms_ties_analysis.py`
- `scripts/audit_maude_B.py`, `scripts/summarize_maude_coverage.py`
- `data/real_R4/maude.json.gz`, `data/real_R4/partd.json.gz`, `data/real_R4/cms.json.gz`, `data/maude_neighbors_vs_global_R2.json`, `data/partd_bpr_vs_specialty_R2.json`
- `data/real_R4/cms_replayed.json`, `data/real_R4/cms_ties_exact.json`
- `data/real_R6/maude_B/{SHA256SUMS,prepared_snapshots.json.gz,descriptors.json,training_tabular.csv,training_graph.csv,coverage_quarterly.csv,provenance.json}` et `data/maude_coverage_periods_R6.json`

L’extraction locale utilisée est `results/generated/consolidation-post-RC1/core-verification-20261002/inputs/HealthGraphBench_RC1/` (lecture seule). Aucun contenu de la release, des données historiques ni des artefacts RC1 n’a été modifié. Aucun build, test, lint ou formatter n’a été lancé.
