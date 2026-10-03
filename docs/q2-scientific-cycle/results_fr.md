# Résultats scientifiques Q2 — artefacts distincts de RC2.2

Les résultats ci-dessous sont de **nouveaux fits**, pas des rejeux des métriques historiques. Les périodes/cohortes déjà consultées restent exploratoires. Les comparateurs sont réglés sur validation2023, jamais sur les tests. Aucun nouvel IC/bootstrap ni garantie de quartile/acceptation.

## CMS nursing — comparaison complète
L’inventaire CMS contient171 fichiers, dont32 checkpoints ajustés. Le paquet distinct `HealthGraphBench_Q2_CMS_20261003.tar.gz` conserve toutes les grilles, préparations dérivées, prédictions et ressources;4 569 115B, SHA256 `a11d34e9946c6c03b4b092a423d421094b808db8067ab30777eb2f6b1751cb80`. Aucun fichier brut n’y est ajouté. Filiation: `results/q2_cms_artifacts_20261003.json`, `results/q2_cms_archive_20261003.json`, `results/SHA256SUMS_q2_cms_20261003`.


Preuve: `results/q2_cms_comparison_20261003.json`; run `cms-comparison-002`, code `3e7d548800cbbfd317d9cd74497dcc132707b904`. Les sept raw ont leurs empreintes figées vérifiées;23 712 lignes préparées,24 fits de validation et8 refits test. Le test poolé couvre18 985 inspections, dont2 423 positives, en2024–25.

| Features / famille | Configuration choisie sur validation | AUC validation2023 | AUC2024 | AUC2025 | AUC poolée2024–25 |
|---|---|---:|---:|---:|---:|
| Facility history / logistique | C.01, index0 | .653494 | .621082 | .626874 | .619416 |
| Facility + ownership / logistique | C.01, index0 | .655366 | .621832 | .626598 | .619574 |
| Facility history / HGB | LR.05,100 itérations,15 feuilles,L2=1, index5 | .580839 | .608396 | .630043 | .617756 |
| Facility + ownership / HGB | même configuration, index5 | .585064 | .610319 | .628614 | .618872 |

Tous ces fits sont déterministes au niveau de la politique publiée: training exact≤200 000 lignes, une exécution par configuration/refit, aucun pseudo-seed. L’augmentation ownership n’est pas uniformément positive annuellement; aucune significativité ni effet causal n’est déduit des écarts. La prévalence a AUC=.5 à chaque année; son AUC poolée=.472568 n’est pas nécessairement.5, car son intercept appris est différent entre années.

Ressources mesurées du run complet:33 phases, somme des durées supervisées31.813s, somme CPU worker rapportée43.867s, maximum RSS agrégée881 541 120B. Les runs MAUDE, Part D et de réutilisation ont été lancés dans la même fenêtre; ces coûts ne sont pas des chronométrages sur machine dédiée et ne constituent pas des budgets de calcul identiques. Plafonds inchangés du protocole; aucune phase incomplète n’a servi à choisir une configuration.

### Erreur conservée

`cms-comparison-001` s’est arrêté après les six fits logistiques facility-history de validation: `max_features=1` JSON entier refusé par scikit-learn avant le premier fit HGB. Ce run est conservé, sans sélection. Conversion en float dans le seul adapter CMS, mêmes valeurs/grilles/seeds/plafonds, smoke et régression publiés **avant** le nouveau run complet. Preuves: `results/q2_cms_first_run_failure_20261003.json` et `results/q2_cms_compatibility_preflight_20261003.json`. Les autres runs gardent leur propre snapshot de sources; la correction CMS n’est pas rétrospectivement attribuée à leur code.

## Limites de preuve

Le prévol4000→2000 providers, Recall@10=.5/Recall@20=1, est **synthétique et logiciel**; il ne s’ajoute pas à ce tableau médical. Son transport CMS simulé ne prouve pas une source officielle publique. L’évaluation réellement indépendante requiert la source cible future et les conditions/attestations de non-consultation; l’étude d’utilisateur extérieur humain requiert un participant réel. Un forecast scellé ou une exécution d’assistant ne satisfait pas ces gates.
