# MAUDE — comparaison exploratoire mean30 / none30 (D1)

**Exécution D1 complète :** cette unique comparaison de P2 met côte à côte le modèle MAUDE `mean` à 30 époques déjà ajusté dans C et réutilisé tel quel, et la nouvelle variante `none` à 30 époques : un fit de validation et deux réajustements annuels indépendants. Il ne s’agit ni de nouveaux fits `mean`, ni d’une grille de durées ou d’un tuning. D2, les graines supplémentaires, bootstrap et intervalles de confiance sont hors périmètre.

Le [manifeste compact de cette comparaison](../../../results/maude_aggregation_ablation_20261002T205122Z.json) conserve résultats, origines, empreintes et réserves. Les sorties physiques D1 sont dans [`results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/`](../../../results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/), notamment [`report.json`](../../../results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/report.json), [`run_manifest.json`](../../../results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/run_manifest.json) et [`selection_locked_before_test.json`](../../../results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/selection_locked_before_test.json). Ces gros exports/checkpoints locaux restent ignorés ; le clone public ne contient pas à lui seul toutes les données nécessaires au rejeu exhaustif.

## Provenance, verrouillage et rendu

- Le run D1 complet s’est déroulé de `2026-10-02T20:51:22.508511Z` à `2026-10-02T20:58:18.652080Z`. Le code publié avant cette phase santé est le commit `b14d878a78f559b65c70fc872a51a59af4c5ae85`.
- L’entrée préparée en lecture seule est [`prepared_snapshots.json.gz`](../../../results/generated/consolidation-post-RC1/core-verification-20261002/inputs/HealthGraphBench_RC1/data/real_R6/maude_B/prepared_snapshots.json.gz), SHA-256 `1cba7f84ff24131715c68a985d9302c96c7bab4a4b2a27d906559a41104fbd36` : 28 instantanés trimestriels de 2019Q1 à 2025Q4, limités à `quarter`, `product_reports` et `edges`. Les dates utilisées sont les `DATE_RECEIVED` préparées; elles ne prouvent pas la disponibilité publique historique des informations.
- Le choix commun de 30 époques provient de la sélection C et du protocole D1 figé, sans tuning D1. D1 a verrouillé cette durée à `2026-10-02T20:53:30.842192Z`, avant le début des tests D1; le verrou porte `test_scores_consulted=false`. Cette chronologie ne retire pas l’exposition antérieure aux périodes historiques déjà consultées.
- `mean30` est réutilisé depuis C, sans réentraînement dans D1. Sa référence compacte pinnée reste [`results/maude_duration_diagnostic_20261002T172405Z.json`](../../../results/maude_duration_diagnostic_20261002T172405Z.json), SHA-256 `0c8a610991e313d49a9fba03736d225897620cec86779989c8b243665942dff2`; les sorties correspondantes sont dans [`maude-duration-20261002T172405Z/`](../../../results/generated/consolidation-post-RC1/maude-duration-20261002T172405Z/). Le run C et ses fichiers datés ne sont pas modifiés ici.
- Le [protocole D1](../aggregation_protocol.md), SHA-256 `78d1408a96da81fceb85b1f3f91034592b3b96dd95fbe4d508906e121c1efaca`, reste figé ; sa copie exacte est `aggregation_protocol_executed.md` dans le run. Le code, le protocole et le [prévol](../../../results/maude_aggregation_preflight_20261002.json) ont été commités et poussés avant ces fits, sur la [PR #3 en brouillon](https://github.com/carabistouflette/HealthGraphBench/pull/3), dépendante de #2. La commande complète du lancement est capturée dans le manifeste brut et le manifeste compact ; la CLI est `scripts/run_maude_aggregation_ablation.py`.
- Le rendu reproductible lit les journaux `epochs.jsonl.gz`, les résumés et les manifestes physiques C/D1; il n’entraîne rien. Commande exécutée depuis la racine du dépôt :

  ```sh
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1 \
    results/generated/consolidation-post-RC1/core-verification-20261002/analysis-env/bin/python \
    results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/postprocessing/render_maude_aggregation.py
  ```

  Environnement observé : Python 3.13.5 et Matplotlib 3.10.8. Le script, sa commande, les entrées hachées et les empreintes des rendus sont consignés dans [`postprocessing/render_metadata.json`](../../../results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/postprocessing/render_metadata.json).
- La [figure PNG](maude_aggregation_20261002T205122Z.png) montre les pertes observées pour les trois fits de chaque variante et les rappels micro@10 côte à côte avec les différences signées `mean30 − none30`; le [SVG](maude_aggregation_20261002T205122Z.svg) conserve le texte. Les [180 enregistrements d’époque mesurés et lignes de résumé](../../../results/maude_aggregation_epochs_20261002T205122Z.csv) comprennent exactement 90 époques mean30 réutilisées et 90 époques none30 nouvellement entraînées. Aucun point ou perte d’époque zéro n’est ajouté.
  Détail du CSV : 230 lignes de données (231 lignes avec l’en-tête), 39 colonnes — 180 époques mesurées, 6 résumés de fit/coût, 40 lignes de métriques et 4 différences R@10 signées. SHA-256 CSV `05f579b9076ff976e43850223f51511fc27e6074231f16a5e7598b59b9948e7e`; SVG `130c63895661731a8ae2160bef8130de92c017dd474d430cd7be570d08a1615d`; PNG `034f04b645e5c4d5a8a6da35c04864177aaf5faf9a8865caefc298717a9a1230`. Le renderer a pour SHA-256 `17d3624c4a1e08cd50f0d3067b472a9569b4db938c48d6fbc301069eef8c2ed6`; les métadonnées de rendu hachées `1c1bebd1c7a469b467621d67c2917c5d59fb031ced261db04dafb82c8f353dee` détaillent les empreintes sources et de sortie.

## Protocole et population

Les fits sont à 30 époques et indépendants. La durée commune est celle fixée par C; D1 ne compare pas plusieurs durées. La configuration partagée consigne l’objectif BPR, dimension 8, `tanh`, taux d’apprentissage 0,02 et régularisation 0,0005. `mean` applique l’agrégation GraphSAGE à un saut avec échantillonnage de 8 voisins. `none` est une variante auto-contenue non-GNN, sans agrégation de voisins : elle calcule les représentations depuis le vecteur propre de nœud, `h = tanh(Wself*x)`. Les vecteurs d’identité des nœuds restent entraînables dans les deux variantes.

La population évaluée comprend seulement les observations produit–trimestre ayant au moins un lien positif, au seuil de soutien historique produit ≥ 1. Les ensembles de candidats vérifiés dans les sorties ont les mêmes identifiants, labels, soutiens et empreintes pour chaque comparaison.

| Cohorte | Produits–trimestres avec positifs | Liens positifs | Paires candidates |
|---|---:|---:|---:|
| Validation 2023 | 3 483 | 7 705 | 1 618 588 |
| Test 2024 | 2 950 | 6 003 | 1 367 736 |
| Test 2025 | 3 420 | 7 171 | 1 607 420 |
| Tests groupés 2024–2025 | 6 370 | 13 174 | 2 975 156 |

Le groupe 2024–2025 additionne les hits et les dénominateurs annuels; son rappel n’est pas la moyenne arithmétique des rappels des deux années. Les cohortes sont positives seulement : ces résultats ne mesurent ni la précision générale ni le comportement sur les observations sans positif.

## Résultat principal : rappel micro@10

Le rappel micro@10 est le critère primaire : hits classés dans les dix premiers rapportés au nombre de liens positifs de la cohorte. Les écarts signés sont calculés `mean30 − none30`, sans intervalle de confiance.

| Cohorte | mean30 : hits / liens positifs | Rappel mean30 | none30 : hits / liens positifs | Rappel none30 | Différence signée |
|---|---:|---:|---:|---:|---:|
| Validation 2023 | 1 580 / 7 705 | 0,205061648280 | 240 / 7 705 | 0,031148604802 | +0,173913043478 |
| Test 2024 | 1 206 / 6 003 | 0,200899550225 | 219 / 6 003 | 0,036481759120 | +0,164417791104 |
| Test 2025 | 1 569 / 7 171 | 0,218797936132 | 250 / 7 171 | 0,034862641194 | +0,183935294938 |
| **Tests groupés 2024–2025** | **2 775 / 13 174** | **0,210642173979** | **469 / 13 174** | **0,035600425080** | **+0,175041748899** |

## Mesures secondaires, soutien ≥ 1

Rappel micro@5 et micro@20 sont rapportés avec leurs hits et le même dénominateur de liens positifs. Le rappel macro@10 et le MRR sont des moyennes au niveau produit parmi les produits avec positifs; leur dénominateur est donc le nombre de produits indiqué dans la table des populations, non le nombre de liens. Ces mesures sont descriptives et n’ajoutent aucune sélection de modèle.

| Cohorte | Variante | Rappel@5 (hits / liens) | Rappel@20 (hits / liens) | Macro R@10 | MRR |
|---|---|---:|---:|---:|---:|
| Validation 2023 | mean30 | 0,122258273848 (942 / 7 705) | 0,323296560675 (2 491 / 7 705) | 0,236504260776 | 0,168020824253 |
| Validation 2023 | none30 | 0,020506164828 (158 / 7 705) | 0,053471771577 (412 / 7 705) | 0,033186167315 | 0,033308161362 |
| Test 2024 | mean30 | 0,122438780610 (735 / 6 003) | 0,309511910711 (1 858 / 6 003) | 0,233641384581 | 0,162336968817 |
| Test 2024 | none30 | 0,022488755622 (135 / 6 003) | 0,062468765617 (375 / 6 003) | 0,036651859935 | 0,036554668775 |
| Test 2025 | mean30 | 0,131222981453 (941 / 7 171) | 0,329661135128 (2 364 / 7 171) | 0,250324262279 | 0,172097614913 |
| Test 2025 | none30 | 0,019244177939 (138 / 7 171) | 0,058569237205 (420 / 7 171) | 0,035934011833 | 0,031389429567 |
| Tests groupés 2024–2025 | mean30 | 0,127220282374 (1 676 / 13 174) | 0,320479732807 (4 222 / 13 174) | 0,242598282811 | 0,167577378495 |
| Tests groupés 2024–2025 | none30 | 0,020722635494 (273 / 13 174) | 0,060346136329 (795 / 13 174) | 0,036266453262 | 0,033781494820 |

## Pertes d’entraînement observées

La perte exportée est la moyenne de `softplus(−marge)` sur les triplets visités avant la mise à jour de l’époque. Elle n’inclut pas la régularisation et n’est pas l’objectif pénalisé complet. Chaque ligne du CSV est une époque réellement observée; chaque fit compte 30 époques, et les pas/triplets visités sont donnés dans ce fichier.

| Fit / origine | Perte époque 1 | Perte époque 30 | Pas sur le fit | Positifs sautés |
|---|---:|---:|---:|---:|
| mean30, validation 2023 — C réutilisé | 0,6927517690732703 | 0,2102084021452126 | 2 030 280 | 0 |
| mean30, réajustement test 2024 — C réutilisé | 0,6927316613411573 | 0,2212121668598577 | 2 269 710 | 0 |
| mean30, réajustement test 2025 — C réutilisé | 0,6733420390007733 | 0,2088448921079758 | 2 456 730 | 0 |
| none30, validation 2023 — nouvel ajustement D1 | 0,6931453622076820 | 0,6931471805589248 | 2 030 280 | 0 |
| none30, réajustement test 2024 — nouvel ajustement D1 | 0,6931324775983980 | 0,6931471805588587 | 2 269 710 | 0 |
| none30, réajustement test 2025 — nouvel ajustement D1 | 0,6931399471343127 | 0,6931471805588161 | 2 456 730 | 0 |

Pour les trois fits none30, la perte mesurée reste au voisinage de `ln(2)` et ne baisse pas au cours des 30 époques; c’est une observation de ces journaux sous ces paramètres, pas un diagnostic de mécanisme ni une explication causale des rappels. Elle ne motive ici aucun ajustement de paramètres.

## Capacités des variantes

La dimension est 8 pour les deux modèles, mais leurs transformations actives ne sont pas de capacité égale : 128 scalaires de transformation partagée pour mean, 64 pour none. Les vecteurs d’identité appris ont le même nombre de scalaires dans chaque paire de fits; l’écart des paramètres actifs totaux est de 64 scalaires dans les trois cohortes.

| Fit | Scalaires actifs des vecteurs de nœuds (communs) | Transformation mean / none | Paramètres actifs totaux mean / none |
|---|---:|---:|---:|
| Validation 2023 | 27 152 | 128 / 64 | 27 280 / 27 216 |
| Test 2024 | 28 608 | 128 / 64 | 28 736 / 28 672 |
| Test 2025 | 29 712 | 128 / 64 | 29 840 / 29 776 |

Le contraste observé regroupe donc le changement d’agrégation (GraphSAGE contre self-only non-GNN) et la différence de paramètres de transformation (128 contre 64), en plus de la réutilisation du modèle mean issu de C. Il ne constitue pas un effet causal isolé de l’agrégation à capacité égale.

## Coûts mesurés et origine

Les temps de fit sont séparés des temps du superviseur de phase. Le fit mean30 est un coût mesuré dans C puis réutilisé; les fits none30 et leurs phases sont mesurés lors de D1. Les temps sont en secondes (mural / CPU worker).

| Fit mesuré | mean30 C : mural / CPU | none30 D1 : mural / CPU |
|---|---:|---:|
| Validation 2023 | 272,092 / 269,570 | 105,233 / 104,899 |
| Réajustement test 2024 | 309,817 / 307,939 | 117,517 / 117,036 |
| Réajustement test 2025 | 333,749 / 332,469 | 127,786 / 127,402 |

| Phase superviseur | C : mural / CPU worker | D1 : mural / CPU worker |
|---|---:|---:|
| Validation 2023 | 482,360 / 478,759 | 128,005 / 127,589 |
| Test 2024 | 329,318 / 327,364 | 136,895 / 136,330 |
| Test 2025 | 356,214 / 354,860 | 150,303 / 149,847 |

La validation C supervise la grille complète de durée `0/3/10/30` et son évaluation; la phase validation D1 supervise uniquement le fit none30 et son évaluation. Ces durées de phase ne sont pas comparables comme coûts de fits isolés. Les temps de test viennent également de deux exécutions et architectures distinctes. Aucun budget CPU égalisé n’est revendiqué. Les sorties sources appliquaient un plafond de 900 s, 512 MiB RSS agrégée et 512 MiB de sorties par phase; le total de plusieurs phases n’est pas un budget global.

Le nouveau run D1 totalise **416,144 s** (415,203 s de phases, CPU worker 413,766 s). Pics RSS agrégés validation/test2024/test2025 : **303 284 224 / 300 412 928 / 302 727 168 octets** ; sorties de phase **28 982 697 / 24 356 623 / 28 699 696 octets**. Chaque phase termine sous ses trois plafonds sans retry. Les trois fits nouveaux cumulent **6 756 720 pas**, 90 époques observées et aucun positif sauté ; les 90 époques C30 dans le CSV sont conservées, pas rejouées en entraînement.

## Audit numérique exhaustif et réserve de télémétrie

L'[audit détaillé](../../../results/generated/consolidation-post-RC1/maude-aggregation-20261002T205122Z/postchecks/numeric_invariants.json) reconstruit l'éligibilité, les premières relations et les candidats depuis les 28 instantanés préparés, puis l'inférence `none` depuis **trois checkpoints bruts**. Les embeddings exportés ne servent pas de réponses.

- **4 593 744 scores nouveaux** contrôlés sans échantillonnage, avec chaque rang, label et EOF ; appariement de ces mêmes paires aux exports C30, eux-mêmes rattachés aux 50 empreintes réutilisées pinnées.
- **12 trimestres**, 9 853 listes candidates par variante ; **9 187 488 entrées d'IDs au total des deux exports**, soit 4 593 744 de chaque côté. Le champ brut `candidate_ids_compared_per_model` porte ce total des deux côtés, malgré son nom ; il ne double pas le nombre de paires distinctes.
- 12 tables trimestrielles, validation et deux tables annuelles, puis regroupement et contraste recalculés ; 90 époques nouvelles appariées aux 90 époques C30 conservées. Configurations, paramètres inactifs, cohortes, pas/sauts et plafonds des trois phases concordants.
- **51 260 776 contrôles, zéro écart numérique** ; entiers/listes/hash exacts et flottants à tolérance absolue `1e-12`. Aucun nouvel entraînement ou ancien audit de scores C relancé.
- Verrouillage `20:53:30.842192Z` et première trace test2024 créée `20:53:30.847309Z` : ordre étayé par les traces et horloges locales, pas attestation externe ni preuve de non-exposition antérieure.

L'audit dure **58,547 s**. Ses mesures mémoire finales divergent : `VmHWM`/`VmRSS` **118 292 480 octets**, contre `getrusage(RUSAGE_SELF).ru_maxrss` **571 580 416 octets**, au-dessus de 512 MiB. Les deux restent consignées ; faute de mesures initiales, aucune certification globale « audit sous 512 MiB » ni attribution certaine au lanceur n'est revendiquée. Cela ne modifie pas les mesures agrégées des trois phases d'entraînement ci-dessus.

Un [probe non médical de télémétrie](../../../results/generated/consolidation-post-RC1/maude-aggregation-publication-20261002T205122Z/rss_exec_probe.json), sans relance de l'audit, observe sur le même PID : avant `exec`, les deux pics valent 49 500 160 octets ; après, `VmHWM` vaut 15 872 000 et `ru_maxrss` reste 49 500 160. Les [métriques `getrusage` sont conservées à travers `execve`](https://man7.org/linux/man-pages/man2/getrusage.2.html), contrairement à la portée de l'espace mémoire courant observée par le probe. Cette différence de portée explique une possibilité de divergence, pas la provenance certaine du pic historique de cet audit.

Script reproductible local : `postchecks/audit_numeric_invariants.py` dans le run D1, SHA-256 `e4cd12daf389a6d5d273a31d9c4363ace652792a655f5d42e04e859ddc173f66` ; rapport SHA-256 `5137c4c7a8df56b1c5ce84d41f1ce913b9d4add2db0048e639a7a550978213b7`. L'audit lit les sorties existantes, sans fit ; il réutilise les utilitaires immuables de l'audit C.

## Interprétation et limites

Les écarts de rappel observés sont nets dans ces cohortes et dans ce point d’entraînement précis; ils ne démontrent ni causalité, ni significativité statistique, ni optimum, convergence, ni supériorité générale d’une famille de modèles. Il s’agit d’une réanalyse exploratoire de périodes déjà consultées, et non d’une confirmation indépendante; aucune approbation humaine indépendante n’est revendiquée. Aucun bootstrap ou nouvel intervalle de confiance n’a été calculé.

Les résumés et journaux rapportés proviennent uniquement des sorties C/D1, produites à partir des 28 instantanés préparés. Les timestamps de ces instantanés suivent `DATE_RECEIVED`, sans preuve d’une disponibilité publique à ces dates. La sélection D1 précède le test D1 selon son verrou, mais les périodes de test sont historiques et avaient déjà été consultées. Le filtrage aux observations ayant au moins un positif exclut les observations sans positif et ne permet pas d’évaluer précision, charge générale ou couverture sur la population complète.

`none` est un modèle self-only non-GNN avec vecteurs de nœuds entraînables; la comparaison ne mesure pas la suppression abstraite d’un opérateur d’agrégation en maintenant toute capacité et tout entraînement constants. D1 n’a ajouté ni tuning, ni graines, ni bootstrap/IC, ni nouveau fit mean; aucune expérience D2 n’est incluse.
