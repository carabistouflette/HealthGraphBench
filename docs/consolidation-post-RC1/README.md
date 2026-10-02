# Consolidation post-RC1 — index de pilotage

Les lots **A/B ont été vérifiés techniquement et C est désormais exécuté**. Les rejeux de sorties conservées A/B et le nouvel entraînement GraphSAGE C depuis les instantanés préparés sont distincts. Responsabilités et validations humaines, support éditorial et échéance scientifique collective restent à fixer. Les périodes 2023–2025 étaient déjà consultées : aucune confirmation indépendante ni achèvement du cycle de quatre semaines n'est revendiqué.

## Références et preuves

- [Roadmap canonique, lots A–F](../ROADMAP_HealthGraphBench.md) — proposition datée du 2 octobre 2026, quatre semaines relatives au démarrage validé.
- [Gitflow du dépôt](../../CONTRIBUTING.md#gitflow) — branches, PR et flux d'intégration.
- [Inventaire réel des pièces](inventory.csv) — état constaté des fichiers accessibles/manquants et empreintes, à lire avant de décider de la faisabilité.
- [Sommes SHA-256 des copies locales RC1](../../results/SHA256SUMS_manuscript_rc1) — empreintes, distinctes des sorties scientifiques à venir.
- [Décisions et prérequis](scope_and_decisions.md).
- [Matrice des 48 affirmations](claims_evidence.csv) — 42 historiques A/B et 6 nouvelles C — et [audit initial des chiffres et limites](verification/claims_audit.md).
- [Rejeux réellement exécutés](verification/core_replays.md) et [contrôles temporels accessibles](verification/temporal_controls.md).
- [Protocole GraphSAGE MAUDE](experiment_protocol.md), [faisabilité avant entraînement](verification/maude_diagnostic_feasibility.md) et [rapport avec courbes C réellement exécuté](verification/maude_duration_diagnostic.md).
- [Journal de l'évolution des preuves](scientific_changes.md).
- [Manifeste compact de vérification](../../results/consolidation_core_verification_20261002.json).
- [Empreintes des nouvelles preuves](../../results/SHA256SUMS_consolidation_20261002) — contrôle depuis la racine par `sha256sum -c results/SHA256SUMS_consolidation_20261002` ; les journaux locaux ne sont pas présents dans un clone neuf.
- [Manifeste compact C](../../results/maude_duration_diagnostic_20261002T172405Z.json), [pertes et mesures CSV](../../results/maude_duration_epochs_20261002T172405Z.csv) et [empreintes C distinctes](../../results/SHA256SUMS_maude_duration_20261002T172405Z) ; les manifestes/empreintes A/B ne sont pas réécrits par le nouvel entraînement.
- [Checklist E/F](submission_checklist.md) — preuves techniques disponibles, approbations et soumission non validées.

La consolidation A/B est publiée sous `e7cc8a6` sur `feature/post-rc1-verification`, avec la [PR #1 en brouillon vers `develop`](https://github.com/carabistouflette/HealthGraphBench/pull/1). Le code C a été commité avant entraînement sous `4a22c2a` sur `feature/maude-duration-diagnostic`, [PR #2 en brouillon](https://github.com/carabistouflette/HealthGraphBench/pull/2), dépendante de #1. Aucune fusion de livraison ni nouveau tag. Les sorties A/B et C restent dans des runs distincts et ne remplacent pas RC1.

## État des lots

S1–S4 restent relatifs à la date scientifique validée par les responsables. Les rôles scientifiques ci-dessous ne sont pas signés ; les responsabilités techniques des deux subagents et de l'intégration sont consignées dans le journal.

| Lot / fenêtre | Priorité | Rôles proposés, non attribués | État réel dans ce cycle | Dépendances, livrables futurs et critère de fin |
|---|---|---|---|---|
| **A — Cadrage et accès**, début S1 | P0 | Référent scientifique + développeur | RC1 conservée, entrées accessibles, environnement propre et budget opérationnel B établis ; responsabilités scientifiques, calendrier collectif et support éditorial non validés. | Inventaire enrichi et journal technique disponibles. Le cadrage complet reste ouvert jusqu'à attribution/accord des responsables, accès et plafond scientifique explicites. |
| **B — Vérification des résultats centraux**, fin S1 | P0 | Développeur + second lecteur | **Rejeux et audit automatisé terminés** : 10/10 contrôles de rejeu, 609/609 contrôles arithmétiques/manifeste, 66 valeurs-source concordantes, matrice de 42 affirmations. | Preuves et limites consignées ; second lecteur humain et disponibilité publique historique des champs restent à vérifier. Aucune incohérence centrale non expliquée détectée dans le périmètre contrôlé ; B n'est pas signé comme clos. |
| **C — Diagnostic GraphSAGE sur MAUDE**, S2 | P1 | Développeur + validation scientifique | **Techniquement clos** : grille indépendante 0/3/10/30, sélection de 30 avant tests 2024 puis 2025 ; R@10 groupé **0,210642**. Les 53 tests et le prévol d'équivalence précèdent cet entraînement. | Rapport/courbes examinés ; 9 449 508 prédictions auditées depuis les six checkpoints, aucun écart à 1e-12 ; chaque phase sous 900 s / 512 MiB RSS / 512 MiB sorties. Revue humaine distincte ; checkpoints d'inférence, sans reprise. Message à intégrer en E sans requalifier les tests en confirmation. |
| **D — Une analyse complémentaire au maximum**, début S3 | P2 | Référent scientifique + développeur | Non démarré ; aucune option engagée. | Plafond d'une seule analyse : D1 avec/sans agrégation si la chaîne de C est fiable, **ou** D2 performances/couverture si les sorties s'apparient. Dépend du choix explicite et des ressources de A ; ne pas faire les deux. Livrable futur : comparaison contrôlée ou report motivé, interprété uniquement dans son périmètre. |
| **E — Intégration et finalisation**, S3–S4 | P0 | Auteurs + auteur correspondant | Non démarré ; manuscrit et dossier ne sont pas marqués prêts. | Dépend des preuves réellement obtenues, du support retenu et des validations des auteurs. Futurs livrables : manuscrit/supplément concordants et paquet vérifié. Clos quand le lecteur distingue exécuté/reproductible/non vérifié, et que les auteurs ont approuvé le dossier. |
| **F — Décision et arrêt**, fin S4 | P0 | Ensemble des auteurs | Non démarré ; aucune décision de soumission prise. | Dépend de E et de l'examen explicite des P0/anomalies/limites. Livrable futur : décision datée « soumettre », « restreindre le périmètre » ou « corriger un blocage ». Les auteurs décident ; aucune garantie d'acceptation. |

### Garde-fous

- P0 prime ; P1 est le diagnostic GraphSAGE borné. **Au plus une P2** (D1 ou D2), sans sacrifier les P0.
- La confirmation sur une origine réellement non consultée est une branche distincte : faisabilité à examiner en S1, avant d'ouvrir une telle origine. Les anciens tests, déjà consultés pendant le développement, ne deviennent pas une confirmation indépendante en les relançant.
- Le résultat synthétique de GraphSAGE motive une question ; il ne prouve rien sur MAUDE. Des sorties rejouées ne sont pas un nouvel entraînement. Toute exploration de périodes déjà consultées reste explicitement exploratoire.
- Arrêt : ne pas prolonger le cycle pour viser un meilleur score ou un quartile supérieur. Une limite assumée peut rester ; une contradiction centrale non résolue impose correction ou retrait des affirmations concernées.

## Où vont les fichiers

- **Destinés au versionnement dans Git :** roadmap et documents de pilotage de ce dossier ; petits manifestes, CSV et empreintes. Les trois audits `docs/manuscript_audit_fr*.md` restent dans leur emplacement actuel et ne sont ni déplacés ni réécrits par cette consolidation.
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

Test 2024 : `1 206 / 6 003 = 0,200900` ; 2025 : `1 569 / 7 171 = 0,218798` ; ensemble : **`2 775 / 13 174 = 0,210642`**, 6 370 observations positives. La valeur historique GraphSAGE à trois époques `0,172840` ne caractérise donc pas toutes les durées ; les voisins historiques restent `0,192045`. Les références historiques ne sont pas réentraînées en test par C. Écarts descriptifs seulement, sans nouvel IC, convergence/optimalité, effet causal de l'agrégation ou budgets égaux.

Le [rapport et les courbes](verification/maude_duration_diagnostic.md) rendent les pertes réellement observées et les limites visibles. Les checkpoints et millions de scores/rangs/labels sont locaux et ignorés ; seuls les petits résumés, le CSV et les figures sont versionnés. Aucune P2 engagée ; A/B humains et E/F restent ouverts.