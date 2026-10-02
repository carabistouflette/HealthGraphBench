# Consolidation post-RC1 — index de pilotage

Les lots **A/B ont démarré techniquement** à la demande d'avancer la roadmap. Les analyses accessibles ont été rejouées et les affirmations centrales reliées à leurs preuves ; les validations humaines, le support éditorial et l'échéance scientifique collective restent à fixer. Les résultats RC1 restent historiques et les nouveaux contrôles ne sont pas une confirmation indépendante.

## Références et preuves

- [Roadmap canonique, lots A–F](../ROADMAP_HealthGraphBench.md) — proposition datée du 2 octobre 2026, quatre semaines relatives au démarrage validé.
- [Gitflow du dépôt](../../CONTRIBUTING.md#gitflow) — branches, PR et flux d'intégration.
- [Inventaire réel des pièces](inventory.csv) — état constaté des fichiers accessibles/manquants et empreintes, à lire avant de décider de la faisabilité.
- [Sommes SHA-256 des copies locales RC1](../../results/SHA256SUMS_manuscript_rc1) — empreintes, distinctes des sorties scientifiques à venir.
- [Décisions et prérequis](scope_and_decisions.md).
- [Matrice des 42 affirmations](claims_evidence.csv) et [audit des chiffres et limites](verification/claims_audit.md).
- [Rejeux réellement exécutés](verification/core_replays.md) et [contrôles temporels accessibles](verification/temporal_controls.md).
- [Protocole GraphSAGE MAUDE](experiment_protocol.md) et [faisabilité calculée des entrées](verification/maude_diagnostic_feasibility.md) — aucun nouveau modèle entraîné.
- [Journal de l'évolution des preuves](scientific_changes.md).
- [Manifeste compact de vérification](../../results/consolidation_core_verification_20261002.json).
- [Empreintes des nouvelles preuves](../../results/SHA256SUMS_consolidation_20261002) — contrôle depuis la racine par `sha256sum -c results/SHA256SUMS_consolidation_20261002` ; les journaux locaux ne sont pas présents dans un clone neuf.
- [Checklist E/F](submission_checklist.md) — preuves techniques disponibles, approbations et soumission non validées.

Branche active de cet incrément : `feature/post-rc1-verification`. Sorties nouvelles isolées dans `results/generated/consolidation-post-RC1/core-verification-20261002/` ; aucun commit, push ou tag créé.

## État des lots

S1–S4 restent relatifs à la date scientifique validée par les responsables. Les rôles scientifiques ci-dessous ne sont pas signés ; les responsabilités techniques des deux subagents et de l'intégration sont consignées dans le journal.

| Lot / fenêtre | Priorité | Rôles proposés, non attribués | État réel dans ce cycle | Dépendances, livrables futurs et critère de fin |
|---|---|---|---|---|
| **A — Cadrage et accès**, début S1 | P0 | Référent scientifique + développeur | RC1 conservée, entrées accessibles, environnement propre et budget opérationnel B établis ; responsabilités scientifiques, calendrier collectif et support éditorial non validés. | Inventaire enrichi et journal technique disponibles. Le cadrage complet reste ouvert jusqu'à attribution/accord des responsables, accès et plafond scientifique explicites. |
| **B — Vérification des résultats centraux**, fin S1 | P0 | Développeur + second lecteur | **Rejeux et audit automatisé terminés** : 10/10 contrôles de rejeu, 609/609 contrôles arithmétiques/manifeste, 66 valeurs-source concordantes, matrice de 42 affirmations. | Preuves et limites consignées ; second lecteur humain et disponibilité publique historique des champs restent à vérifier. Aucune incohérence centrale non expliquée détectée dans le périmètre contrôlé ; B n'est pas signé comme clos. |
| **C — Diagnostic GraphSAGE sur MAUDE**, S2 | P1 | Développeur + validation scientifique | **Protocole daté et entrées caractérisées** ; aucun entraînement, score ou choix de durée nouveau. | Graphe/validation disponibles ; instrumentation des pertes/checkpoints et limites effectives nécessaires avant exécution de 0/3/10/30. Le contrôle synthétique ne remplace pas MAUDE ; C n'est pas clos. |
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