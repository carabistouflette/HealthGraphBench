# Journal scientifique — consolidation post-RC1

## 2 octobre 2026 — vérification A/B et préparation C

**Aucun résultat historique, tableau, PDF ou source du paquet RC1 modifié. Aucun nouvel entraînement de santé, score de prédiction ou test indépendant produit.** Les changements portent sur le niveau de vérification et la traçabilité, pas sur le classement des méthodes.

### Preuves nouvelles

- [Rejeux centraux](verification/core_replays.md) exécutés dans Python 3.13.5 et l'environnement RC1 figé : dix contrôles réussis, 49 champs MAUDE, 91 Part D, deux arbres CMS de 284 champs, cinq artefacts MAUDE B et la synthèse de couverture identiques aux références. Résultats conditionnels aux sorties préparées, pas reconstruction brute.
- [Audit des affirmations](verification/claims_audit.md) : 609/609 contrôles arithmétiques/manifeste ; 66 clés numériques concordantes au résumé canonique, dont deux présentations Part D à six décimales explicites. Aucune incohérence centrale non expliquée détectée dans ce périmètre.
- [Matrice des preuves](claims_evidence.csv) : 42 affirmations avec population, convention, fichier/calcul, résultat et limite. Les résultats GraphSAGE MAUDE historiques, AUC/Brier CMS et contrôles synthétiques ne sont pas présentés comme nouvellement entraînés ou intégralement recalculés.
- Identité locale des sorties originales MAUDE, CMS et des classements Part D confirmée par SHA-256 contre les constantes RC1 ; ce contrôle séparé d'identité ne vérifie pas à lui seul la dérivation des compacts.
- [Frontières temporelles](verification/temporal_controls.md) examinées dans le code. La disponibilité publique historique des champs et les décisions humaines de développement restent à vérifier.
- [Protocole C](experiment_protocol.md) fixé avant nouvel entraînement et [entrées MAUDE](verification/maude_diagnostic_feasibility.md) caractérisées : graphe/validation accessibles ; aucun temps d'entraînement mesuré, aucune perte/checkpoint nouveau, aucune configuration sélectionnée.
- [Manifeste compact](../../results/consolidation_core_verification_20261002.json) et [empreintes nouvelles](../../results/SHA256SUMS_consolidation_20261002) : résultats de vérification finale, environnement et chemins des preuves persistés, distincts du paquet RC1.

### Interprétation à conserver

Les écarts et intervalles historiques restent attachés à leurs populations et métriques. AP de rang et AP par seuils ne sont pas interchangeables ; l'AUC CMS groupée n'est pas la moyenne annuelle ; MAUDE positif-seulement ne permet pas une charge générale ; Part D garde les observations sans positif. Le synthétique ne valide pas MAUDE et les tests déjà consultés restent exploratoires.

La mise en évidence des deux arrondis Part D ne justifie ni remplacement des fichiers historiques ni correction d'une erreur inexistante. Les couvertures sont des présences de clés dans des inventaires reconstruits, pas une inspection des vecteurs appris ni une preuve causale de l'effet d'agrégation.

### Intégration du dossier de preuves

L'inventaire recense 27 artefacts avec tailles et SHA-256 ; la matrice comporte 42 affirmations et 11 colonnes, avec 124 références source résolues. Le contrôle d'intégration porte sur leur lisibilité, les identifiants, les fichiers réellement présents et les liens du pilotage. Son rapport local et les empreintes des documents sont référencés dans le manifeste compact, sans cycle d'empreintes manifeste–inventaire. Ces contrôles n'ajoutent aucune conclusion scientifique ni validation humaine.

### Statut des autres lots

A et B restent ouverts pour validation humaine, disponibilités historiques, responsabilités scientifiques et support éditorial. C n'est pas exécuté : instrumentation des pertes et de l'état appris requise avant lancement du diagnostic. D n'est pas engagé ; D1 et D2 ne seront pas cumulés. Aucun manuscrit RC2, dépôt permanent, déclaration d'auteur finalisée ou décision de soumission n'est revendiqué.

L'assistance par IA dans cet incrément a servi à la coordination technique, aux calculs de vérification et à la rédaction des documents de pilotage ; les auteurs doivent valider leur déclaration d'assistance réelle et leurs responsabilités. Aucun subagent n'est présenté comme un auteur signataire ou un second lecteur humain indépendant.

## 2 octobre 2026 — publication Git et poursuite du minimum C

- Demande explicite de commiter, pousser et continuer : commit A/B `e7cc8a6`, publication de `develop` et `feature/post-rc1-verification`, [PR #1 en brouillon](https://github.com/carabistouflette/HealthGraphBench/pull/1) vers `develop`. CI distante **Gitflow and tests** réussie en 18 s ; aucune approbation scientifique ni fusion de livraison.
- Nouvelle branche `feature/maude-duration-diagnostic`, issue de `develop` avec merge de dépendance A/B. `main`, les tags, les données et les scores historiques restent intacts.
- Travail technique partagé entre `GraphSageTrace` (pertes, état final et reconstruction d'inférence) et `MaudeDurationRunner` (pipeline et arrêt effectif). Le contrôle du chemin historique doit précéder tout nouvel entraînement MAUDE.
- Précision opérationnelle préalable au lancement : contrôleur léger + un seul worker d'apprentissage, RSS agrégée, aucun fit parallèle. Plafonds, grille indépendante, critères et populations inchangés ; pas d'augmentation opportuniste du budget.
- Prévol C achevé : 53 tests passent ; quatre fixtures non médicales comparées au noyau RC1, représentations et 364 scores strictement identiques à trois époques, callbacks activés ou non ; reconstruction de l'inférence depuis les paramètres bruts concordante. La CLI a été exercée. [Provenance prévol](../../results/maude_graphsage_preflight_20261002.json).
- Défaut de surveillance reproduit puis corrigé : une permission `/proc` refusée renvoyait auparavant une fausse RSS nulle. Le nouveau chemin échoue avant lancement du worker ; smoke réel du pipeline avec erreur d'I/O injectée → run/phase incomplets, aucune sélection, aucun enfant restant. Les journaux d'époque absents ne sont plus remplacés par une liste vide. Aucun résultat de santé n'est produit par ces contrôles.
- Implémentation instrumentée commitée avant entraînement sous `4a22c2addc8203efd2b38a60c416270855c3bf3b`, puis poussée sur `feature/maude-duration-diagnostic`. [PR #2 en brouillon vers `develop`](https://github.com/carabistouflette/HealthGraphBench/pull/2) ; check distant **Gitflow and tests** réussi en 19 s. Aucune fusion de livraison.
- Lancement C séparé sous `maude-duration-20261002T172405Z`, avec le protocole SHA-256 `69cda4bbd4cd86c3ebbe2346346e2a6292ef69a89699d92e1b628bc504fcb94a`, avant toute sélection et sans variante des paramètres gelés. Les résultats ne sont pas anticipés par cette entrée.

## 2 octobre 2026 — diagnostic MAUDE C réellement terminé

- Run neuf `maude-duration-20261002T172405Z`, terminé à 17:43:51 UTC, code d'entraînement déjà commité `4a22c2addc8203efd2b38a60c416270855c3bf3b`. Instantanés préparés RC1 utilisés en lecture seule, sans réacquisition FDA ni reconstruction des champs tabulaires absents.
- Grille indépendante 0/3/10/30 complète : micro R@10 validation **0,022193 / 0,171577 / 0,166905 / 0,205062**, sur les mêmes 3 483 observations positives, 7 705 liens et 1 618 588 candidats. Le critère et les hyperparamètres ne changent pas ; zéro reste témoin.
- Sélection **30 époques** verrouillée à 17:32:26.207893 UTC, avant les tests 2024 puis 2025. Test 2024 **1 206 / 6 003 = 0,200900** ; 2025 **1 569 / 7 171 = 0,218798** ; groupé **2 775 / 13 174 = 0,210642**, sur 6 370 observations positives, sans moyenne des rappels annuels.
- Comparaisons descriptives : nouveau30 moins GraphSAGE historique3 **+0,0378017307** ; moins voisins historiques **+0,0185972370**. Les références historiques ne sont ni réentraînées dans C ni remplacées. Aucun nouvel IC, bootstrap, ablation, stratification ou tuning hors protocole.
- Pas observés : **2 910 068** sur la validation et **7 636 508** au total, sans positifs sautés dans les résumés des fits. La perte de données BPR avant mise à jour est séparée de la régularisation ; zéro n'a pas de perte d'optimisation observée. Checkpoints bruts d'inférence, `resume_supported=false`.
- Phases validation/test2024/test2025 : **482,36 / 329,32 / 356,21 s**, RSS agrégée maximale **249 405 440 octets** et sorties de chaque phase sous 512 MiB. Plafonds effectifs inchangés : 900 s / 512 MiB / 512 MiB par phase ; total du run **1 167,91 s**, sans plafond global à 900 s.
- Deux travaux post-exécution indépendants : `DurationNumericAudit` pour les invariants des exports conservés ; `DurationReportCurves` pour le [rapport et les courbes](verification/maude_duration_diagnostic.md). Courbes réellement rendues et surface PNG examinée ; le CSV conserve les mesures, sans point de perte artificiel à zéro.
- Le snapshot exact du protocole exécuté, SHA-256 `69cda4bbd4cd86c3ebbe2346346e2a6292ef69a89699d92e1b628bc504fcb94a`, est préservé en lecture seule dans le run ; sa version est récupérable au commit de code. Le document canonique actualise ensuite son statut, pas les règles du lancement.

**Changement du message à intégrer en E :** la contre-performance historique de GraphSAGE à trois époques ne caractérise pas toutes les durées. Trente est le meilleur point de la grille fixée sur validation, pas un optimum démontré ; dix n'améliore pas trois sur cette validation. Le nouveau point test est supérieur aux deux références citées sans démonstration de significativité, causalité de l'agrégation, robustesse ou budgets égaux.

Le résultat reste exploratoire sur des périodes déjà consultées, conditionnel aux instantanés préparés et à leurs règles de temps/éligibilité. La disponibilité publique historique et la précision/charge générale ne sont pas démontrées. Aucun accord des auteurs, nouvelle RC2, dépôt permanent, DOI, tag, P2 ou soumission n'est créé par cette exécution. A/B humains, responsabilités/support et E/F restent ouverts.

### Audit final des artefacts C

`DurationNumericAudit` a contrôlé intégralement **24 trimestres-fit**, **20 302 listes candidates** et **9 449 508 lignes scores/rangs/labels**, scores recalculés depuis les six checkpoints bruts, sans échantillonnage. Les premières relations et règles d'éligibilité sont dérivées de l'entrée préparée ; 24 tables trimestrielles, six tables de phase et le pool test concordent. Aucun écart détecté ; entiers/listes/hash exacts, flottants à `1e-12`. Audit **71,072 s**, RSS **506 212 352 octets**, sous ses plafonds.

Le contrôle d'ordre s'appuie sur les événements de trace et les dates locales de création des fichiers : verrouillage 17:32:26.207893, trace test2024 créée 17:32:26.211612 UTC. Les lignes de trace n'ont pas d'horodatage absolu ; ce n'est ni une attestation externe ni une preuve de non-exposition antérieure. Le [manifeste C](../../results/maude_duration_diagnostic_20261002T172405Z.json) conserve le périmètre de cette vérification, les empreintes et les limites, sans modifier le manifeste A/B.
