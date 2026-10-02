# Faisabilité des entrées du diagnostic MAUDE

Contrôle exécuté le 2 octobre 2026 avec Python 3.13.5 dans l'environnement propre du lot B. Aucun modèle n'a été ajusté, aucun score nouveau n'a été calculé et aucune métrique 2024/2025 n'a été examinée dans ce contrôle.

## Ce qui a été calculé

Lecture des instantanés préparés RC1, alimentation du graphe et des comptes produits strictement avant chaque trimestre, application de `eligible_edges` et des listes `History.candidate_problems`. Les champs réellement présents sont `quarter`, `product_reports`, `edges` ; aucun champ de fabricant ou de multiplicité par arête n'est fabriqué pour un faux `DataBundle`.

| Origine / période | Produits / observations avec positif | Problèmes / liens positifs | Arêtes / paires candidates |
|---|---:|---:|---:|
| Graphe avant 2023Q1 | 2 878 nœuds produits | 516 nœuds problèmes | 67 676 arêtes |
| Validation 2023Q1 | 914 observations | 2 007 liens | 425 657 paires |
| Validation 2023Q2 | 943 observations | 2 133 liens | 441 235 paires |
| Validation 2023Q3 | 893 observations | 2 136 liens | 415 234 paires |
| Validation 2023Q4 | 733 observations | 1 429 liens | 336 462 paires |
| Validation 2023 regroupée | **3 483 observations** | **7 705 liens** | **1 618 588 paires** |

Les quatre nombres de graphe/pas par époque (produits, problèmes, arêtes, triplets) ont été comparés au membre RC1 `data/real_R6/maude_B/training_graph.csv` : conformité observée. Les 67 676 triplets par époque et les 2 910 068 visites pour quatre fits indépendants de 0/3/10/30 sont des implications des boucles, pas des pas d'optimiseur mesurés.

Mesure de ce seul contrôle de graphe/éligibilité : **0,539 s**, pic RSS **144 712 KiB**. Cela ne mesure ni le temps ni la mémoire d'un entraînement GraphSAGE.

## Sources et empreintes

- Membre RC1 `data/real_R6/maude_B/prepared_snapshots.json.gz` : `1cba7f84ff24131715c68a985d9302c96c7bab4a4b2a27d906559a41104fbd36`.
- `healthgraphbench/tasks/maude/models.py` : `07ae3cbc1f21b9e8018e02a77b3825bd84a65577146ee13d3d0b4518539c9bfb`.
- `healthgraphbench/tasks/maude/evaluate.py` : `825cafb260dd2b8f8558224447a866cec9c7dba1cee5b5c5b05ad89a174145b7`.

Commande de calcul, source exacte du script jetable, versions, arguments, empreintes et résultat conservés dans `results/generated/consolidation-post-RC1/core-verification-20261002/maude_diagnostic_feasibility.json` ; environnement dans `analysis_environment.json` du même run. Les deux journaux sont locaux et ignorés ; aucun script jetable n'a été ajouté au code du projet.

## Décision de faisabilité

Les entrées du **graphe et de l'évaluation GraphSAGE** sont accessibles pour 2023 ; leur présence ne signifie pas que toutes les entrées tabulaires ou sources brutes ont été reproduites. Les checkpoints historiques n'ont pas été récupérés. Les fichiers `.pth`/`.npz` de l'environnement scientifique sont des ressources de bibliothèques, pas des checkpoints MAUDE.

Le chemin actuel fournit un paramètre `epochs` mais pas les journaux de perte d'optimisation ni la persistance des vecteurs/transformations d'un checkpoint. Ces éléments sont requis dans le [protocole C](../experiment_protocol.md) avant une exécution diagnostique interprétable. Aucune durée n'est sélectionnée et aucun plafond n'est présenté comme un temps de calcul mesuré.

Départage MAUDE conservé : score décroissant, soutien global historique du problème décroissant, code croissant. Maintenir les candidats non représentés avec le repli à zéro ; ne pas appliquer une convention d'une autre tâche. La population rapportée ici contient des observations avec positif et ne permet pas une charge/précision générale.
