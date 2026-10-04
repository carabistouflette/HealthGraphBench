# RC3.1 — expériences ciblées sur l'information relationnelle

## Décision et question

Après la clôture documentaire RC3, l'utilisateur a explicitement choisi **de nouvelles expériences ciblées avant RC3.1**. Cela ouvre un cycle distinct, pas une modification des preuves RC3 ni une recherche générale du meilleur modèle. RC3, Q2, C/D1, les anciens ZIP, checkpoints, ledgers, environnements et les quatre documents utilisateur restent immuables. D2/ClinicalTrials restent hors périmètre.

**Dans quelles situations les relations apportent-elles une information prédictive supplémentaire à l'historique individuel et à la popularité, et quelle complexité faut-il pour l'exploiter ?**

Trois objets restent séparés : comparaison de procédures raisonnablement réglées; interventions isolant une étape ou un facteur; confirmation sur une cible réellement non consultée. Les nouveaux résultats sur 2023–25 demeurent exploratoires : verrouiller les nouveaux calculs n'efface pas la consultation antérieure des cibles.

## Verrou et plafonds

Protocole exécutable : `configs/rc31_relational_protocol_20261004.json`. Sources, protocole et prévol synthétique doivent être committés et publiés **avant tout nouveau fit ou score médical**. Le runner consomme le SHA256 exact, refuse les sources scientifiques non committées et crée exclusivement un nouveau root. Les erreurs et phases incomplètes restent conservées; aucune sélection sur une grille incomplète.

Seuils effectifs via le superviseur Linux existant : **1 800 s par phase**, **4 GiB RSS agrégée contrôleur + worker**, **1 GiB de fichiers par phase**, **3 600 s de validation par famille**, **21 600 s par run**, **8 GiB de sorties par run**. Un thread numérique; machine partagée. Coûts mesurés, jamais coûts supposés égaux. Environnement numérique distinct `results/generated/rc31-cycle-20261004/env`, NumPy2.3.5/scikit-learn1.8.0/Numba0.68.0; versions effectivement installées conservées.

Les fits stochastiques utilisent **103/211/307**, tous rapportés, jamais un seed choisi. Un seul fit/état pour les méthodes déterministes. Les nouveaux GraphSAGE doivent modifier l'état persistant et réduire d'au moins1% la perte de données d'un probe historique fixe; gates et erreurs ne sont pas remplacées par des scores zéro. Les preuves historiques de gradients du backend inchangé sont réutilisées, pas recontrôlées pour confirmer leurs anciens succès.

## Part D : comparaison commune

Préparation raw Q2 conservée et déclarée comme **entrée préparée vérifiée**, non nouvelle acquisition raw; validation2023 avec2019–22, test2024 avec2019–23. Même cohorte2000, identité generic name trim exact, candidats globaux historiques hors toute l'histoire du provider, ranking/ties et positifs observables. Aucun échantillonnage de candidats d'évaluation. Tous les provider–années, y compris sans positif, sont retenus.

| Procédure | Réglages avant test |
|---|---|
| Voisins par fréquence d'intersection | k8/16/32/50/100/200 |
| Voisins Jaccard | même grille k |
| Voisins cosinus | même grille k |
| GraphSAGE mean | d16/32 × L2 .0005/.000005/0;30époques,LR.02,fanout8 |
| BPR | sélection Q2 six configurations, config-05 d32/LR.03/L2.001/5négatifs;30époques,poids spécialité.35; trois sorties conservées réutilisées |
| Popularités globale / spécialité | références fixes, sans tuning |

« Fréquence » signifie **nombre de médicaments distincts partagés**, pas pondération par claims. Incidence binaire; similarités strictement positives; soi exclu; similarité décroissante puisNPI lexical; votes pondérés; voisins choisis une fois par provider, pas selon le candidat. Six opportunités nominales par procédure réglée, **pas même calcul**.

Sélection : moyenne micro Recall@10 validation2023, tous seeds quand pertinents; égalité exacte départagée par l'ordre publié (k croissant pour voisins). Toutes les sélections sont écrites avant scoring2024. Les BPR déjà réussis ne sont pas refittés : leur état/scores sont consommés dans le nouvel univers commun après contrôle de compatibilité exact des historiques, cohortes, candidats et cibles. Le témoin cosinus top50 RC3 n'est pas simplement ajouté au classement; cette campagne effectue sa propre sélection et son scoring sous contrat commun.

Contraste principal : **cosinus sélectionné − BPR sélectionné réutilisé**, micro Recall@10 test2024. Les autres procédures, toutes configurations de validation et différences annoncées sont rapportées. GraphSAGE et BPR diffèrent aussi par objectif, négatifs, initialisation et information auxiliaire de spécialité : ce comparatif n'isole pas l'architecture seule.

## MAUDE : interventions ciblées

Même architecture d16, L2.000005, LR.02,30époques, trois seeds;2023 puis refits pré-cibles2024/25. Quatre niveaux publiés : fanout4/8/16 sur vraies arêtes, fanout8 sur arêtes d'agrégation réassignées. Pas de sélection du meilleur fanout. Contrastes principaux :16−8 et vraies8−réassignées8;4−8 en sensibilité.

Réassignation : doubles échanges bipartites bornés, seed303,10tentatives par arête; conservation de chaque degré, des types de nœuds et de l'univers agrégé **antérieur à l'origine annuelle**. Étiquettes d'entraînement, probe, CSR des négatifs, histoire/candidats/cibles et initialisation restent identiques. Tentatives, échanges acceptés, fraction changée et adjacency complète conservés. Pas de null uniforme, de conservation revendiquée des degrés par trimestre, ni de causalité médicale.

BPR : checkpoints annuels sélectionnés Q2 réutilisés (validation config06, d16/L2=0). Sur **les mêmes représentations apprises**, comparer scores bruts x·y et scores avec .5vecteur propre+.5moyenne fixe des voisins historiques. C'est une intervention sur le **lissage à l'inférence**, conditionnelle à une configuration sélectionnée avec lissage; pas retrait de tout apprentissage relationnel ni comparaison des meilleurs BPR bruts et lissés séparément réglés.

## CMS : histoire locale, agrégats et documentation des liens

La cible demeure une déficience grave **conditionnellement à une inspection Health Standard ayant lieu**, pas la priorisation nationale des établissements à inspecter. Reproduire exactement les23712 épisodes/histoires locales/labels Q2, puis recomputer les seuls agrégats de relations. Même training, mêmes établissements, mêmes lignes d'évaluation; états et scaler appris dans le passé strict.

Trois jeux : histoire locale; histoire+propriétaires combinés; histoire+liens mieux documentés selon un **proxy opérationnel**, non vérité de propriété. Paramètres partagés : logistique C.01/LBFGS1000/tol1e-8, pas class_weight; HGB LR.05/100itérations/15feuilles/L2=1, early_stoppingFalse, max_features1.0, max_bins255, min_samples_leaf20. Aucun tuning selon jeu de variables ou sous-groupe. Fits antérieurs aux cibles2023/24/25; ces training<200000 sont déterministes.

Le proxy conserve les identifiants PAC propriétaires déjà combinés s'ils sont soutenus par un événement CHOW daté qui relie enrollment etCCN, et par une date d'association propriétaire, **tous deux strictement antérieurs à l'inspection**; enrollment doit désigner un seulCCN parmi événements antérieurs. Les deux extrémités d'une relation de pair doivent qualifier. Aucune nouvelle résolution parfaite des noms, date de fin ou vérité externe n'est inventée. La règle des associations combinées devient elle aussi strictement`<` dans ce nouveau cycle, au lieu du`<=` historique; résultats Q2 intacts. Snapshot rétrospectif, fins inconnues et disponibilité publique à l'origine non établie restent des limites. La sensibilité à la représentation ne tranche pas causalement redondance versus erreurs de liens sans vérité de propriété.

## Sous-groupes, incertitude et charge

Groupes **pré-cibles** fixés : PartD≤10/11–50/>50 médicaments historiques; MAUDE1–9/10–49/50–199/200+ reports; fréquence historique du candidat≤5/6–50/>50 providers ou produits; soutien voisin0/1–2/3+. Le stratificateur PartD utilise un cosinus top50 historique fixe indépendamment de la méthode/k sélectionnés. CMS :1/2–3/>3 inspections antérieures; aucune association combinée / aucune conservée / certaines / toutes conservées par le proxy. Tous les groupes, y compris sans dénominateur ou classe suffisants, sont rapportés; indéfini≠zéro.

Étendues entre seeds séparées des intervalles. Bootstrap apparié **2000tirages, seed313**, clusters provider/produit/établissement, toutes périodes d'un cluster ensemble; mêmes tirages pour les procédures. Moyenne des hits par unité entre seeds avant ratio micro. Zéros conservés; ratio recalculé à chaque tirage. Intervalles percentiles95% **conditionnels aux fits et configurations figés**, sans sélection, variation de période, indépendance de réseau ou couverture simultanée garanties; exploratoires, pas confirmation.

Marge fixée **.01 absolu** (1point de rappel/AUC) : repère analytique conventionnel, **pas seuil clinique ni bénéfice certifié par auteurs**. Une borne supérieure sous cette marge exclut seulement ce gain sous les conditions du resampling; elle ne prouve pas seule l'équivalence. Une conclusion globale « les graphes n'aident pas » est exclue.

Charge àK1/5/10/20/50/100 : liens publiés retrouvés, précision parmi slots réellement proposés min(K,candidats), couverture des entité–périodes et fraction sans positif. MAUDE étend explicitement l'univers de charge à **tous produits historiquement connus, support≥1 et candidats non vides**, incluant produit–trimestres sans positif; ce n'est plus une précision conditionnelle aux seuls produits positifs. Le rappel conserve les premiers liens éligibles. Absence dans les fichiers≠erreur clinique. CMS ne change pas de tâche.

## Confirmation et extérieur : gates non substituables

Voir `independence_and_reuse_fr.md` et le contrôle frais `results/rc31_availability_20261004.json`. Aucun nouveau comparateur n'est ajouté rétroactivement au forecast scellé; aucune cible2025 ni métrique indépendante n'est inventée. Nouvelle confirmation : protocole distinct avant consultation d'une vraie cible future, snapshots réellement disponibles à l'origine et attestations/intervention indépendantes réelles. Équipe extérieure : reproduction depuis sources et comparateur ajouté par elle, journaux/écarts/consentement; assistant≠participant humain. Ces prérequis ne sont pas fermés par un runner automatique.

La [comparaison d'Errica et al.](https://arxiv.org/abs/1912.09893) motive des protocoles contrôlés et des références sans structure dans le domaine distinct de la classification de graphes, pas une démonstration des mécanismes médicaux ici. Le manuscrit français sera recentré après résultats réels, puis traduit fidèlement. Chronologie détaillée et contrôles techniques au supplément; différences de protocole et limites interprétatives dans le principal. Support/auteurs/déclarations/approbation/envoi restent humains. Aucun merge/tag/Zenodo/soumission automatique.
