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
