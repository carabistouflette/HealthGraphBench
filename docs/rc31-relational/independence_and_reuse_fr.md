# RC3.1 — confirmation, disponibilité et équipe extérieure

## État vérifié, pas une confirmation acquise

Le contrôle frais du catalogue officiel, métadonnées seulement, est conservé sous `results/rc31_availability_20261004.json`; corps exact `results/rc31_catalog_20261004.json`. Capture publique du4octobre2026à19:58:26.587211UTC, HTTP200,278033octets, SHA256`1388b6cd63fd11d2977cb041d7ade58075b34ef3943253129b1df696325d85fa`. Les versions exposées dans cette réponse filtrée vont de2013à2024; aucun node service2025 n'y est listé. Ce constat est borné à la réponse et à cet instant, pas absence universelle de données privées/publiques.

Aucun outcome2025 ouvert/téléchargé, aucune métrique cible calculée; aucune modification du forecast Q2 scellé ou de ses scores/origine/protocole. Non-consultation humaine : **unknown**. Réutilisation par équipe extérieure : **non réalisée**. Assistant/agent n'est pas cette équipe.

## Deux expériences temporelles distinctes

1. **Forecast Q2 existant** : conserver sa sélection, ses scores, son ancrage et sa cohorte. À disponibilité réelle, une personne indépendante vérifie provenance officielle du fichier cible et les attestations prévues, puis exécute l'évaluation différée sans fit ni tuning/seed supplémentaire. Interface existante `healthgraphbench.q2.prospective_partd.evaluate_forecast(origin_dir, target_source, target_manifest, output_dir)`; le CLI correspondant est `scripts/run_q2_prospective_partd.py`. Il ne devient pas par cette note un résultat réalisé ou indépendant passé.
2. **Nouvelles méthodes RC3.1** : les comparateurs définis aujourd'hui ne font pas rétroactivement partie du forecast Q2. Toute confirmation de leurs contrastes exige son propre protocole, source-set, origine et scores scellés **avant ouverture d'une cible non consultée**, ainsi que réel intervenant/attestations. Un test2024 supplémentaire, une cohorte NPI disjointe ou un certificat automatique ne ferment pas cette gate.

Pour une nouvelle confirmation, fixer avant cible : contraste principal, unité et métrique, marge analytique/utilité motivée par les responsables, plan d'incertitude et gestion des dépendances; conserver toutes configurations/seeds prévues et aucune sélection cible. Les intervalles exploratoires RC3.1 conditionnels aux fits n'établissent pas déjà cette confirmation. CMS2026 n'est pas certifiée intacte; D2/ClinicalTrials ne sont pas des substituts.

## Disponibilité effective à l'origine

Un calendrier d'événement/service n'est pas une date d'accès public aux bytes. Pour une future collecte : conserver à l'acquisition URL finale, horodatageUTC, corps exact, SHA256/size, version/dataset node/media et règles de filiation. Avant une prédiction, n'admettre que les versions réellement acquises et documentées avant cette origine; conserver les rééditions au lieu d'écraser l'ancien snapshot. Les métadonnées HTTP/Drupal ne prouvent pas seules une première publication historique.

Les raw et préparations actuels restent rétrospectifs/exploratoires, même si les features sont datées antérieures à la cible. Le forecast Q2 a ses propres captures réelles2019–24 : les conserver, ne pas les transformer en preuve de disponibilité publique2019–24 dans leurs années de service. L'accès local aux archives ne garantit pas l'accès extérieur ou un dépôt durable.

## Parcours réel d'une équipe extérieure

Préconditions humaines : identifier une équipe qui n'a pas conduit ces expériences, son rôle/affiliation réel, consentement et règles de diffusion des journaux; obtenir les autorisations institutionnelles pertinentes, sans présumer une exemption éthique. Consigner toute consultation antérieure et toute aide des auteurs. État actuel de ces champs : **non recueilli**, pas approbation implicite.

Livraison nécessaire : commit/protocole exacts, wheel construit depuis un clone du commit publié et hashes de ses sources, contrats/manifests, URLs publiques des raw, documentation et commande sélectionnée. La version de package0.2.0 seule n'identifie pas les sources scientifiques du cycle; SHA commit/wheel/source-set doivent être conservés. Aucun raw lourd n'est promis dans le ZIP du manuscrit.

L'équipe doit ensuite, dans son environnement propre :

1. Récupérer elle-même les sources publiques et enregistrer URL/versions/bytes/hash/date; déclarer si elle a seulement reçu une préparation dérivée.
2. Préparer la tâche PartD depuis ces vrais raw via l'API `load_task("partd", source_root, manifest_path=..., preparation_dir=...)`, avec un répertoire neuf et le contrat reçu.
3. Reproduire une procédure RC3.1 explicitement choisie et ses règles de sélection sur validation, puis produire scores/rangs/métriques : comparer les véritables résultats à la référence, pas lire un JSON historique pour simuler une reproduction.
4. Ajouter **son propre comparateur** sans intervention directe cachée des auteurs : `task.history_view(split)` expose seulement le passé; un scorer reçoit `(view,npi,candidate_ids)` et renvoie un score fini par candidat; `task.predict_ranker` n'exige pas de whitelist. L'équipe fixe son protocole avant scoring du test et déclare le statut exploratoire des périodes déjà consultées. Ce parcours public réalise les deux années; ne pas l'utiliser pour prétendre avoir isolé une année ou préservé un futur hold-out sans vérifier sa procédure.
5. Conserver commandes, OS/Python/dépendances, journaux, erreurs, code réellement ajouté, coûts et résultats. Déclarer séparément réussite autonome, réussite avec assistance, échec et étapes non réalisées. Durée humaine, compréhension et satisfaction nécessitent de vraies observations.

La démonstration assistante déjà obtenue est une preuve logicielle distincte. Une nouvelle exécution par ce même assistant ne satisferait pas cette étude extérieure.

## Utilité de revue : éventuelle étude humaine séparée

Les courbes RC3.1 de propositions/liens retrouvés/précision/couverture mesurent une charge sur observations publiées. Elles ne démontrent ni pertinence clinique de chaque proposition ni bénéfice patient. Une étude ultérieure peut présenter des propositions en aveugle sur la méthode, à charge égale, et mesurer pertinence analytique et temps de revue; participants, protocole, référence de jugement et autorisations doivent exister réellement. Absence d'un lien dans les fichiers n'est pas une erreur clinique.

Ces trois gates — évaluation temporelle, reproduction extérieure et utilité humaine — restent **distinctes et non réalisées** tant que leurs preuves manquent. Pas d'attente indéfinie pour déclarer le cycle exploratoire terminé; pas de conversion de cette absence en résultat négatif. Support exact, déclarations et approbation des auteurs restent nécessaires à toute soumission; aucun envoi automatique.
