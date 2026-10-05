# RC3.1 — résultats ciblés exploratoires

## Exécution observée

Protocole publié avant les nouveaux fits au commit `dde6a2facf83a493c23ea4797ff5da9e90138452`, PR brouillon [7](https://github.com/carabistouflette/HealthGraphBench/pull/7), dépendante de PR6. SHA256 protocole `faf881cf4a5880f5f444d11badc5ea3a79a08325efb4be394e9c5093137064a8`. CI préfit passée. Run `results/generated/rc31-cycle-20261004/experiment-001` terminé `completed_exploratory` : **75 nouveaux fits, zéro réentraînement BPR historique, 126 phases complètes**, wall CLI9 243,60s. Les57 GraphSAGE passent les gates avec état modifié et réduction minimale de perte probe47,09%. Aucun ancien audit scientifique/gradient réussi relancé.

Les phases représentent6 845 996 551octets, RSS agrégée maximale1 240 743 936octets. Plafonds effectifs respectés; machine partagée, pas benchmark matériel dédié. Temps de réutilisation BPR ≠ coût de ses anciens entraînements. Analyse conservée SHA256 `2a569d2aa0c1a09befa2fbc9fcc2b5f5fe6899e8889798fb6b2bef90cb4a44c8`.

## Part D : gain agrégé et revers conditionnels

Validation2023 : intersection k16, Jaccard/cosinus k50, GraphSAGE d32/L2.0005. Tous les candidats et les2000 prescripteurs, dont981 sans positif2024, sont conservés.

| Procédure | Rappel micro@10 2024 | Étendue entre seeds |
|---|---:|---:|
| Cosinus | .258583 | déterministe |
| Jaccard | .257487 | déterministe |
| BPR réutilisé | .236182 | .231738–.242148 |
| Intersection | .218590 | déterministe |
| Spécialité | .217860 | déterministe |
| Global | .149562 | déterministe |
| GraphSAGE | .145970 | .142075–.150475 |

Cosinus−BPR : **+.022401**, intervalle bootstrap apparié conditionnel **[+.014212;+.030800]**. Cosinus−spécialité+.040723[+.027661;+.053268]; cosinus−global+.109021[+.092979;+.126042]. Jaccard−cosinus−.001096[−.005329;+.002970]. Intersection−cosinus inclut des k sélectionnés différents : pas intervention isolant la normalisation. GraphSAGE−cosinus−.112613[−.130531;−.096307] concerne cette procédure, pas toutes architectures.

Par soutien voisin fixe top50 : cosinus−BPR **+.037752**[+.027685;+.048108] pour3+ soutiens(4300positifs), **−.035263**[−.053292;−.019871] sans soutien(501), **−.032593**[−.048154;−.019724] pour1–2(675). Sur160positifs de candidats historiques≤5 prescripteurs, cosinus retrouve zéro à10, BPR moyen.018750. Les trois groupes de taille d'histoire ont des écarts ponctuels positifs, sans supprimer ces revers. Les méthodes apprises dépassent aussi le vote dans certains groupes faiblement soutenus malgré un classement agrégé défavorable. Toutes les strates sont rapportées.

## MAUDE : structure utile à une étape, complexité non monotone

| Contraste | 2023 | 2024 | 2025 |
|---|---:|---:|---:|
| Vraies8−réassignées8 | +.016007 | +.008884 | +.016502 |
| Fanout16−8 | +.000346 | +.001666 | −.003207 |
| Fanout4−8 | −.002769 | +.001499 | −.004416 |
| BPR lissé−brut | +.007874 | +.003720 | +.011807 |

Vraies8−réassignées8 : intervalles [+.011838;+.020048], [+.002908;+.015055], [+.012123;+.020884]. Réassignation :63,09/62,17/61,63% d'arêtes changées, degrés annuels conservés; labels/probe/négatifs/init/candidats inchangés. Une réalisation bornée, pas null uniforme ni causalité médicale.

Les trois intervalles16−8 incluent zéro et ont une borne supérieure sous.01;4−8en2025 a[−.008257;−.000565]. Tous les niveaux restent rapportés, sans sélectionner le fanout favorable. Lissage−brut : [+.002827;+.012461], [−.001570;+.009519], [+.006591;+.017260]. Même état appris, modification d'inférence; réglage historiquement choisi avec lissage. Pas suppression de toute information relationnelle, ni transfert des résultats GraphSAGE antérieurs réglés séparément.

## CMS : incrément non cohérent, proxy non vérité externe

Même23712lignes préparées/histoires locales/labels que dans les comparaisons antérieures, agrégats recomputés, associations strictement avant inspection. Task demeure déficience conditionnelle à une inspection, pas priorisation nationale.

Logistique combiné−local : +.001939/+.000764/−.000285 ; documenté−local : +.001893/−.000571/−.000685. Les bornes supérieures sont sous le repère analytique.01 dans ces contrastes. Boosting combiné−local : −.007163/+.001867/−.004204 ; documenté−local : −.023589/−.006054/−.003129. Le documenté2023 a[−.037002;−.010218]; les intervalles combinés2023/2024 ne permettent pas d'exclure un gain positif>.01. Pas bénéfice uniforme, pas équivalence clinique générale.

Training compris, proxy :115759/263567 memberships propriétaires cumulés par épisode;512162/1049117pairs cumulés;7287lignes avec propriétaires documentés. Aucune strate « certaines conservées », aucune strate d'évaluation « >3 inspections antérieures » : indéfinies, pas zéro. Le proxy distingue une couverture documentaire, ne prouve pas des erreurs de propriété et n'identifie pas causalement redondance vs qualité des liens.

## Charge, incertitude et gates restantes

PartD cosinus@10 :1416liens/20000slots, précision observable.070800, couverture.337500. À100 : précision.021435, couverture.481000, dix fois plus de slots. MAUDE :11819/12640/13263produit–trimestres, dont8336/9690/9843sans positif; BPR lissé précision globale@10 .014809/.010949/.012946. Absence publiée ≠ erreur clinique; charge de propositions ≠ temps humain ou bénéfice patient.

**336 enregistrements de contraste** :296avec2000tirages valides,40indéfinis avec zéro tirage valide. Bootstrap provider/produit/établissement, seed313, conditionnel aux fits/configurations; étendues de seeds séparées. Pas couverture de sélection, garantie de dépendance de réseau/période ou simultanée. Marge.01 absolue conventionnelle, non clinique. Toutes périodes déjà consultées : résultats exploratoires.

Forecast PartD scellé inchangé; aucun fichier cible PartD2025 acquis ou métrique de cette cible calculée. La capture officielle ne le listait pas à l'instant documenté, pas preuve d'absence universelle. Non-consultation humaine unknown; équipe extérieure, confirmation temporelle et étude d'utilité humaine non réalisées. CMS2026 non certifiée intacte. Auteurs/CRediT/déclarations/éthique/IA/licence/support/approbation demeurent humains. Aucun merge/tag/Zenodo/envoi automatique.
