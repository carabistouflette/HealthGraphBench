# Consolidation post-RC1 — index de pilotage

Les lots **A/B ont été vérifiés techniquement et C est désormais exécuté**. Les rejeux de sorties conservées A/B et le nouvel entraînement GraphSAGE C depuis les instantanés préparés sont distincts. Responsabilités et validations humaines, support éditorial et échéance scientifique collective restent à fixer. Les périodes 2023–2025 étaient déjà consultées : aucune confirmation indépendante ni achèvement du cycle de quatre semaines n'est revendiqué.

## Références et preuves

- [Roadmap canonique, lots A–F](../ROADMAP_HealthGraphBench.md) — proposition datée du 2 octobre 2026, quatre semaines relatives au démarrage validé.
- [Gitflow du dépôt](../../CONTRIBUTING.md#gitflow) — branches, PR et flux d'intégration.
- [Inventaire réel des pièces](inventory.csv) — état constaté des fichiers accessibles/manquants et empreintes, à lire avant de décider de la faisabilité.
- [Sommes SHA-256 des copies locales RC1](../../results/SHA256SUMS_manuscript_rc1) — empreintes, distinctes des sorties scientifiques à venir.
- [Décisions et prérequis](scope_and_decisions.md).
- [Matrice des 55 affirmations](claims_evidence.csv) — 42 historiques A/B, 6 nouvelles C et 7 D1 — et [audit initial des chiffres et limites](verification/claims_audit.md).
- [Rejeux réellement exécutés](verification/core_replays.md) et [contrôles temporels accessibles](verification/temporal_controls.md).
- [Protocole GraphSAGE MAUDE](experiment_protocol.md), [faisabilité avant entraînement](verification/maude_diagnostic_feasibility.md) et [rapport avec courbes C réellement exécuté](verification/maude_duration_diagnostic.md).
- [Protocole D1 avec/sans agrégation](aggregation_protocol.md) et [rapport/courbes exécutés](verification/maude_aggregation_ablation.md) — unique P2 techniquement close à durée commune 30 ; témoin C réutilisé. D2 reste exclue.
- [Prévol D1](../../results/maude_aggregation_preflight_20261002.json) — 364 scores `mean` exactement égaux à RC1, reconstruction des checkpoints et gradients `none` contrôlés ; moniteur indisponible → incomplet, sans fit de santé ni verrouillage. Suite initiale 60/60, puis 6/6 tests ciblés après correction du runner.
- [Journal de l'évolution des preuves](scientific_changes.md).
- [Manifeste compact de vérification](../../results/consolidation_core_verification_20261002.json).
- [Empreintes des nouvelles preuves](../../results/SHA256SUMS_consolidation_20261002) — contrôle depuis la racine par `sha256sum -c results/SHA256SUMS_consolidation_20261002` ; les journaux locaux ne sont pas présents dans un clone neuf.
- [Manifeste compact C](../../results/maude_duration_diagnostic_20261002T172405Z.json), [pertes et mesures CSV](../../results/maude_duration_epochs_20261002T172405Z.csv) et [empreintes C distinctes](../../results/SHA256SUMS_maude_duration_20261002T172405Z) **au commit `5eb82ba`** ; les documents de pilotage évoluent ensuite pour D1, sans réécriture des manifestes/empreintes C ou A/B. Contrôler les empreintes documentaires C dans leur révision correspondante, pas les re-pinner au nouvel état.
- [Manifeste compact D1](../../results/maude_aggregation_ablation_20261002T205122Z.json), [CSV des pertes/métriques](../../results/maude_aggregation_epochs_20261002T205122Z.csv) et [empreintes D1 distinctes](../../results/SHA256SUMS_maude_aggregation_20261002T205122Z) ; 180 époques observées (90 C conservées + 90 D1 nouvelles). Les gros exports locaux ne sont pas inclus dans un clone neuf.
- [Checklist E/F](submission_checklist.md) — preuves techniques disponibles, approbations et soumission non validées.

La consolidation A/B est publiée sous `e7cc8a6` sur `feature/post-rc1-verification`, avec la [PR #1 en brouillon vers `develop`](https://github.com/carabistouflette/HealthGraphBench/pull/1). Le code C a été commité avant entraînement sous `4a22c2a` sur `feature/maude-duration-diagnostic`, [PR #2 en brouillon](https://github.com/carabistouflette/HealthGraphBench/pull/2), dépendante de #1. Aucune fusion de livraison ni nouveau tag. Les sorties A/B et C restent dans des runs distincts et ne remplacent pas RC1.

D1 : code/protocole/prévol publiés avant santé sous `b14d878`, [PR #3 en brouillon](https://github.com/carabistouflette/HealthGraphBench/pull/3) vers `develop`, dépendante de #2 ; CI initiale réussie en 18 s. Cette CI est technique, pas une revue scientifique. Les preuves finales D1 sont un lot distinct, sans fusion de livraison.

## État des lots

S1–S4 restent relatifs à la date scientifique validée par les responsables. Les rôles scientifiques ci-dessous ne sont pas signés ; les responsabilités techniques des deux subagents et de l'intégration sont consignées dans le journal.

| Lot / fenêtre | Priorité | Rôles proposés, non attribués | État réel dans ce cycle | Dépendances, livrables futurs et critère de fin |
|---|---|---|---|---|
| **A — Cadrage et accès**, début S1 | P0 | Référent scientifique + développeur | RC1 conservée, entrées accessibles, environnement propre et budget opérationnel B établis ; responsabilités scientifiques, calendrier collectif et support éditorial non validés. | Inventaire enrichi et journal technique disponibles. Le cadrage complet reste ouvert jusqu'à attribution/accord des responsables, accès et plafond scientifique explicites. |
| **B — Vérification des résultats centraux**, fin S1 | P0 | Développeur + second lecteur | **Rejeux et audit automatisé terminés** : 10/10 contrôles de rejeu, 609/609 contrôles arithmétiques/manifeste, 66 valeurs-source concordantes, matrice de 42 affirmations. | Preuves et limites consignées ; second lecteur humain et disponibilité publique historique des champs restent à vérifier. Aucune incohérence centrale non expliquée détectée dans le périmètre contrôlé ; B n'est pas signé comme clos. |
| **C — Diagnostic GraphSAGE sur MAUDE**, S2 | P1 | Développeur + validation scientifique | **Techniquement clos** : grille indépendante 0/3/10/30, sélection de 30 avant tests 2024 puis 2025 ; R@10 groupé **0,210642**. | Rapport/courbes et 9 449 508 prédictions audités depuis six checkpoints, aucun écart à 1e-12. Interprétation intégrée à RC2, sans requalifier les tests en confirmation ; revue humaine distincte. |
| **D — Une analyse complémentaire au maximum**, début S3 | P2 | Référent scientifique + développeur | **D1 techniquement close**, D2 exclue : `mean30` C conservé **0,210642**, nouveau `none30` **0,035600**, contraste **+0,175042** en R@10 groupé. | 4 593 744 nouveaux scores audités exhaustivement, aucun écart à 1e-12 ; graphes/candidats/labels appariés, 30 fixé avant les nouveaux tests. Les trois phases sous 900 s / 512 MiB RSS / 512 MiB sorties. Réserve RSS propre à l'audit post-hoc documentée ; capacité 128→64 et perte `none` proche de ln(2), pas effet causal pur ou confirmation. |
| **E — Intégration et finalisation**, S3–S4 | P0 | Auteurs + auteur correspondant | **RC2.1 documentaire livrée après avis reçu favorable** : légende figure 2 et carte des preuves S2 corrigées, version distincte ; cinq PDF recompilés, pages ciblées examinées, 706 contrôles du paquet. | [Manifeste RC2.1](../../results/manuscript_rc2_1_20261003.json), 537 empreintes ; 27 paires couvertes par concordance antérieure et delta (4 modifiées, 23 conservées). RC2 auditée conservée, aucune analyse relancée. Nouvelle review et approbations auteurs/déclarations/revue ouvertes : E n'est pas clos humainement. |
| **F — Décision et arrêt**, fin S4 | P0 | Ensemble des auteurs | Non démarré ; aucune décision de soumission prise. | Dépend de E et de l'examen explicite des P0/anomalies/limites. Livrable futur : décision datée « soumettre », « restreindre le périmètre » ou « corriger un blocage ». Les auteurs décident ; aucune garantie d'acceptation. |

### Garde-fous

- P0 prime ; P1 est le diagnostic GraphSAGE borné. **Au plus une P2** (D1 ou D2), sans sacrifier les P0.
- La confirmation sur une origine réellement non consultée est une branche distincte : faisabilité à examiner en S1, avant d'ouvrir une telle origine. Les anciens tests, déjà consultés pendant le développement, ne deviennent pas une confirmation indépendante en les relançant.
- Le résultat synthétique de GraphSAGE motive une question ; il ne prouve rien sur MAUDE. Des sorties rejouées ne sont pas un nouvel entraînement. Toute exploration de périodes déjà consultées reste explicitement exploratoire.
- Arrêt : ne pas prolonger le cycle pour viser un meilleur score ou un quartile supérieur. Une limite assumée peut rester ; une contradiction centrale non résolue impose correction ou retrait des affirmations concernées.

## Où vont les fichiers

- **Destinés au versionnement dans Git :** roadmap et documents de pilotage de ce dossier ; petits manifestes, CSV et empreintes. Les trois audits `docs/manuscript_audit_fr*.md` restent dans leur emplacement actuel et ne sont ni déplacés ni réécrits par cette consolidation.
- **Sources RC2 versionnées :** `manuscript/rc2/overlay/` conserve les fichiers LaTeX révisés et ajouts compacts, sans recopier les données historiques ni les gros checkpoints dans Git. `scripts/build_manuscript_rc2.py` assemble depuis le ZIP RC1 attesté et les neuf checkpoints locaux indexés ; un clone seul ne fournit pas ces entrées.
- **Copies et calculs locaux ignorés :** copies en lecture seule du paquet manuscrit dans `results/generated/manuscript-rc1/` ; chaque nouvelle exécution, uniquement si autorisée et réellement faite, dans `results/generated/consolidation-post-RC1/<run-id>/`. Les données brutes restent externes. Les sources locales d'origine ne sont jamais déplacées ni modifiées.
- **Archives publiées :** versions et assets publiés demeurent immuables ; une correction passe par une nouvelle version avec provenance. Le benchmark **v0.2.0** et son DOI ne sont pas le paquet manuscrit **RC1** ; aucun tag RC1 ni DOI de benchmark pour le manuscrit n'est créé ou revendiqué ici.

Le détail des décisions déjà prises et de ce qu'il reste à obtenir figure dans [scope_and_decisions.md](scope_and_decisions.md).

## Prévol du diagnostic C

Le [manifeste prévol](../../results/maude_graphsage_preflight_20261002.json) conserve les 53 tests, la comparaison au noyau RC1 et les empreintes du code/protocole avant nouvel entraînement. Les représentations et les **364 scores de paires** sont identiques au chemin historique sur les fixtures non médicales, callbacks activés ou non ; le checkpoint reconstruit l'inférence depuis les paramètres bruts.

La CLI réelle est [`scripts/run_maude_duration_diagnostic.py`](../../scripts/run_maude_duration_diagnostic.py). Elle exige une destination neuve et l'empreinte exacte du protocole. Les pertes BPR avant mise à jour, l'état final et les candidats/rangs/labels sont persistés ; contrôleur + worker appliquent les plafonds. Si la télémétrie RSS requise est inaccessible, le worker n'est pas lancé et le run est consigné incomplet, sans sélection ni passage test.

## Résultat observé du diagnostic C

Run `maude-duration-20261002T172405Z`, code `4a22c2addc8203efd2b38a60c416270855c3bf3b`, protocole antérieur SHA-256 `69cda4bbd4cd86c3ebbe2346346e2a6292ef69a89699d92e1b628bc504fcb94a`. Le snapshot exact du protocole reste en lecture seule dans le run et accessible dans l'historique Git ; le document canonique a seulement actualisé son statut après exécution.

| Durée | Micro R@10 validation 2023 | Rôle |
|---:|---:|---|
| 0 | 0,022193 | Témoin d'initialisation exclu de la sélection |
| 3 | 0,171577 | Fit indépendant |
| 10 | 0,166905 | Fit indépendant |
| 30 | **0,205062** | Sélectionné à 17:32:26 UTC, avant les tests |

Test 2024 : `1 206 / 6 003 = 0,200900` ; 2025 : `1 569 / 7 171 = 0,218798` ; ensemble : **`2 775 / 13 174 = 0,210642`**, 6 370 observations positives. La valeur historique GraphSAGE à trois époques `0,172840` ne caractérise pas toutes les durées ; voisins historiques `0,192045`, non réentraînés par C. C initial n'avait pas de nouvel IC. Le [rapprochement distinct autorisé le 3 octobre](../../results/maude_C30_neighbors_paired_20261003.json) ajoute un IC conditionnel C30–voisins, sans confirmation indépendante, convergence/optimalité, effet causal ou budgets égaux.

Le [rapport et les courbes C](verification/maude_duration_diagnostic.md) rendent les pertes réellement observées et les limites visibles. Les checkpoints et millions de scores/rangs/labels sont locaux et ignorés ; seuls les petits résumés, CSV et figures sont versionnés. D1 est l'unique P2 techniquement close ; A/B humains et E/F restent ouverts.

## Résultat observé D1 et arrêt des P2

À durée commune 30 : validation `mean/none = 0,205062/0,031149` ; tests groupés **`2 775/13 174 = 0,210642` contre `469/13 174 = 0,035600`**, soit **+0,175042** (`mean30 − none30`). Le témoin n'a pas été réentraîné. Les pertes `none` restent proches de ln(2) ; les paramètres communs ne sont pas retunés après ce résultat. Transformations actives 128 contre 64, mêmes vecteurs d'identité entraînables ; portée limitée à ces variantes.

L'audit numérique détecte zéro écart sur les 4 593 744 scores nouveaux et leurs cohortes appariées. Ses lectures RSS finales discordent (`VmHWM` 118 292 480 octets, `ru_maxrss` 571 580 416) ; aucune certification globale de son RSS sous 512 MiB ni cause certaine n'est revendiquée. Les limites des trois phases scientifiques restent séparément observées. [Rapport complet et réserve](verification/maude_aggregation_ablation.md).

**Arrêt de campagne : aucune D2, nouveau tuning, fit ou graine d'entraînement.** Seul le nouvel IC C30–voisins est explicitement autorisé le 3 octobre, hors D1 ; les résultats restent exploratoires. A/B humains, auteurs/déclarations/support et décision F restent ouverts ; ni D1 ni C ne clôt le cycle de quatre semaines.

## Consolidation ciblée du 3 octobre 2026

C principal, D1 secondaire conservé en S11 ; durée non monotone et absence de preuve causale explicites. Français canonique révisé puis traduit, supplément ouvert sur méthodes/carte des preuves. Nouvel écart apparié +0,018597, IC95 conditionnel [ +0,011975 ; +0,025570 ], 1 000 tirages avec remise des 2 026 produits, graine 20261003. Sélection/entraînement et toutes les dépendances réseau non couverts ; limites des candidats historiques exportés déclarées.

Livraison distincte `_RC2_consolidation_MAUDE.zip` : 694 contrôles, 525 empreintes, 526 membres ZIP ; CRC/identité binaire contrôlés. Rejeu compact exact hors dépôt, 64 tests ; cinq PDF compilés, quatre scientifiques examinés. [Manifeste](../../results/manuscript_rc2_consolidation_20261003.json). Aucun fit/tuning/D2 ou audit historique réussi relancé ; approbations ouvertes.

## RC2.1 documentaire après avis reçu

Rapport externe transmis favorable au positionnement exploratoire, sous deux corrections désormais appliquées : légende du rappel de validation, pertes en S11 ; bibliographie commune vers S2. RC2.1 demandée par l'utilisateur. [Livraison distincte](../../results/manuscript_rc2_1_20261003.json) : 706 contrôles, 537 empreintes, 538 membres ZIP ; cinq PDF recompilés à paginations inchangées. Aucun nouveau fit/score/tuning/bootstrap/D2 ni audit acquis relancé. Original bibliographique archivé à empreinte inchangée ; 105 autres chemins protégés inchangés. Avis reçu, exécutions amont et vérifications de cette passe sont distingués ; nouvelle review et gates de soumission ouverts.

## État de clôture RC2.1 — 3 octobre 2026

La [roadmap utilisateur RC2.1](../ROADMAP_HealthGraphBench_RC2_1.md) remplace l'élan de campagne par une clôture bornée vers soumission : fenêtre indicative de 5 à 10 jours ouvrés après accès aux pièces et disponibilité des auteurs, sans garantie de délai et sans recommencer RC1. La roadmap RC1 de quatre semaines et les journaux antérieurs restent conservés tels qu'ils étaient datés.

La livraison RC2.1 demeure une révision documentaire non soumise et non approuvée. Son [manifeste de livraison](../../results/manuscript_rc2_1_20261003.json) consigne 706 contrôles, 537 entrées d'empreintes et 538 membres ; aucun contrôle, rejeu, calcul ou compilation n'est relancé pour cette mise à jour de pilotage. La [matrice de clôture](verification_cloture.md) attribue chaque preuve déjà exécutée et expose ce que le paquet n'inclut pas. Le [guichet auteur RC2.1](submission_checklist_RC2_1.md) réunit les informations et décisions restant à fournir.

Retouches RC2.2 appliquées : « entraînements séparés, réinitialisés de manière déterministe », GraphSAGE historique à trois époques distinct de GraphSAGE30. C reste principal, D1 secondaire et les résultats inchangés. **D2 et un nouveau réglage de `none30` ne sont pas des prérequis**. Statut éditorial : prêt pour relecture/maquette de lecture, approbations des auteurs, support et déclarations encore ouverts ; aucun format final de revue n'est revendiqué.

## RC2.2 — clôture éditoriale techniquement vérifiée

Cinq PDF compilés (17/16/23/22/2 pages), treize pages ciblées et quatre figures bilingues examinées. Sept paires de sources modifiées et vingt conservées ; 82 fichiers scientifiques byte-identiques à RC2.1, deux titres C précisés, figures historiques conservées et dérivés `historical3` identifiés. Aucun nouveau fit, score, bootstrap ou audit scientifique réussi. [Matrice et preuves](verification_cloture.md) ; [guichet auteurs](submission_checklist_RC2_1.md). Archive distincte `HealthGraphBench_FAIA_LaTeX_RC2_2_cloture.zip` ; manifeste `results/manuscript_rc2_2_20261003.json`. PR #4 reste brouillon vers `develop`, dépendante de #3 ; aucune fusion, aucun tag ou dépôt Zenodo.

