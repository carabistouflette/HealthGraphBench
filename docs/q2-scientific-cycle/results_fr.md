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
## Réutilisation Part D — preuve technique réalisée

`results/q2_external_reuse_20261003.json` conserve le witness `external-reuse-001`: les sixCSV bruts vérifiés, une préparation fraîche, deux fits cosine aux cutoffs2023/2024, les vrais fits du logistique SDK demandé, de nouveaux scores et une évaluation recalculée par `PartDTask.evaluate`. Le driver hors repo importe les40 fichiers de package vérifiés depuis `site-packages`, sous Python isolé `-I`, sans editable/PYTHONPATH ni patch de whitelist. Les checkpoints cosine sont rechargés et l’identité des scores est vérifiée.

| Modèle du witness | Recall micro@10 validation2023 | Recall micro@10 test2024 |
|---|---:|---:|
| Cosine top50 hors paquet, non supervisé, sans tuning | .260960 | .258583 |
| Logistique SDK public, algorithme historique18 époques | .178460 | .168188 |

Chaque target a2000 providers;2024 compte5476 relations positives réparties sur1019 providers et981 providers sans positif. Le logistique SDK n’est **pas** le comparator LBFGS choisi par la nouvelle grille Q2. Ces métriques de witness sont exploratoires; le but ici est la réutilisation observable, pas une comparaison réglée supplémentaire ou une validation humaine.

Phase raw→fits→évaluation:1362.134s supervisées,1340.519s CPU rapportées,595 460 096B de RSS agrégée maximale. Le PID après `execve` est bien celui supervisé. Le wheel vient du clone propre `f8ea41c4d8f090560fbdbc698db2300821b9cfef`, SHA256 `b5c776556ef64686804c4dec6e354127c59c3db441710519da793ffee6117428`; versionSDK0.2.0 de développement, pas nouvelle publication du benchmarkDOI.

Paquet `HealthGraphBench_Q2_Reuse_20261003.tar.gz`:13 086 403B, SHA256 `b0b2cddc54be88120dc6933f544cfa5d4be3811b77d1b65bb15a5e403c66315a`. Wheel, logs, provenance, préparations dérivées, checkpoints et prédictions conservés, sans lesCSV raw. L’étude d’un participant humain extérieur demeure **pending**; cette exécution est assistant-authored.

Inventaire complet du witness et de son wheel:31 fichiers, dont deux checkpoints cosine,111 700 682B; `results/q2_external_reuse_artifacts_20261003.json` et `results/SHA256SUMS_q2_external_reuse_20261003`. Les données d’origine2019–24 ne figurent pas dans ce ledger de sortie ni dans l’archive.


## MAUDE — validation complète et reprise conservée

`results/q2_maude_validation_20261003.json` conserve les84 fits de validation, trente époques de pertes lorsqu’applicables, sensibilités par seed et critères d’admissibilité. Les six configurations sont achevées pour chaque famille. Aucun seed n’est sélectionné.

| Famille | Configuration choisie | Recall micro@10 validation2023, moyenne requise |
|---|---|---:|
| Logistique | C.01 | .186762 |
| HGB | configuration01 | .185853 |
| Spectral | configuration06 | .176163 |
| BPR | configuration06 | .227169 |
| GraphSAGE `mean` | configuration01 | .190785 |
| GraphSAGE `none` | configuration04 | .149167 |

Les six configurations `mean` passent les trois gates de validation; `none01` n’est pas admissible, les cinq autres le sont. Le contrôle `none04` est réellement apprenant sur validation, sans voisin; cela ne prouve ni généralisation ni effet causal à capacité égale. Le premier run s’est arrêté sur sérialisation avant les fits test, et reste incomplet conservé. Les nouveaux refits doivent passer à nouveau leurs gates avant toute interprétation de leurs métriques.

### MAUDE — refits et scoring test achevés

`maude-comparison-002` est `COMPLETE`:28 refits test et deux phases heuristiques, sans réentraînement des84 fits de validation. Les douze refits GraphSAGE sélectionnés passent les gates avant scoring; leur plus petite baisse relative de probe est49.689%, largement au-dessus du seuil fixé1%. Les états/checkpoints et les30 époques de pertes sont conservés, sans remplacer les diagnostics historiques C/D1.

| Famille, configuration choisie sur2023 | Recall micro@10 test2024 | Recall micro@10 test2025 |
|---|---:|---:|
| Popularité globale, sans tuning | .182242 | .186306 |
| Fréquence des voisins, sans tuning | .189239 | .194394 |
| Logistique C.01 | .189738 | .187003 |
| HGB100/7/L2=0 | .188739 | .185051 |
| Spectral rang16/power24 | .188350 | .181286 |
| BPR d16/L2=0 | .230551 | .239437 |
| GraphSAGE `mean` d8/L2=.0005 | .204065 | .211825 |
| GraphSAGE `none` d16/L2=.0005 | .193403 | .165388 |

Les lignes latentes rapportent la moyenne des trois seeds103/211/307, jamais le meilleur seed. `none` varie de.179910 à.209229 en2024 et de.145447 à.177381 en2025; cette sensibilité est conservée, pas masquée par une répétition favorable. Dénominateurs:6003 relations positives en2024 et7171 en2025. HGB reste déterministe aux trois cutoffs96906/112316/124322 lignes. Les configurations/capacités séparées interdisent une interprétation causale d’agrégation.

Ressources des deux roots, phase échouée incluse:2158.507s supervisées cumulées,2181.950s CPU worker rapportées, RSS agrégée maximale1 399 336 960B. Les autres processus/captures ont partagé la machine; pas de chronométrage dédié ni de coût égal revendiqué. Inventaire612 fichiers/112 checkpoints/614 538 068B. Archive distincte `HealthGraphBench_Q2_MAUDE_20261003.tar.gz`:141 798 509B, SHA256 `dbce2d88f335b0b718d2decc750dae2638f6de877e8542fb93857a6691a0d637`, sans ZIP raw. Preuves: `results/q2_maude_comparison_20261003.json`, `results/q2_maude_artifacts_20261003.json`, `results/q2_maude_archive_20261003.json`, `results/SHA256SUMS_q2_maude_20261003`.

## Part D — comparaison réglée complète

`partd-comparison-001` est `complete`,54/54 phases terminées:42 fits de validation et sept refits test, plus préparation et heuristiques. Toutes les familles réglées ont six configurations; la sélection utilise toute la moyenne requise sur validation2023, puis seulement le test2024. BPR et HGB utilisent les trois seeds103/211/307; la logistique est déterministe. Aucun seed n’est choisi.

| Famille | Configuration choisie | Recall micro@10 validation2023 | Recall micro@10 test2024 |
|---|---|---:|---:|
| Popularité par spécialité | Sans tuning | .2202 | .2179 |
| Recouvrement historique | Sans tuning | .2220 | .2104 |
| Logistique | C.1, balanced | .1947 | .1844 |
| HGB | LR.1/100/15/L2=0 | .1950 | .1971 |
| BPR | d32/LR.03/L2=.001/5 négatifs | .2355 | .2362 |

BPR test varie de.231738 à.242148 entre seeds; HGB de.1958 à.1980. Les deux cutoffs HGB comportent337 702 et349 460 lignes, donc dépassent le seuil200 000 et justifient les trois répétitions. BPR baisse sa perte pairwise échantillonnée d’environ.7020–.7026 à.0264–.0265, sur30 époques, avec états/checkpoints conservés. Cette baisse ne prouve pas une généralisation indépendante.

Dénominateurs:2000 providers par target,5794 positifs en validation et5476 au test;965 puis981 providers sans positif inclus dans la charge de recommandation. Tous les1 955 528/2 023 800 candidats sont scorés, sans échantillonnage d’évaluation. Part D2023/2024 ont déjà été consultées et restent exploratoires; aucune cible officielle2025 ne fait partie de cette comparaison.

Wall observée2013.026s, CPU worker cumulée1999.932s, RSS agrégée maximale850 653 184B. Six opportunités de sélection par famille, mais validation logistique86.3s/BPR200.3s/HGB389.9s: coûts différents, machine partagée. Le snapshot consommé est `abf13e3bbb279909c4633fd0dd7ed95231980129`, sans attribution rétroactive des corrections CMS/MAUDE.

L’archive conserve les324 fichiers du run, **y compris `edges.csv` de préparation dérivée**, et49 checkpoints, sans les sixCSV sources CMS. `HealthGraphBench_Q2_PartD_20261003.tar.gz`:630 693 314B, SHA256 `abaf9d40356dc6a8dc02cdddc5fa70328f9e18d082f7f2fabc0989328de3fca4`. Preuves: `results/q2_partd_comparison_20261003.json`, `results/q2_partd_artifacts_20261003.json`, `results/q2_partd_archive_20261003.json`, `results/SHA256SUMS_q2_partd_20261003`.

## Limites de preuve

Le prévol4000→2000 providers, Recall@10=.5/Recall@20=1, est **synthétique et logiciel**; il ne s’ajoute pas à ce tableau médical. Son transport CMS simulé ne prouve pas une source officielle publique. L’évaluation réellement indépendante requiert la source cible future et les conditions/attestations de non-consultation; l’étude d’utilisateur extérieur humain requiert un participant réel. Un forecast scellé ou une exécution d’assistant ne satisfait pas ces gates.
