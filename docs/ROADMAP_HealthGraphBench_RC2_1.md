# Roadmap actualisée — HealthGraphBench RC2.1 vers la soumission

**Date de revue :** 3 octobre 2026  
**Version de référence :** RC2.1, manuscrit et supplément.  
**Décision proposée :** passer d'un cycle d'expérimentation à un cycle borné de vérification, de finalisation éditoriale et d'approbation des auteurs.  
**Horizon proposé :** cinq à dix jours ouvrés de finalisation, une fois le paquet technique exact accessible. Cette durée est une estimation de planification, non une mesure de travail restant ou une promesse de soumission.

> Le diagnostic expérimental prioritaire de la roadmap RC1 est désormais rapporté. Il ne faut ni le recommencer par principe, ni transformer le résultat favorable à GraphSAGE30 en preuve générale. La priorité est de rendre le dossier vérifiable et soumissible.

## 1. Base documentaire et portée de cette mise à jour

Dans ce document, **M** désigne `HealthGraphBench_RC2_1_manuscrit_FR(1).pdf` et **S** désigne `HealthGraphBench_RC2_1_supplement_FR(1).pdf`. Les numéros de pages renvoient aux PDF français. La roadmap précédente est `ROADMAP_HealthGraphBench.md` ; elle reste conservée séparément.

Cette mise à jour repose sur une lecture documentaire, centrée sur les changements scientifiques, les résultats MAUDE et les éléments ouverts. Les principales fractions imprimées de C et D1 ont été recalculées arithmétiquement et concordent avec les valeurs affichées. Ce contrôle n'est ni un rejeu des prédictions, ni un recalcul des intervalles, ni une validation du code. Les scripts, checkpoints et journaux décrits dans les PDF n'ont pas été exécutés ou inspectés directement dans cette revue. La concordance bilingue exhaustive reste à vérifier.

Les mentions **rapporté** ou **documenté** ci-dessous désignent ce que les PDF présentent, pas une certification indépendante. Les échéances, priorités et livrables sont des propositions de travail.

## 2. Ce qui change réellement depuis RC1

### 2.1 Le diagnostic réel de durée est désormais documenté

L'exploration C compare sur la validation 2023 des entraînements séparés à 0, 3, 10 et 30 époques. Zéro époque est un témoin, exclu de la sélection. Les rappels micro@10 sont respectivement 0,022193381 ; 0,171576898 ; 0,166904607 ; 0,205061648. La règle de sélection retient 30 époques. La relation n'est pas monotone : dix époques font moins bien que trois. Les pertes BPR et les nombres de pas sont rapportés. **Le lot C de la roadmap précédente est donc substantiellement traité sur le plan documentaire.** [S, §S11.1, tableau 15, p. 17.]

### 2.2 Le classement MAUDE n'est plus seulement celui de la configuration historique

| Résultat sur le test 2024–2025 | Rappel micro@10 | Statut |
|---|---:|---|
| GraphSAGE à trois époques | 0,172840 | Résultat historique conservé |
| Fréquence des voisins | 0,192045 | Prédictions historiques conservées |
| GraphSAGE à trente époques | 0,210642 | Modèle retenu dans l'exploration C |

Le rapprochement GraphSAGE30–voisins rapporte 2 775 contre 2 530 liens retrouvés parmi les mêmes 13 174 liens positifs. L'écart est de 245 liens, soit +0,018597 de rappel, ou environ **+1,86 point de pourcentage**. L'IC conditionnel à 95 % est [+0,011975 ; +0,025570]. Il porte sur ce contraste de prédictions, pas sur l'effet de passer de trois à trente époques. [M, §4.1–4.2, tableaux 3–4, pp. 7–9 ; S, §S11.3, p. 19.]

**Message à conserver :** le classement historique à trois époques ne suffit pas à caractériser la famille GraphSAGE. Le résultat favorable à trente époques ne démontre ni une supériorité générale, ni une durée optimale, ni une confirmation indépendante. Le résumé et la conclusion RC2.1 reprennent déjà cette distinction. [M, résumé, p. 1 ; §7, p. 15.]

### 2.3 D1 est un diagnostic réalisé, pas une explication validée

D1 compare le modèle avec agrégation moyenne conservé de C à un contrôle `none30` sans propagation. Ce contrôle utilise encore les arêtes historiques et BPR pour apprendre ses vecteurs d'identité : il n'est pas dépourvu d'information relationnelle. La durée choisie pour `mean` lui est imposée ; les transformations actives n'ont pas la même capacité. Sa perte reste presque plate, proche de ln(2). [S, §S11.4, p. 20.]

Le graphique de la page 21 du supplément présente les rappels et les pertes ensemble. Il faut préserver cette lecture : l'écart de rappel ne prouve pas que le contrôle a été efficacement optimisé, ni que l'agrégation explique causalement cet écart. Le constat n'identifie pas non plus, à lui seul, un bug ou sa cause. [S, §S11.4 et figure 2, pp. 20–21.]

**Décision proposée :** clore D1 comme diagnostic secondaire sous réglages fixes. Ne pas ouvrir automatiquement un nouveau programme de réglage pour le faire mieux fonctionner. Une affirmation plus forte sur l'effet propre de l'agrégation exigerait une autre comparaison.

## 3. État des lots de la roadmap précédente

| Lot ou objectif | État documentaire en RC2.1 | Suite proposée |
|---|---|---|
| A — Cadrage, accès et conservation des versions | Versions, commits et pièces de provenance décrits ; l'accès effectif au paquet exact n'est pas vérifié ici | Vérifier le paquet à livrer et son inventaire, sans refaire la collecte historique par principe |
| B — Rattacher les résultats centraux à des preuves | Audits C/D1 et rapprochement GraphSAGE30–voisins rapportés | Faire un contrôle ciblé du paquet et un rejeu des analyses centrales accessibles |
| C — Diagnostic GraphSAGE sur MAUDE | Grille, pertes, sélection, résultats de test et checkpoints documentés | Clôturable après vérification ciblée des pièces ; pas de nouvelle grille exigée |
| D1 — Une analyse complémentaire | Comparaison réalisée, avec limites importantes reconnues | Conserver un rôle secondaire ; ne pas la présenter comme effet causal isolé |
| D2 — Analyse par couverture | Pas de nouveau résultat de performance par strate établi dans les passages examinés | Ne pas la rendre obligatoire : D1 constituait déjà l'option complémentaire retenue |
| Confirmation indépendante | Non apportée ; périodes antérieurement consultées | Reporter à une suite distincte, sauf possibilité réelle déjà cadrée |
| E — Intégration scientifique | Nouveau résultat repris dans le résumé, les résultats et la conclusion | Vérifier la cohérence finale et la correspondance FR/EN |
| E/F — Dossier et décision des auteurs | Auteurs, déclarations, cible et format final encore ouverts | Travail prioritaire avant l'envoi |

Sources : M, §3.1, p. 3 ; §4.2, pp. 7–9 ; §6–7 et déclarations, pp. 14–15. S, §S11–S12, pp. 16–22. Les statuts des lots sont une appréciation de cette revue, non des validations signées.

## 4. P0 — Vérifier les pièces qui soutiennent les conclusions centrales

**Responsables proposés :** développeur et second lecteur scientifique. Les cases concernent le prochain contrôle de clôture ; elles ne déclarent pas que les contrôles historiques n'ont jamais été faits.

- [ ] Obtenir le paquet exact correspondant à RC2.1 ; distinguer les fichiers inclus, les entrées externes et les pièces seulement mentionnées. Vérifier versions, inventaire et empreintes.
- [ ] Examiner le protocole C, les métriques de validation, la sélection à trente époques, les résultats annuels et l'index des neuf checkpoints annoncés. Vérifier la correspondance entre commits historiques, commit C et commit D1. [S, §S11.1–S11.2, pp. 17–18.]
- [ ] Contrôler les pièces de l'appariement : 6 370 produit–trimestres, 2 026 produits, 13 174 positifs, 2 775 et 2 530 liens retrouvés. Respecter la distinction entre listes candidates reconstruites et listes historiques complètes non exportées. [S, §S11.3, p. 19.]
- [ ] Rejouer le contraste et son IC à partir des contributions compactes dans un environnement propre, avec une destination nouvelle. Vérifier la graine 20261003, les 1 000 tirages et le regroupement par produit conservant tous ses trimestres. Ce rejeu ne revérifie pas les candidats originaux.
- [ ] Contrôler la correspondance des résultats centraux avec le résumé, les tableaux et la conclusion. Conserver les conventions distinctes d'AP, les périmètres annuels/regroupés et les dénominateurs propres à chaque tâche.
- [ ] Faire consigner par le second lecteur ce qui a été effectivement consulté, rejoué, non accessible ou reporté. Ne pas convertir un audit décrit dans un PDF en audit indépendant réussi.

**Commande de rejeu décrite dans le supplément**, à utiliser uniquement depuis la racine du paquet exact, avec les dépendances requises et une nouvelle destination ; elle n'a pas été exécutée dans cette revue :

```bash
PYTHONPATH=vendor/post_rc1 python \
  scripts/analyze_maude_paired_comparison.py \
  --protocol data/post_rc1/paired_protocol.json \
  --replay-contributions data/post_rc1/paired_contributions.csv \
  --output-dir NEW/maude_paired_replay
```

Le supplément distingue ce rejeu compact du calcul original et indique que les flux complets de scores C/D1 ne sont pas inclus. Documenter ce que permettent les checkpoints et les autres pièces livrées, sans promettre un parcours de reproduction qui n'a pas été vérifié. L'absence des flux complets n'invalide pas à elle seule le rejeu de l'IC. [S, §S11, p. 17 ; §S11.3, p. 19.]

**Livrable proposé :** `verification_cloture.md`, avec commandes, environnement, entrées, tolérances annoncées, résultats des contrôles et limites.

**Critère de fin :** les affirmations centrales conservées sont reliées à des pièces accessibles et cohérentes ; les écarts éventuels sont corrigés ou les affirmations correspondantes restreintes. Il n'est pas nécessaire de réentraîner toutes les méthodes historiques pour comparer des prédictions correctement appariées.

## 5. P0 — Terminer la préparation éditoriale et l'approbation

**Responsables proposés :** auteur correspondant et ensemble des auteurs.

Le supplément précise que la cible éditoriale reste à fixer et que les PDF constituent une maquette de lecture, non un format final validé. Les déclarations et l'approbation scientifique restent également ouvertes. [S, §S12, p. 22 ; M, déclarations, p. 15.]

- [ ] Choisir le support exact et vérifier ses consignes officielles applicables : type d'article, longueur, supplément, disponibilité des artefacts, langue et anonymisation. Ne pas traiter le nom historique du paquet comme une décision éditoriale.
- [ ] Faire approuver le contenu scientifique et bibliographique par les auteurs. Compléter identités, affiliations, correspondant, contributions, financements, conflits d'intérêts, position éthique et conditions d'usage des données. Ne pas présumer « aucun » ou une dispense.
- [ ] Valider la déclaration d'assistance par IA en fonction des usages réels, y compris l'assistance technique aux analyses mentionnée par RC2.1.
- [ ] Contrôler la concordance FR/EN et les renvois entre manuscrit, supplément et fichiers numériques. Compiler et relire les documents au format effectivement demandé.
- [ ] Préparer les pièces requises et vérifier l'accès au paquet associé. Distinguer le DOI du benchmark v0.2 de l'identification du paquet RC2.1 ; ne pas attribuer l'un à l'autre.
- [ ] Recueillir une décision explicite des auteurs sur la version et le support à soumettre. Retirer les mentions de travail non approuvé seulement une fois cette approbation acquise.

**Livrable proposé :** `submission_checklist_RC2_1.md`, accompagné des fichiers validés.

**Critère de fin :** plus aucun champ requis n'est laissé indéterminé ; les auteurs ont approuvé le contenu et la destination ; le paquet requis est accessible. Cette étape prépare une soumission, sans valoir acceptation.

## 6. P1 — Améliorer la lisibilité sans ajouter d'expériences

Ces retouches sont des propositions éditoriales, non des défauts expérimentaux démontrés.

- [ ] Introduire les labels par leur fonction : « exploration de durée (C) » et « diagnostic sans propagation (D1) ». Éviter que le lecteur doive connaître l'historique de développement pour comprendre le résultat.
- [ ] Clarifier « fits indépendants » ou « grille indépendante » par « entraînements séparés, réinitialisés de manière déterministe ». Les documents décrivent une initialisation déterministe ; il ne faut pas laisser entendre qu'il s'agit de répétitions aléatoires indépendantes ou d'une validation externe. [S, §S11.1–S11.2, pp. 17–18.]
- [ ] Rendre explicite « GraphSAGE historique, trois époques » dans les légendes pertinentes. Conserver les résultats historiques sans les confondre avec GraphSAGE30 ni transférer leurs intervalles. [M, figure 1 et tableau 4, p. 8.]
- [ ] Maintenir D1 dans son rôle secondaire. Préserver la présentation conjointe des rappels et des pertes ; ne pas faire de l'écart `mean30–none30` le résultat mécanistique central.
- [ ] Conserver les réserves sur les mesures de ressources sans les développer comme une contribution principale. La divergence de télémétrie de l'audit D1 ne permet pas de certifier son respect du plafond de mémoire ; elle ne démontre pas, à elle seule, une erreur des scores. [S, §S11.5, p. 22.]

**Critère de fin :** un lecteur comprend le résultat principal, les trois niveaux de preuve et le rôle limité de D1 sans devoir reconstruire toute la chronologie des révisions.

## 7. Ce qui ne doit pas relancer automatiquement le projet

**Pas de nouvelle grille de durées par principe.** La grille C répond au diagnostic minimal proposé. Le fait que trente époques soit la borne supérieure ne démontre pas l'optimalité, mais n'oblige pas à chercher une durée toujours meilleure pour cet article exploratoire.

**Pas de réglage illimité de D1.** Une meilleure comparaison peut devenir une étude ultérieure. Elle devient nécessaire avant une affirmation forte sur l'agrégation, pas simplement pour conserver un diagnostic dont les limites sont correctement exposées. Un défaut de code connu affectant les résultats doit néanmoins être corrigé.

**Pas de multiplication des architectures, tâches ou cohortes pour changer de quartile.** L'absence de confirmation indépendante et de budgets comparables reste une limite du périmètre ; davantage de scores sur les mêmes tests ne l'efface pas. [M, §5.2 et §6, pp. 13–14.]

**Confirmation indépendante : branche séparée.** Documenter la faisabilité d'une période réellement non consultée, les choix fixés avant son ouverture et la disponibilité historique des champs. Ne pas supposer qu'une année plus récente suffit, ni différer indéfiniment la présente soumission pour attendre cette branche. [M, §6, p. 14.]

## 8. Calendrier de clôture proposé

Les lots peuvent se chevaucher ; leur calendrier dépend de l'accès aux pièces et de la disponibilité des auteurs. La décision finale ne dépend pas de l'obtention d'un meilleur score.

| Fenêtre indicative | Travail | Sortie attendue |
|---|---|---|
| J1–J2 | Fixer le périmètre, identifier le paquet exact, choisir le support et attribuer les responsabilités | Inventaire d'accès et liste des seuls points bloquants |
| J2–J4 | Vérifier les pièces centrales et effectuer les rejeux ciblés accessibles | Rapport de clôture avec écarts ou concordances documentés |
| J3–J6, en parallèle | Retouches de lisibilité, concordance bilingue, déclarations et format | Manuscrit et supplément finalisés |
| J7–J10 au plus tard dans ce cycle | Relecture des auteurs, contrôle des fichiers et décision | Dossier approuvé pour soumission, ou blocage précis avec correctif et échéance |

## 9. Règle de décision finale

| Situation constatée | Décision proposée |
|---|---|
| Pièces centrales cohérentes, conclusions limitées aux preuves, dossier complet et approuvé | Soumettre au support retenu |
| D1 reste un diagnostic non concluant sur le mécanisme | Soumettre en conservant ce rôle secondaire ; ne pas exiger une explication causale |
| Aucune période indépendante réellement accessible | Conserver le statut exploratoire et reporter la confirmation |
| Une incohérence centrale de code, d'appariement, de dénominateur ou d'interprétation est identifiée | Suspendre l'envoi, corriger le point précis ou retirer l'affirmation invalidée |
| Le paquet ne permet pas d'étayer une affirmation centrale ou un parcours de reproduction promis | Rendre les pièces nécessaires accessibles ou restreindre l'affirmation avant l'envoi |
| Seuls restent le souhait d'un score supérieur ou celui d'une cible plus prestigieuse | Ne pas prolonger ce cycle pour ce seul motif |

### Validation de sortie

- [ ] Les chiffres centraux sont reliés aux bonnes pièces et populations.
- [ ] Les résultats historiques, C et D1 restent clairement distingués.
- [ ] L'IC GraphSAGE30–voisins est explicitement conditionnel, sans couverture de la sélection ni de l'entraînement.
- [ ] D1 n'est pas présenté comme un contrôle efficacement optimisé ou comme une preuve causale.
- [ ] Les limites du paquet et des chemins de reproduction sont exactes.
- [ ] Les auteurs ont approuvé les contenus, les déclarations, le support et les fichiers finaux.

> **Trajectoire actualisée : vérifier les pièces centrales → finaliser le dossier → obtenir l'approbation des auteurs → soumettre. Ne pas recommencer la roadmap RC1 depuis le début.**
