# Périmètre et décisions — consolidation post-RC1

## Statut

État au 2 octobre 2026. L'organisation puis les lots A/B ont été engagés techniquement à la demande de l'utilisateur ; leurs preuves sont consignées ci-dessous. Les semaines S1 à S4 du calendrier scientifique restent liées à un démarrage validé par les responsables. Les contrôles techniques ne valent ni signature d'auteur, ni validation scientifique humaine, ni autorisation de soumission.

## Décisions d'organisation effectivement prises

| Date | Décision constatée | Portée |
|---|---|---|
| 2 octobre 2026 | Importer la roadmap source dans `docs/ROADMAP_HealthGraphBench.md`, sans changer son contenu scientifique, ses quatre semaines, ses lots A–F, ses priorités ni ses garde-fous. | Le plan demeure proposé. Le dépôt ne certifie pas les affirmations scientifiques de la source et l'import ne compte pas comme exécution. |
| 2 octobre 2026 | Créer `develop` depuis le `main` stable `b010d5a49eae56837a920b2e30dece41c42c0c44`, puis isoler les travaux nouveaux sur `chore/consolidation-post-rc1`. | Références locales créées ; aucun commit, push, tag ou publication. Respecter [Gitflow](../../CONTRIBUTING.md#gitflow) pour les intégrations. |
| 2 octobre 2026 | Séparer strictement le paquet manuscrit RC1 du benchmark HealthGraphBench v0.2.0. | Ne pas créer de tag RC1, transférer au manuscrit le DOI du benchmark, ni faire passer une version du benchmark pour un paquet de soumission. |
| 2 octobre 2026 | Préserver les sources locales d'origine et les archives publiées ; conserver cinq copies locales en lecture seule du paquet RC1 à `results/generated/manuscript-rc1/` et consigner leurs sommes dans `results/SHA256SUMS_manuscript_rc1`. | Une nouvelle analyse aura ses propres sorties sous `results/generated/consolidation-post-RC1/<run-id>/`. Ne jamais écraser les sources, résultats ou assets publiés ; la lecture seule locale n'est pas un stockage WORM. |
| 2 octobre 2026 | Ne pas exécuter de nouvelle expérience ni de réanalyse scientifique dans le cadre de l'import. | Les preuves historiques restent identifiées comme historiques ; aucun livrable scientifique futur n'est pré-rempli ou présenté comme produit. |
| 2 octobre 2026 | Laisser les trois fichiers `docs/manuscript_audit_fr*.md` dans leur emplacement actuel et préserver la correction DOI préexistante dans `README.md`. | Ces changements préexistants sont hors périmètre de cette consolidation documentaire. |

## Calendrier relatif et séquence proposée

La date exacte de démarrage scientifique n'est pas décidée. Une fois validée, **S1** désigne la première semaine à compter de cette date, puis S2, S3 et S4 les semaines suivantes ; la date d'import du 2 octobre 2026 ne sert pas de point de départ.

| Fenêtre relative au démarrage validé | Travail proposé |
|---|---|
| S1 | A : confirmer accès, responsables, périmètre, budget et support ; B : commencer la vérification des résultats centraux ; décider si la branche de confirmation indépendante est réellement faisable. |
| S2 | C : diagnostic GraphSAGE borné sur MAUDE, seulement si les accès et le plafond de ressources permettent de l'engager. |
| Début S3 | D : sélectionner au plus une seule analyse P2 (D1 ou D2), sinon la reporter avec motif. |
| S3–S4 | E : intégrer uniquement les analyses réellement terminées et finaliser avec approbations. |
| Fin S4 | F : décision des auteurs de soumettre, réduire le périmètre ou corriger un blocage ; arrêt du cycle selon la règle de la roadmap. |

Il s'agit de fenêtres proposées, pas de dates calendaires ou d'un engagement de calcul. L'absence de démarrage validé signifie que les semaines ne sont pas engagées.

## Prérequis et décisions encore à obtenir

Aucun nom, budget, calendrier absolu, support éditorial ou signature n'est désigné. Les décisions suivantes doivent être prises et leur preuve consignée avant l'étape correspondante :

| À obtenir | Ce qui est à établir | Trace attendue avant validation |
|---|---|---|
| Responsabilités | Attribuer les rôles de référent scientifique, développeur, second lecteur, validateur scientifique, auteurs et auteur correspondant ; préciser qui approuve la portée et la décision finale. Une personne peut assumer plusieurs rôles, mais aucun rôle n'est encore attribué. | Décision datée, responsables acceptants et périmètre d'approbation consignés au lot A. |
| Démarrage et échéance | Fixer la date de démarrage scientifique et la date de décision de fin de S4. | Accord daté des responsables ; calendrier relatif converti en dates uniquement après cet accord. |
| Entrées et droits d'accès | Vérifier le paquet d'accompagnement décrit dans le supplément, les sources, les artefacts, les checkpoints éventuellement nécessaires, les données et les droits/conditions d'usage. Distinguer accès réel, mention dans les PDF et éléments absents. | [Inventaire réel](inventory.csv), sources d'accès et limites documentées ; aucune disponibilité supposée. |
| Calcul et stockage | Définir un plafond explicite, les ressources disponibles, l'environnement propre, le temps et le stockage compatibles avec les analyses proposées. | Budget/plafond accepté avant exécution et capacité vérifiée ; ne pas déduire de budget des durées de planification. |
| Support éditorial | Choisir un support principal et un support de repli, puis vérifier leurs consignes officielles, format, langue, anonymisation, longueur et exigences d'artefacts. La seule mention « FAIA » ne suffit pas. | Versions/liens datés des instructions et décision des auteurs ; aucune revue n'est encore retenue. |
| Confirmation indépendante | Établir si une origine réellement non consultée, complète et mûre est accessible ; fixer le cas échéant les choix avant son ouverture. | Décision de faisabilité en S1 et preuve d'accès ; sinon branche explicitement reportée, sans requalifier les anciens tests. |
| Portée et P2 | Après examen des ressources, choisir D1 ou D2 au maximum, ou ne faire aucune P2 ; fixer la date de décision et les plafonds. | Décision datée avant l'analyse ; aucune exécution des deux options. |
| Approbations et déclarations | Obtenir les validations des auteurs sur résultats/références et les informations vérifiées sur identités, affiliations, contributions, financement, conflits, éthique, conditions d'usage des données et assistance par IA. | Approbations explicites et éléments requis par le support ; ne pas transformer une information manquante en « aucun » ou en dispense. |

## Séparation et préservation des artefacts

- **Dans Git :** documents de pilotage, roadmap, petits manifestes/CSV et sommes de contrôle. Les chemins de copies et d'exécutions locales sont des destinations, pas une affirmation qu'une pièce scientifique existe déjà.
- **Local et ignoré :** `results/generated/manuscript-rc1/` conserve les copies en lecture seule du paquet manuscrit RC1 ; `results/generated/consolidation-post-RC1/<run-id>/` réserve un espace neuf par exécution future. Ces deux répertoires n'autorisent jamais la modification des sources locales d'origine.
- **Données brutes :** restent à l'extérieur du dépôt ; accès, droits et empreintes doivent être consignés selon le cas.
- **Versions publiées :** assets et versions déjà publiés restent immuables ; toute correction éventuelle exige une nouvelle version et une provenance explicite.
- **Frontière des objets :** HealthGraphBench v0.2.0 est une version du benchmark, RC1 est le paquet de manuscrit ; le DOI benchmark ne devient pas un DOI de manuscrit.

Les trois audits existants dans `docs/` ne sont pas déplacés ni réécrits ici. Aucun fichier de résultats, protocole expérimental daté, matrice de preuves ou approbation scientifique vide n'est créé pour simuler un travail effectué.

## Vérification de l'organisation

Contrôles réellement exécutés, sans rejeu des analyses de santé ni entraînement sur les données réelles :

| Contrôle | Résultat observé |
|---|---|
| `python -m unittest discover -s tests -v` | **41 tests réussis**, dont cinq régressions des frontières Gitflow, sous Python 3.14.7 et NumPy 2.5.3. |
| Scénario dans un dépôt Git temporaire, supprimé à la fin | Feature → develop acceptée ; feature → main refusée ; merge commits conservés ; hotfix intégré à main, à une release active et à develop ; release retournée à develop ; arbres livrés cohérents et tags annotés sur les commits approuvés. Aucun tag du vrai dépôt créé. |
| Inventaire | Tailles et SHA-256 des **15 artefacts** présents vérifiés ; les cinq copies RC1 n'ont aucun bit d'écriture. Les deux sorties Part D locales ignorées ne sont pas annoncées présentes dans un clone neuf. |
| Manifeste interne du ZIP RC1 | **419 fichiers** vérifiés par empreinte, sans extraction ni modification de l'archive. Ce contrôle d'intégrité ne valide pas les conclusions scientifiques. |
| Documentation | **16 liens locaux** vérifiés ; sections scientifiques 1–9 et règle d'arrêt de la roadmap conservées. |
| CI et CLI | YAML analysé, direction de PR exercée via un événement JSON, `python -m healthgraphbench.cli --help` exécuté. |
| Isolation des sorties | Les chemins RC1 et de nouvelles exécutions sont effectivement ignorés par Git. |

Rapport local détaillé : `results/generated/consolidation-post-RC1/workflow-smoke-20261002/verification.json`. Ce journal est ignoré ; le tableau ci-dessus conserve la preuve compacte destinée à Git.

La première tentative `python -m pytest` n'a exécuté aucun test : pytest n'est pas installé. Le guide et la CI utilisent désormais `unittest`, déjà employé par la suite, sans nouvelle dépendance de test. La CI GitHub n'a pas été exécutée à distance et les protections serveur restent à activer avant le travail partagé. Aucun commit, push, nouveau tag du dépôt, DOI ou approbation d'auteur n'est produit par ces vérifications.

## Avancement technique A/B demandé

Le démarrage technique des lots A/B est autorisé par la demande d'avancer la roadmap avec des subagents. Il ne remplace pas l'accord des auteurs sur le calendrier scientifique, le support éditorial ou la soumission.

- Intégration et cadrage technique : assistant principal ; rejeux : subagent `CoreReplays` ; audit arithmétique et matrice des affirmations : subagent `ClaimsAudit`. Ces rôles techniques ne sont pas des signatures d'auteur ni un second lecteur humain.
- Branche de travail : `feature/post-rc1-verification`, créée depuis `develop` sans commit ni push ; les changements existants restent préservés.
- Entrées : ZIP RC1 extrait dans un nouveau répertoire local `core-verification-20261002/inputs/HealthGraphBench_RC1/` sous les sorties de consolidation. Extraction de 15 162 289 octets, sans liens symboliques ni chemins sortant du répertoire cible ; fichiers et dossiers en lecture seule. Les originaux restent intacts.
- Ressources observées avant exécution : 8 CPU logiques, 30 GiB de RAM dont environ 3,3 GiB disponibles ; swap saturé ; 194 GiB de disque disponibles. Ne pas interpréter ces capacités comme un budget comparatif historique.
- Plafond opérationnel de chaque tâche B : 900 secondes de temps mural, calcul mono-processus et bibliothèques numériques mono-thread, 768 MiB de RSS et 512 MiB de nouvelles sorties ; dépassement à arrêter et consigner. Aucun téléchargement de données brutes ni entraînement de modèle de santé dans B.
- Environnement neuf : Python 3.13.5 ; versions directes de `requirements-review.txt` RC1 (`numpy==2.3.5`, `matplotlib==3.10.8`, `scikit-learn==1.8.0`). Les versions transitives et l'usage réellement mesuré seront consignés avec l'exécution.
- Lot C : préparation du protocole et examen de faisabilité séparés de B ; aucun test historique ou nouveau holdout utilisé pour sélectionner des paramètres.

## Résultats techniques A/B et décision C

- `CoreReplays` : une invocation, 4,539 s, pic RSS agrégé échantillonné 177,8 MiB, 7 619 114 octets de sorties ; dix contrôles réussis. MAUDE 49 champs, Part D 91, deux comparaisons CMS de 284 champs, cinq fichiers B1/B2 et la synthèse de couverture identiques aux références.
- `ClaimsAudit` : 609/609 contrôles, dont 419 empreintes du manifeste ; 66 clés numériques concordantes à la précision déclarée (deux arrondis Part D à six décimales expliqués). Matrice de 42 affirmations et limites fournie. Identité locale des trois sorties originales également vérifiée, sans réingestion ni entraînement.
- Intégration : chemin source du supplément corrigé dans la matrice ; protocole/faisabilité MAUDE et contrôles temporels ciblés consignés. La validation 2023 comporte 3 483 observations positives, 7 705 liens et 1 618 588 paires candidates ; pas de nouveau score.
- Vérification finale : 747/747 contrôles du paquet RC1, 16 définitions GraphSAGE égales au noyau source épinglé, 41 tests du dépôt réussis dans Python 3.13.5 / NumPy 2.3.5. Les contrôles de documents et d'AST ne certifient pas les conclusions scientifiques ni l'apprentissage réel.
- Décision : conserver les chiffres et conclusions historiques dans leur périmètre ; aucune anomalie centrale non expliquée détectée par ces contrôles. B reste ouvert pour revue humaine et disponibilité publique historique des champs. Le protocole C est daté, mais C n'est pas exécuté : les journaux d'optimisation et checkpoints doivent être instrumentés sans altérer la trajectoire historique avant lancement.

Les pièces et empreintes sont rassemblées dans `results/consolidation_core_verification_20261002.json`. Les données et logs détaillés restent dans le nouveau run local ignoré. Aucune P2, confirmation indépendante, nouvelle version de manuscrit, publication distante, validation d'auteur ou soumission n'est effectuée.