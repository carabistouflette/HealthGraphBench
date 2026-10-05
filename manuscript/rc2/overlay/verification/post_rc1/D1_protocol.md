# Protocole D1 — GraphSAGE avec et sans agrégation sur MAUDE

**Fixé le 2 octobre 2026 avant tout entraînement de la variante sans agrégation.** Décision de poursuite : D1 est l'unique P2 engagée ; D2 n'est pas engagée dans ce cycle. Ce protocole technique n'est ni une préinscription externe ni une approbation scientifique des auteurs.

## Question, décisions et informations déjà connues

La roadmap privilégie D1 lorsque C fournit une chaîne fiable et instrumentée. C est techniquement achevé : grille indépendante 0/3/10/30, 30 époques choisies par micro rappel@10 de validation 2023, puis nouveaux tests historiques 2024/2025. Ses sorties ont été intégralement contrôlées depuis les checkpoints bruts.

Les scores C sont **déjà connus** : validation30 `0.20506164828033743`, test groupé30 `0.21064217397904964`. Les références historiques GraphSAGE3 et voisins sont également connues. Ces connaissances font partie de la décision D1 ; elles empêchent toute qualification confirmatoire. L'objectif n'est pas de trouver une variante qui gagne, mais de documenter une comparaison à choix communs.

**Durée commune fixée : 30 époques pour les deux variantes**, issue de la sélection C sur validation. Aucun nouveau tuning indépendant de la variante sans agrégation. Sa validation à 30 époques est publiée, quelle que soit sa direction, puis le choix commun est verrouillé avant production de ses scores test. Pas de grille D1 supplémentaire, de choix sur test ou de remplacement opportuniste de durée si le score est bas.

## Variantes et capacité

- **`mean` :** chemin GraphSAGE historique à un saut, `h = tanh(W_self x + W_neighbor mean(neighbor_inputs))`, produit scalaire des représentations produit/problème. Utiliser les sorties C à 30 époques conservées et vérifiées ; **ne pas réentraîner silencieusement le témoin**. Identifier cette réutilisation et ses empreintes dans D1.
- **`none` :** `h = tanh(W_self x)` ; aucune moyenne de voisins dans la représentation, aucun gradient propagé via des voisins et aucune matrice de voisins active. Les listes de voisinages utilisées par cette variante sont vides. Une matrice de voisins nulle peut être conservée comme emplacement inactif du format de checkpoint, mais elle ne doit ni apprendre ni contribuer aux scores.
- Les vecteurs d'identité des nœuds restent entraînables dans les deux variantes, initialisés dans les mêmes ordres triés avec la même règle. `W_self` garde la même initialisation. Les représentations après agrégation ne sont pas identiques à l'initialisation : c'est une différence définie par la variante.
- À dimension8, transformations partagées actives : **128 scalaires dans `mean`, 64 dans `none`**, en plus des vecteurs de nœuds de taille `8 × (produits + problèmes)`. L'absence de voisins réduit donc aussi la capacité active et les chemins de gradient. Ce n'est pas un contrôle de capacité strictement égale ni une preuve d'effet causal pur de l'agrégation.
- `none` est un modèle BPR à vecteurs d'identité et transformation propre partagée, pas un GNN de propagation. Le nom de classe commun d'inférence ne requalifie pas cette variante en message passing.

Le chemin `mean` par défaut, les paramètres historiques et les anciens checkpoints C doivent garder leur sémantique et leurs scores. L'équivalence après modification doit être vérifiée avant tout entraînement de santé D1. Les checkpoints restent d'inférence, `resume_supported=false`.

## Entrées et paramètres communs

- Entrée préparée RC1 : `results/generated/consolidation-post-RC1/core-verification-20261002/inputs/HealthGraphBench_RC1/data/real_R6/maude_B/prepared_snapshots.json.gz`, SHA-256 `1cba7f84ff24131715c68a985d9302c96c7bab4a4b2a27d906559a41104fbd36`.
- Témoin conservé : `results/maude_duration_diagnostic_20261002T172405Z.json`, SHA-256 `0c8a610991e313d49a9fba03736d225897620cec86779989c8b243665942dff2`. Code C `4a22c2addc8203efd2b38a60c416270855c3bf3b`, résultats publiés `5eb82ba534169b48cf3b926aa2aadaae04c38dba`.
- Dimension8, taux0.02, régularisation0.0005, objectif BPR, activation `tanh`, fanout8 pour `mean`, désactivé dans `none`.
- Même histoire à chaque réajustement, mêmes nœuds, positifs parcourus, négatifs par hachage dépendant de l'époque, exclusion des voisins historiques, ordre des mises à jour et règle de régularisation des paramètres actifs. Les négatifs sont définis par le graphe observé même dans `none`.
- Même éligibilité, premières relations et liste candidate entière ; pas de retrait des nœuds absents. Classement : score décroissant, nombre décroissant de produits historiques associés au problème, code croissant. Repli à zéro inchangé.
- Horloge `DATE_RECEIVED` préparée ; mise à jour de l'histoire après chaque trimestre ; aucune source brute FDA réacquise, aucun champ absent inventé.

## Validation, verrouillage et test

1. Entraîner `none` 30 époques sur l'histoire jusqu'à 2022Q4 au refit2023Q1 ; représentation fixe pendant la validation2023 roulante.
2. Conserver ses résultats complets sur les mêmes **3483 observations positives, 7705 liens, 1618588 paires** que le témoin C30. Contrôler l'identité des ids/candidats/labels ; absence de cohorte complète → analyse incomplète, sans passage test.
3. Verrouiller le choix commun30, les deux variantes et le contraste, avec date et scores de validation, avant les nouveaux tests `none`. Ne pas choisir un gagnant puis omettre l'autre.
4. Réajuster `none` à2024Q1 sur l'histoire jusqu'à2023Q4, puis à2025Q1 jusqu'à2024Q4. Conserver chaque année et leur agrégation par sommes de numérateurs/dénominateurs, jamais moyenne simple des rappels annuels.
5. Rapporter le témoin C30 réutilisé et `none30` côte à côte sur **6370 observations positives, 13174 liens, 2975156 paires test**, mêmes candidats et labels. Aucun nouveau test C3 ou réentraînement des autres méthodes.

**Contraste principal : `mean30 − none30` au rappel micro@10**, soutien produit historique≥1. Secondaires descriptifs : R@5/R@20, macro R@10, MRR. Aucun bootstrap ou nouvel IC dans ce minimum ; ni analyse de performances par couverture (D2), ni sensibilité aux graines ou nouvelles architectures.

## Budgets, arrêt et provenance

Pour la seule variante nouvelle : un contrôleur léger et un worker à la fois ; **900 secondes par phase validation/test2024/test2025, 512 MiB RSS agrégée et 512 MiB de sorties par phase**, bibliothèques mono-thread. Pas d'augmentation par rapport à C. La comparaison égalise époques et exemples, pas les temps CPU/mur : réutiliser les coûts C avec leur origine, mesurer séparément ceux de `none` et ne pas prétendre à des budgets historiques égaux.

Au dépassement, erreur de télémétrie ou incohérence d'entrée/témoin : arrêter, conserver les pièces et consigner incomplet ; pas de retry automatique, sélection partielle, cohorte tronquée ou augmentation de plafond. Pas de réécriture de C, de RC1 ou d'un ancien run.

Le code, ce protocole et leurs empreintes doivent être commités avant l'exécution de santé. Destination neuve `results/generated/consolidation-post-RC1/maude-aggregation-<run-id>/`. Capturer la commande réelle, environnement, hashes d'entrées/témoin/code/protocole, pertes de données BPR avant mise à jour (régularisation distincte), pas/sauts, checkpoints bruts, scores/rangs/labels/candidats, coûts et statuts. Petits résumés/CSV/rapport/figures/empreintes dans Git ; gros états et scores locaux ignorés. Conserver le protocole exact avant tout changement ultérieur de statut documentaire.

## Critère de fin et portée

D1 est techniquement clos quand les deux résultats sont publiés avec leurs origines distinctes, les observations/candidats/labels concordent, les sorties nouvelles sont contrôlées depuis les checkpoints et le contraste, coûts et limites sont documentés ; ou lorsque son non-achèvement est explicitement décidé avec conclusions restreintes.

L'analyse informe sur ces deux variantes et cette durée commune, y compris leur différence de capacité active. Elle ne démontre ni causalité générale d'agrégation, ni robustesse statistique, optimum, utilité clinique, budgets égaux ou confirmation indépendante. Les seules observations avec positif ne donnent pas précision ou charge générale. Disponibilité publique historique, revue humaine A/B, support/déclarations/auteurs, manuscrit E et décision F restent ouverts. Aucune D2 n'est engagée.
