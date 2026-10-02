# Protocole C — durée d'apprentissage GraphSAGE sur MAUDE

**Fixé techniquement le 2 octobre 2026, avant tout nouvel entraînement de ce cycle.**
Statut actualisé après l'exécution : diagnostic **exécuté le 2 octobre 2026**, grille complète et 30 époques sélectionnées avant les nouveaux tests historiques. Le protocole effectivement lancé, SHA-256 `69cda4bbd4cd86c3ebbe2346346e2a6292ef69a89699d92e1b628bc504fcb94a`, reste conservé dans le run et au commit `4a22c2addc8203efd2b38a60c416270855c3bf3b` ; cette mise à jour documentaire ne change pas rétrospectivement sa règle. Voir le [rapport C](verification/maude_duration_diagnostic.md). Ce document n'est pas une préinscription externe, une validation humaine des auteurs ou une preuve de confirmation indépendante.

## Question et périmètre

Mesurer l'effet de la durée d'apprentissage de la variante GraphSAGE historique à un saut, sans changer cible, candidats, initialisation, négatifs, agrégation, dimension ou métriques. Les périodes 2023–2025 ont déjà été consultées pendant le développement : les résultats nouveaux resteront exploratoires. Le contrôle synthétique ne répond pas à cette question MAUDE.

Le code de référence est `healthgraphbench/tasks/maude/models.py::fit_graphsage` et l'évaluation `healthgraphbench/tasks/maude/evaluate.py`. Les tags historiques et RC1 ne sont jamais modifiés. Le code effectivement instrumenté devra être identifié par son SHA-256 ; il devra conserver les scores du chemin historique pour les mêmes entrées et trois époques.

## Entrées fixées et limites

- Archive locale RC1 : `results/generated/manuscript-rc1/HealthGraphBench_FAIA_LaTeX_RC1.zip`, SHA-256 `2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be`.
- Membre : `HealthGraphBench_RC1/data/real_R6/maude_B/prepared_snapshots.json.gz`, SHA-256 `1cba7f84ff24131715c68a985d9302c96c7bab4a4b2a27d906559a41104fbd36`.
- Les instantanés préparés contiennent seulement `quarter`, `product_reports`, `edges`. Ils donnent le graphe biparti, le soutien produit, les premières relations et les listes candidates nécessaires à ce diagnostic. Ils ne permettent pas de prétendre reconstruire toutes les caractéristiques tabulaires, les fabricants ou les multiplicités de signalements par arête.
- L'histoire doit être alimentée par ces valeurs réellement présentes, sans inventer les champs absents d'un `DataBundle` complet. La chaîne de collecte FDA antérieure est une provenance historique, pas une réacquisition effectuée par ce diagnostic.
- Le filtre temporel utilise l'horloge MAUDE `DATE_RECEIVED` telle que préparée ; il ne prouve pas la disponibilité publique historique de chaque champ.

La [faisabilité calculée](verification/maude_diagnostic_feasibility.md) confirme le graphe au réajustement 2023Q1 : **2 878 produits, 516 problèmes, 67 676 arêtes**. Ces nombres sont conformes au tableau RC1 `training_graph.csv` ; ils ne sont pas des logs d'optimiseur.

## Configuration et grille

| Paramètre | Choix fixé |
|---|---|
| Époques | **0, 3, 10, 30** ; quatre résultats à conserver |
| Dimension | 8 |
| Voisins | 8, échantillonnage déterministe historique |
| Taux d'apprentissage | 0,02 |
| Régularisation | 0,0005, mises à jour inchangées |
| Objectif | BPR ; activation `tanh` |
| Initialisation | Ordres de nœuds triés et initialisation historique |
| Négatif | Hachage historique dépendant de l'époque, du produit et du problème ; exclure les voisins historiques du produit |
| Graines/sensibilités | Aucune variante d'initialisation ou de négatifs dans ce minimum |

Zéro époque est un témoin d'initialisation, **jamais un candidat à sélectionner**. Les quatre ajustements partent de la même histoire et de la même initialisation ; pas de warm-start d'une configuration vers la suivante. Le réemploi de préfixes d'un entraînement plus long exigerait une modification datée et une preuve d'équivalence, pas une optimisation silencieuse.

## Validation 2023 et sélection

1. Construire l'histoire 2019Q1–2022Q4, sans incorporer 2023 avant l'ajustement.
2. Ajuster chaque durée au réajustement 2023Q1. Garder la représentation apprise fixe pour les quatre trimestres de validation, comme dans le chemin historique.
3. Avant chaque trimestre, définir les positifs comme premières relations observées, avec produit ayant au moins un signalement antérieur et problème déjà connu globalement. Les candidats sont tous les problèmes historiquement connus sauf ceux déjà observés pour ce produit.
4. Classer la liste candidate **entière** par score décroissant, puis nombre décroissant de produits historiques associés au problème, puis code problème croissant. C'est la règle exacte de `_ranked_candidates`, pas un simple tri lexical en cas d'égalité.
5. Conserver le repli historique à zéro pour un nœud absent de la représentation. Ne pas retirer les candidats non représentés. Mettre à jour l'histoire seulement **après** l'évaluation du trimestre.
6. Calculer le rappel micro à 10 au seuil historique de soutien produit 1 : somme des hits / somme des liens positifs sur les quatre trimestres. Ne pas faire la moyenne des rappels trimestriels.
7. Une fois la **grille complète** terminée, sélectionner parmi 3, 10 et 30 le plus grand rappel micro à 10 sur validation ; égalité numérique exacte → durée la plus courte. Aucune sélection sur le test, aucune sélection de zéro et aucune sélection sur une grille incomplète.

La population validation calculée contient **3 483 produit–trimestres avec positif, 7 705 liens positifs et 1 618 588 paires candidates**. Elle ne définit pas une précision ou charge générale sur les observations sans positif. Rappels à 5/20, rappel macro et MRR sont descriptifs secondaires ; aucun n'est un critère alternatif choisi après lecture des scores.

## Test historique après verrouillage

Écrire et dater la décision de sélection avant de produire de nouveaux scores de test. Avec la seule durée retenue :

- Réajustement 2024Q1 sur l'histoire jusqu'à 2023Q4, puis évaluation roulante de 2024Q1–Q4, mise à jour après chaque trimestre.
- Réajustement 2025Q1 sur l'histoire jusqu'à 2024Q4, puis évaluation roulante de 2025Q1–Q4, même règle.
- Conserver séparément 2024, 2025 et leur agrégation définie par les dénominateurs ; ne pas retoucher les paramètres après lecture de ces scores.

Ce passage est une **nouvelle analyse exploratoire** des tests historiques, pas une confirmation indépendante. Conserver résultats historiques et nouveaux côte à côte, sans écrasement. Une confirmation sur une origine réellement non consultée est hors de ce protocole et nécessite sa propre décision avant ouverture.

## Instrumentation minimale requise avant lancement

Le chemin historique du benchmark accepte le nombre d'époques mais ne conserve ni pertes d'optimisation, ni état brut des vecteurs/transformations, ni checkpoint sur disque. L'instrumentation nouvelle doit satisfaire les exigences suivantes avant le lancement ; sa seule présence ne prouve pas encore le diagnostic :

- Instrumenter les triplets effectivement visités sans changer leur ordre ni les gradients. Enregistrer par époque le nombre d'étapes réellement effectuées, les positifs sautés et la moyenne de `softplus(-marge)` **avant mise à jour** sur ces triplets. Nommer ce terme « perte de données BPR » : ce n'est pas, à lui seul, l'objectif pénalisé complet ; garder la régularisation explicitement séparée.
- Si une perte diagnostique est évaluée sur d'autres exemples, la nommer et la séparer de la perte d'optimisation. Pour zéro époque, il n'y a pas de perte d'optimisation observée.
- Enregistrer paramètres, clés de nœuds, voisinages échantillonnés, représentations, transformations et vecteurs d'entrée nécessaires à un checkpoint de l'état appris. Distinguer checkpoint d'inférence et état permettant une reprise ; ne pas appeler « reprise possible » un export insuffisant.
- Conserver scores/rangs et labels avec identifiants produit–trimestre–problème, listes candidates originales et empreintes ; formats compacts compressés et sorties séparées par durée/réajustement.
- Mesurer temps mural/CPU, pic RSS, nombre de pas et environnement. Toute comparaison de budgets avec les méthodes historiques reste non démontrée.

## Plafond opérationnel et arrêt

Plafond technique conservateur pour un lancement local : **un seul processus d'apprentissage à la fois sous un contrôleur léger, bibliothèques mono-thread, 900 secondes pour la grille validation, puis 900 secondes au maximum par réajustement test, 512 MiB RSS agrégée contrôleur + worker et 512 MiB de nouvelles sorties par phase**. Ce plafond n'est pas un temps d'exécution prédit ou une égalisation des budgets historiques. Vérifier les ressources disponibles au lancement ; le cadrage initial avait observé une RAM disponible faible et un swap saturé.

Les ajustements indépendants de la grille impliquent **2 910 068 visites de triplets** sur ce graphe si toutes sont effectuées. Cette charge était calculée avant lancement, pas mesurée. Les temps et pas désormais observés sont dans le rapport C. Tout nouveau lancement exige un mécanisme effectif d'arrêt et de consignation des dépassements ; une limite écrite seule ne constitue pas son application.

Au dépassement ou à une erreur : arrêter, conserver la configuration, les étapes terminées et l'erreur dans un nouvel identifiant de run. La grille incomplète reste incomplète ; pas de sélection opportuniste, pas de métrique d'une cohorte tronquée. Toute augmentation du plafond est une décision datée, pas l'attente d'un meilleur score.

**Précision opérationnelle du 2 octobre 2026, avant le premier lancement C :** le contrôleur est réservé à la surveillance du délai, de la RSS et des sorties ainsi qu'à l'arrêt effectif du worker. Aucun entraînement, ajustement ou trimestre n'est parallélisé ; les quatre fits restent indépendants. La mesure de RSS inclut les deux processus, et les limites numériques ne sont pas augmentées. Cette précision rend l'arrêt indépendant de la coopération du code d'apprentissage, sans changer données, objectif, ordre des mises à jour ni règle de sélection.

## Sorties et critère de fin

Nouvelle destination : `results/generated/consolidation-post-RC1/<run-id>/`, jamais RC1 ni un ancien run. Petits manifestes, protocole, rapport et limites destinés à Git ; gros états et scores restent ignorés et sont publiés séparément si une nouvelle version est approuvée.

C est clos seulement lorsque la grille, ses courbes et ses limites sont documentées, la sélection est verrouillée et le passage test historique prévu est terminé, ou lorsque son non-achèvement est explicitement décidé avec conclusions restreintes. Une hausse de score ou une convergence démontrée n'est pas requise. **Exécution observée : grille 0/3/10/30 complète ; 30 époques verrouillées à 17:32:26 UTC avant les tests 2024 puis 2025, tous deux complets.** Les conclusions restent exploratoires, attachées aux entrées préparées et à la grille fixée.
