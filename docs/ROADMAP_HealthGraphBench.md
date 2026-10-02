# Roadmap — HealthGraphBench RC1 vers une version soumissible

**Date :** 2 octobre 2026  
**Import dans ce dépôt :** 2 octobre 2026 depuis `~/Downloads/ROADMAP_HealthGraphBench.md`.  
**Statut :** plan de travail proposé ; aucune nouvelle expérience n'est exécutée par ce document. Son import ne démarre pas le cycle scientifique et n'atteste pas que les lots ci-dessous ont été réalisés.  
**Objectif :** consolider les preuves, finaliser l'article de ressource exploratoire, puis soumettre sans prolonger indéfiniment les améliorations.  
**Horizon proposé :** quatre semaines à compter du démarrage validé, avec une décision formelle en fin de semaine 4.

> La réussite n'est ni un meilleur score de GraphSAGE, ni l'obtention d'un quartile de revue. C'est un article dont les résultats sont vérifiés, les conclusions proportionnées aux preuves et le dossier de soumission complet.

Les durées sont des fenêtres de planification, pas des temps de calcul mesurés. Elles supposent l'accès au code, aux artefacts et aux données nécessaires ; leur faisabilité doit être vérifiée en semaine 1. Les responsables sont des rôles à attribuer, éventuellement à une même personne.

**Base documentaire.** `M` désigne `HealthGraphBench_manuscrit_fr_RC1.pdf` ; `S` désigne `HealthGraphBench_supplement_fr_RC1.pdf`. Ce sont les noms sans suffixes `(1)` et `(2)` effectivement disponibles dans l'espace local source consulté pour cet import. Les originaux restent externes ; leurs copies locales dans `results/generated/manuscript-rc1/` sont ignorées par Git. Les références de section et de page renvoient à ces PDF. Les constats ci-dessous reprennent ce qu'ils rapportent : ils ne constituent pas une vérification indépendante du dépôt ou du paquet logiciel. Les priorités, échéances, expériences nouvelles et noms de livrables sont des propositions de cette roadmap, non des exigences déjà formulées par une revue.

## 1. Point de départ et périmètre à conserver

Le manuscrit présente une ressource documentée réunissant trois tâches, leurs comparateurs et des résultats versionnés. Il distingue l'intérêt de l'information relationnelle, celui d'un modèle de graphe et l'utilité d'une décision ; il ne mesure pas cette dernière. **Conserver ce positionnement**, plutôt que transformer la révision en recherche d'un nouvel algorithme. *(M, §1, p. 2.)*

Les périodes de validation et de test ont déjà été consultées pendant le développement. Les relancer ne les rendra pas intactes. Toute nouvelle exploration sur ces périodes doit rester explicitement exploratoire. *(M, §3.1, p. 4 ; §5.3, p. 13.)*

La collecte R6 rapporte une reconstruction des entrées et de la couverture MAUDE, sans recalcul des scores appris ni récupération des checkpoints. Le supplément indique qu'il manque encore un contrôle direct de GraphSAGE sur MAUDE et une ablation avec/sans agrégation. **Ne pas refaire toute la traçabilité déjà documentée ; cibler ces questions non résolues.** *(S, §S2.1, p. 3 ; §S10, p. 14.)*

Enfin, les déclarations d'auteurs et le format éditorial final restent à compléter. L'avis favorable conservé dans le paquet ne vaut pas décision éditoriale. *(S, §S11, pp. 16–17 ; M, déclarations, p. 14.)*

## 2. Priorités et calendrier

**P0 — indispensable :** exactitude des résultats centraux, traçabilité des affirmations, validation des auteurs et conformité au support retenu. Une erreur connue ne devient pas acceptable parce que le délai est écoulé.

**P1 — fortement recommandé :** un diagnostic borné de l'apprentissage GraphSAGE sur MAUDE. C'est le complément scientifique prioritaire de ce cycle ; son absence ne doit jamais être masquée par une formulation plus forte.

**P2 — conditionnel :** une seule analyse supplémentaire de comparaison contrôlée ou de couverture. La confirmation sur une période non consultée constitue une branche distincte, engagée seulement si elle est réellement réalisable.

| Fenêtre | Lot | Priorité | Responsable proposé | Livrable de sortie |
|---|---|---|---|---|
| Semaine 1, début | A. Cadrage et accès aux artefacts | P0 | Référent scientifique + développeur | Périmètre signé, inventaire et plafond de ressources |
| Semaine 1, suite | B. Vérification des résultats centraux | P0 | Développeur + second lecteur | Matrice affirmations–preuves et rapport de vérification |
| Semaine 2 | C. Diagnostic GraphSAGE sur MAUDE | P1 | Développeur, validation scientifique | Protocole daté, journaux et résultats complets |
| Semaine 3, début | D. Une analyse complémentaire au maximum | P2 | Référent scientifique + développeur | Analyse contrôlée ou report motivé |
| Semaines 3–4 | E. Intégration et finalisation | P0 | Auteurs + auteur correspondant | Manuscrit, supplément et paquet de soumission cohérents |
| Fin de semaine 4 | F. Décision de soumission | P0 | Ensemble des auteurs | Décision datée : soumettre, restreindre le périmètre ou corriger un blocage |

La sélection du support éditorial et la collecte des déclarations commencent dès la semaine 1, en parallèle des travaux techniques. La faisabilité d'une confirmation indépendante est examinée à ce même stade, pas découverte en fin de cycle.

## 3. Lot A — Cadrer la révision et sécuriser les entrées

**Question :** quels travaux peut-on effectivement mener avec les ressources disponibles ?

- [x] Conserver une copie immuable de RC1 et de ses résultats historiques. Utiliser un répertoire ou une branche distincte pour les travaux nouveaux, avec un nom provisoire tel que `consolidation-post-RC1`.
- [ ] Obtenir le paquet d'accompagnement, les sources et les entrées nécessaires. Distinguer fichiers réellement accessibles, fichiers seulement décrits dans les PDF et éléments manquants. Le supplément décrit un ZIP d'accompagnement ; cette roadmap n'atteste pas que son contenu est disponible ou exécutable. *(S, §S1, p. 2 ; §S9, p. 13.)*
- [ ] Fixer les questions étudiées, les responsables, une date de décision et un plafond de calcul. Ouvrir un journal consignant chaque changement, sa date, son motif et les résultats déjà connus au moment de la décision.
- [ ] Choisir un support principal et un support de repli ; relever leurs consignes officielles applicables, le format, la langue, les contraintes d'anonymisation et la place disponible pour les artefacts. Ne pas traiter la seule mention « FAIA » comme une cible éditoriale complètement définie. *(S, §S11, p. 17.)*

**Critère de fin :** la liste des entrées disponibles et manquantes est explicite, les travaux ont un responsable et le budget est borné.

**Règle en cas d'indisponibilité :** ne pas inventer de nouveaux scores ou de reproduction. Les analyses impossibles sont reportées ; les affirmations centrales qui ne peuvent être étayées doivent être restreintes ou retirées avant soumission.

## 4. Lot B — Vérifier les résultats centraux, sans confondre les niveaux de preuve

**Question :** chaque chiffre et chaque conclusion importante sont-ils rattachés à une preuve identifiable ?

Le supplément documente déjà des rejeux des compacts MAUDE, Part D et CMS. Ces rejeux portent sur des sorties conservées, non sur un nouvel entraînement. La distinction doit rester visible dans la révision. *(S, §S9, pp. 13–14 ; M, §6, p. 14.)*

- [ ] Rejouer les analyses centrales accessibles dans un environnement propre, avec de nouveaux chemins de sortie. Conserver les commandes, versions, empreintes, journaux et écarts observés. Utiliser les tolérances annoncées pour les rejeux concernés, sans les transformer en exigence générale de reproduction bit à bit des entraînements.
- [ ] Contrôler les dénominateurs, clés d'appariement, périodes, candidats et conventions de métriques. Pour MAUDE, ne pas calculer une précision ou une charge générale à partir du seul export limité aux observations avec positif. Pour Part D, conserver les observations sans positif dans les mesures de précision et de charge. *(S, §S6.1, p. 9.)*
- [ ] Vérifier les contrôles temporels disponibles : caractéristiques et standardisation construites sans utiliser la période cible, historique mis à jour selon le protocole, réajustements correctement datés. Distinguer date de l'événement et preuve de disponibilité publique du champ. *(M, §3.2, pp. 4–5.)*
- [ ] Construire une matrice « affirmation → fichier source → calcul → statut → limite ». Un second lecteur valide les chiffres du résumé, les contrastes centraux et leur interprétation.

**Statuts à employer :** résultat historique rapporté ; analyse rejouée sur sorties conservées ; entrées reconstruites ; entraînement réexécuté ; confirmation sur données non consultées. Ne pas utiliser un statut pour en suggérer un autre.

**Avancement technique A/B :** dix contrôles de rejeu réussis dans un environnement propre, 609/609 contrôles arithmétiques/manifeste et 42 affirmations initiales. Les cases qui incluent validation humaine, contrôle des sources primaires ou disponibilité publique historique restent ouvertes. Voir le [pilotage et ses preuves](consolidation-post-RC1/README.md) ; A/B ne revendiquent ni nouvel entraînement ni confirmation indépendante. Le nouvel entraînement C est distingué ci-dessous.

**Critère de fin :** aucune incohérence numérique centrale n'est laissée inexpliquée, et chaque affirmation conservée peut être reliée à sa preuve et à ses limites. Un contrôle non réalisable est déclaré comme tel, pas marqué « réussi ».

## 5. Lot C — Diagnostiquer l'apprentissage GraphSAGE sur MAUDE

**Question :** la contre-performance observée dépend-elle fortement de la durée d'apprentissage retenue ?

Dans le diagnostic **synthétique** du tableau 10, page 12 du supplément, le rappel à 1 passe de 0,083333 après trois époques à 1 après trente époques. Cela motive un contrôle réel, mais ne démontre pas que trois époques sont insuffisantes sur MAUDE. *(S, §S8.1, p. 12 ; §S8.2, p. 13.)*

### Protocole minimal proposé

- [x] Dater le protocole avant les nouvelles exécutions. Conserver les cibles, les candidats, les règles d'éligibilité et de départage historiques. Déclarer que les périodes ont déjà été consultées.
- [x] Commencer sur l'historique d'entraînement antérieur à 2023 et la validation 2023. Tester une petite grille de durées, **fixée avant lancement** : `0, 3, 10, 30` époques. Conserver les autres paramètres de la configuration gelée pour cette première sensibilité. Zéro époque est un témoin, pas une configuration à sélectionner.
- [x] Choisir à l'avance le critère de sélection parmi les configurations entraînées : rappel micro à 10 sur validation, avec préférence à la durée la plus courte en cas d'égalité. Ne pas choisir les paramètres d'après les nouveaux scores de test.
- [x] Enregistrer les pertes réellement calculées, les scores, les rangs, les checkpoints d'inférence, les clés des nœuds représentés, les paramètres, le nombre d'étapes, le temps et la mémoire mesurés. La perte de données BPR avant mise à jour n'inclut pas la régularisation ; la reprise d'entraînement n'est pas implémentée.
- [x] Une fois la configuration choisie sur validation, effectuer un passage d'évaluation sur les périodes historiques de test selon les réajustements prévus. Présenter ce résultat comme une nouvelle analyse exploratoire, à côté des résultats historiques, sans les écraser.

Les négatifs historiques sont déterminés par hachage selon la description du supplément. Répéter exactement la même exécution renseigne sur son déterminisme, pas sur sa robustesse à d'autres initialisations ou échantillonnages. Une telle sensibilité demanderait une variante explicitement définie et versionnée ; elle n'est pas nécessaire au diagnostic minimal. *(S, §S2.1, p. 3.)*

**Livrable :** un rapport court contenant la grille complète, les courbes d'apprentissage, les écarts aux résultats historiques, les conditions d'exécution et la portée des conclusions. Les temps nouvellement mesurés ne prouvent pas rétrospectivement l'égalité des budgets entre toutes les méthodes.

**Critère de fin :** on peut décrire l'effet des durées testées et les limites du diagnostic. Ni une hausse de score ni une convergence démontrée ne sont requises pour clore le lot. Une amélioration à trente époques ne démontre pas davantage l'optimalité de cette durée.

**Décision associée :** si les résultats changent substantiellement, modifier le message de l'article. Si un défaut d'implémentation affecte une conclusion centrale, corriger et réévaluer avant soumission. Si le calcul est inaccessible ou dépasse le budget, conserver une conclusion limitée à la configuration historique et documenter le contrôle non réalisé.

**Résultat C réellement exécuté :** validation R@10 `0/3/10/30 = 0,022193 / 0,171577 / 0,166905 / 0,205062` ; 30 époques verrouillées avant les tests. Test agrégé 2024–2025 : **2 775 / 13 174 = 0,210642**, sur 6 370 observations avec positif. GraphSAGE historique à trois époques reste `0,172840` et les voisins historiques `0,192045` ; les écarts nouveaux sont descriptifs, sans nouvel intervalle ni comparaison de budgets égaux. Le [rapport, les courbes et les preuves C](consolidation-post-RC1/verification/maude_duration_diagnostic.md) détaillent les 900 s / 512 MiB respectés par chaque phase.

**Message à intégrer en E :** la contre-performance du GraphSAGE historique à trois époques ne caractérise pas toutes les durées. La configuration 30 époques sélectionnée sur validation donne une valeur ponctuelle test supérieure aux références historiques citées. Cela ne démontre ni supériorité statistique, ni effet causal de l'agrégation, ni optimum à trente époques. RC1 est conservée ; aucun manuscrit révisé ou accord d'auteur n'est anticipé.

## 6. Lot D — Choisir une seule analyse complémentaire

**Plafond proposé :** trois jours de travail actif, sous réserve des ressources fixées au lot A. Ne pas engager les deux options dans ce cycle.

### Option D1 — Avec et sans agrégation

À privilégier si le lot C a fourni une chaîne d'entraînement fiable et instrumentée.

- [ ] Définir une variante avec agrégation et une variante sans agrégation, sur le même graphe historique, les mêmes exemples, candidats, négatifs, dimensions et règles d'évaluation autant que possible. Documenter ce qui change réellement, y compris la capacité du modèle.
- [ ] Fixer les budgets et la sélection sur validation avant consultation des nouveaux tests. Publier les deux résultats, quelle que soit leur direction, avec une interprétation limitée à cette comparaison.

**Critère de fin :** la comparaison informe sur l'agrégation dans cette configuration, sans attribuer tous les écarts entre familles de modèles à ce seul facteur. L'absence d'une telle ablation est explicitement indiquée dans la version actuelle. *(M, §5.1, p. 12 ; S, §S2.1, p. 3.)*

### Option D2 — Performances et couverture des représentations

À privilégier si les sorties détaillées et les inventaires peuvent être appariés sans nouvelle collecte importante.

- [ ] Définir avant la nouvelle analyse les strates de couverture et leurs dénominateurs, puis comparer les méthodes sur les **mêmes observations et les listes candidates originales**. Ne pas supprimer les candidats non représentés pour améliorer artificiellement le classement.
- [ ] Rapporter les effectifs de chaque strate et présenter les différences comme descriptives. Une restriction aux listes entièrement couvertes change la population et n'isole pas causalement l'effet du repli à zéro.

**Critère de fin :** l'analyse ajoute des performances par strate, pas une simple répétition des taux de couverture déjà livrés. La présence d'une clé dans un inventaire reconstruit reste distincte de l'inspection d'un vecteur appris. *(S, §S10.2, pp. 15–16.)*

## 7. Branche conditionnelle — Confirmation sur une origine non consultée

**Décision de faisabilité :** à prendre en semaine 1. Ne pas présumer qu'une nouvelle année de données est accessible, complète ou exploitable.

Le manuscrit identifie trois conditions : une origine non consultée, des choix documentés avant son ouverture et une disponibilité historique des champs vérifiée. Cette branche répond à une question différente de la reproduction des calculs existants. *(M, §6, p. 14.)*

- [ ] Identifier une période ou une cohorte réellement non utilisée dans les décisions de développement ; vérifier l'accès aux données et la maturité des observations cibles sans sélectionner le test d'après les performances.
- [ ] Fixer avant ouverture les modèles, paramètres, candidats, métriques, contrastes, règles de mise à jour et méthode d'incertitude. Documenter la disponibilité des informations à chaque origine.
- [ ] Conserver tous les résultats de cette évaluation. Tout réglage motivé par leur lecture devient une nouvelle exploration, non une continuation de la même confirmation.

**Règle de calendrier :** intégrer cette branche à l'article uniquement si elle est réalisable dans l'enveloppe fixée, sans sacrifier les P0. Sinon, consigner son protocole et la réserver à une version ultérieure. Une confirmation sur une seule tâche n'étend pas automatiquement ses conclusions aux deux autres.

## 8. Lot E — Finaliser le manuscrit et le dossier

### Cohérence scientifique

- [ ] Mettre à jour résumé, tableaux, discussion et conclusion à partir des seules analyses réellement terminées. Séparer résultats gelés, nouvelles explorations et éventuelle confirmation.
- [ ] Vérifier la concordance entre versions française et anglaise, supplément et fichiers numériques. Conserver les conventions distinctes d'AP, les périmètres annuels ou regroupés et les populations évaluées ; ne pas transférer un intervalle à une autre métrique. *(M, §3.4, pp. 6–7 ; §4.3–4.4, pp. 9–10.)*
- [ ] Maintenir les distinctions essentielles : CMS compare deux logistiques ; les variables tabulaires MAUDE incluent déjà du relationnel ; Part D n'a pas de comparateur strictement local. Ne pas conclure à l'inutilité générale des graphes, à une équivalence démontrée ou à une utilité clinique. *(S, §S2.1–S2.2, pp. 2–3 ; M, §4.2, p. 9 ; §4.5, p. 10 ; §5, pp. 12–13.)*

### Validation des auteurs et livraison

- [ ] Faire valider les résultats et références par les auteurs. Renseigner identités, affiliations, correspondant, contributions, financement, conflits d'intérêts, position éthique, conditions d'usage des données et assistance par IA. Ne pas remplacer une information manquante par « aucun » ou une dispense supposée. *(M, déclarations, p. 14 ; S, §S11, p. 17.)*
- [ ] Compiler selon les instructions du support choisi et relire les PDF finaux. Préparer les pièces requises par ce support, sans présenter l'avis conservé dans RC1 comme une acceptation éditoriale. *(S, §S11, pp. 16–17.)*
- [ ] Produire un paquet versionné avec commandes, environnement, résultats, journaux et limites connues. Vérifier son contenu et ses chemins d'accès. Distinguer la version du benchmark de celle du manuscrit et ne pas attribuer au nouveau paquet le DOI d'un autre objet. *(S, §S1, p. 1 ; §S9, p. 13.)*

**Critère de fin :** un lecteur peut identifier ce qui a été exécuté, ce qu'il peut reproduire et ce qui reste non vérifié ; les auteurs ont approuvé le dossier à soumettre.

## 9. Lot F — Décider et arrêter les améliorations

| Situation à l'échéance | Décision proposée |
|---|---|
| P0 terminés, résultats centraux étayés, aucune anomalie bloquante | Soumettre au support retenu avec les compléments réellement terminés. |
| Confirmation indépendante indisponible, mais périmètre exploratoire solide | Soumettre sans requalifier les anciens tests ; reporter la confirmation. |
| Diagnostic P1 ou analyse P2 non réalisable, sans anomalie centrale identifiée | Décider explicitement d'une soumission au périmètre plus limité ; supprimer toute conclusion qui dépendrait du complément absent. |
| Erreur de code, incohérence centrale ou fuite d'information affectant les résultats | Suspendre l'envoi, corriger le point identifié et fixer une nouvelle échéance bornée. |
| Compléments modifiant l'ordre des méthodes | Réviser les conclusions et publier l'évolution ; ne pas chercher à préserver le classement historique. |
| Seul motif de prolongation : viser un quartile supérieur ou obtenir un score plus favorable | Ne pas prolonger ce cycle pour ce seul motif. |

### Validation finale

- [ ] Chaque conclusion centrale correspond à une preuve identifiable et à la bonne population.
- [ ] Les anomalies connues sont corrigées, ou les affirmations qu'elles invalident ont été retirées.
- [ ] L'exposition aux tests et la portée des intervalles sont déclarées sans ambiguïté.
- [ ] Les analyses nouvelles sont séparées des résultats historiques, avec des sorties conservées.
- [ ] Les auteurs ont approuvé le contenu, les déclarations et le support ; les fichiers requis sont prêts.

**Règle d'arrêt :** une limite explicitement assumée peut rester dans un article exploratoire ; une contradiction non résolue entre les preuves et la conclusion ne doit pas rester. La soumission est une décision des auteurs, pas une garantie d'acceptation.

## 10. Organisation proposée des livrables

L'organisation ci-dessous est en place pour les preuves techniques A/B et le diagnostic C réellement exécuté. La grille, la sélection et les tests historiques C sont complets ; les conclusions restent exploratoires. La présence des documents ne clôt pas les validations scientifiques humaines ni les livrables de soumission.

```text
docs/
├── ROADMAP_HealthGraphBench.md
└── consolidation-post-RC1/
    ├── README.md                       # Index des lots, de l'état et des preuves
    ├── scope_and_decisions.md          # Décisions d'organisation et prérequis à obtenir
    ├── inventory.csv                   # Inventaire réel des pièces disponibles/manquantes
    ├── claims_evidence.csv              # Affirmations historiques et nouvelles C, statuts et limites
    ├── experiment_protocol.md           # C fixé avant lancement ; statut après exécution
    ├── verification/                    # Rejeux, audits, rapport et courbes C
    ├── scientific_changes.md            # Évolution des preuves ; chiffres historiques conservés
    └── submission_checklist.md          # Contrôles E/F et décision de soumission

results/
├── SHA256SUMS_manuscript_rc1            # Empreintes des copies RC1, sans rendre la version mutable
├── consolidation_core_verification_20261002.json # Manifeste compact des vérifications A/B
├── SHA256SUMS_consolidation_20261002     # Empreintes A/B conservées, non réécrites par C
├── maude_duration_diagnostic_20261002T172405Z.json # Manifeste compact du nouvel entraînement C
├── maude_duration_epochs_20261002T172405Z.csv      # Pertes observées, témoin zéro explicite
├── SHA256SUMS_maude_duration_20261002T172405Z      # Empreintes du nouvel incrément C
└── generated/
    ├── manuscript-rc1/                  # Copies locales RC1 en lecture seule
    └── consolidation-post-RC1/<run-id>/ # Nouvelles sorties locales par exécution
```

Les documents de pilotage, manifestes/CSV et petites empreintes sont destinés au versionnement dans Git. `results/generated/` contient les copies locales RC1 en lecture seule et les sorties nouvelles ; les gros fichiers et données brutes restent locaux ou externes selon leur nature. Les versions publiées sont immuables : une correction exige une nouvelle version et une provenance explicite. Les sources locales d'origine ne sont ni déplacées ni modifiées. A/B portent sur des sorties conservées ; C est un nouvel entraînement depuis les entrées préparées, pas une réacquisition brute, une confirmation indépendante ou une approbation des auteurs.

**À réserver à une suite distincte :** nouvelles architectures, multiplication des tâches, extension systématique des cohortes, plan factoriel complet, étude d'utilité clinique ou recherche exhaustive de réglages. Ces directions peuvent être utiles, mais ne font pas partie du minimum retenu pour ce cycle.

> Trajectoire recommandée : vérifier le socle → réaliser un diagnostic GraphSAGE borné → ajouter au maximum une analyse ciblée → finaliser → décider de la soumission à date fixe.