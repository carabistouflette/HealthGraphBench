# Disponibilité publique et indépendance — cycle Q2

## Ce que les sources actuelles n’établissent pas

Une année de service, réception FDA, `DATE_ADDED`, date de modification HTTP, chemin daté, date de création/modification Drupal ou accès actuel ne prouvent pas seuls que **ces bytes** étaient publics à l’origine historique revendiquée. Les expériences principales MAUDE/CMS2023–25 et Part D2023/24 restent exploratoires; un réglage plus fort n’efface pas leur consultation antérieure.

Les [archives nursing CMS](https://data.cms.gov/provider-data/archived-data/nursing-homes) ont des dates et un accès public déclarés. La [FAQ officielle](https://data.cms.gov/provider-data/about/faq#archived-data-snapshots) distingue les snapshots mensuels avant juillet2026 des archives de seuls fichiers modifiés ensuite, accompagnées d’un manifeste. Cette disponibilité constitue une piste, pas la preuve qu’un hold-out2026 soit intact: le préparateur historique collecte des épisodes de toutes années avant de filtrer les lignes de modèle2019–25;2026 peut avoir été incluse dans des statistiques globales déjà consultées. Aucun outcome nursing2026 n’a été ouvert comme nouveau hold-out de ce cycle.

Le [catalogue Part D officiel](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug) expose des versions annuelles. La [méthodologie CMS2023, datée mars2025](https://data.cms.gov/sites/default/files/2025-04/MUP_DPR_RY25_20250401_Methodology_508.pdf) décrit les délais de submission, démographie NPPES de l’année suivante et suppressions des petites cellules. Elle indique aussi la mise à jour des années2013–21 en mai2024. Une reconstruction avec ces fichiers réédités ne prouve donc pas leur disponibilité dans leurs années de service.

Le node2023 `e54db557-cd82-4e91-a0fe-61aad5865d69` est actuellement publié, créé le8avril2025 et modifié le9septembre2025; ces dates ne sont pas des empreintes contemporaines du fichier brut. L’identifiant `9552739e-3d05-4c1b-8eff-ecabf391e2e5` dans l’ancienne filiation est un terme de taxonomy de dataset, pas un ancien node2024: une différence avec le node2024 ne démontre pas une dérive des bytes.

## Inventaire des populations de développement

`results/q2_partd_development_population_20261003.json` contient **2 518 NPIs**, union de tous ceux apparaissant dans les edges et rankings des sept runs Part D conservés, et les empreintes des fichiers effectivement lus. L’exclusion ne se limite pas aux2 288 NPIs du lookback002. Le nouveau run de comparaison est également inventorié au moment du forecast, sans présumer que ses NPIs soient tous inclus dans l’ancienne union.

L’ancien préparateur parcourait les identifiants nationaux pour former une cohorte, puis rejetait les autres NPIs **avant** extraction des drugs/claims/specialties. Ce parcours d’identités n’est pas une consultation de tous les labels provider–drug. Il ne remplace pas une attestation humaine de non-consultation d’autres sorties ou données.

## Règle prospective vérifiable

Le bloc `tasks.partd.prospective` fixe une nouvelle procédure avant ses fits:

1. Conserver le catalogue CMS officiel sans ouvrir des outcomes cibles. Refuser de qualifier ce forecast de prospectif si le service2025 est déjà listé officiellement.
2. Recapturer publiquement, sans authentification, **l’intégralité** des sixCSV2019–24 en streaming. SHA256, nombre d’octets et comparaison avec les fichiers locaux établissent les données réellement connues avant prédiction. Les corps ne sont pas dupliqués sur disque; reçus, URL finales, métadonnées et horodatages sont conservés. Aucun ancien `last_updated` n’est utilisé comme preuve rétroactive.
3. Recontrôler le catalogue après toutes les recaptures, puis fixer l’origine réelleUTC. Ce n’est ni la première publication mondiale, ni la première acquisition historique de ces fichiers, déjà conservés auparavant.
4. Choisir2000 NPIs présents avant le target via `SHA256(salt + NUL + NPI)`, salt `q2-prospective-20261003`, ordre hex puisNPI, hors toutes populations de développement inventoriées. Le choix ne consulte aucun drug/claim/label du target.
5. Reprendre exclusivement les configurations choisies dans la validation2023 du run de comparaison. Aucune sélection nouvelle de configuration ou de seed dans la nouvelle cohorte. Adapter/refitter la procédure sur sa seule histoire publique2019–24; c’est une évaluation d’une procédure fixée avec refit pré-cible, pas le transfert sans adaptation d’un checkpoint ancien.
6. Conserver histoire, candidats, checkpoints et **tous les scores**, puis recapturer le catalogue après les fits et avant le scellement final. Une publication2025 intervenue entre les premières captures et ce dernier contrôle refuse le statut prospectif; phases, checkpoints et erreurs restent conservés. Les deux catalogues de scellement, leurs corps/hash/timestamps et la chronologie des captures sont vérifiés par l’évaluateur. La cible est une nouvelle relation **observée lors de cette publication annuelle**, non une première prescription ni une prévision clinique prospective de l’année de service2025.
7. Publier les empreintes du forecast et des scores scellés avant la publication cible future. Un timestamp local seul n’est pas un ancrage externe antérieur à publication; le dépôt publié conserve les artefacts et leur filiation.
8. À réception réelle de la source cible, vérifier le node officiel service2025, le lien de filiation vers son primary-file et les size/SHA1 du CSV exposés par ce média, puis recapturer publiquement les bytes du fichier et les comparer à la source locale et à son SHA256. L’évaluation utilise les scores scellés sans fit, tuning ou choix du seed. `dataset_id` désigne ici le **node annuel2025**, pas le terme de taxonomy commun aux anciens manifests. Les dates Drupal/HTTP ne servent toujours pas de preuve de première publication.

La publication future n’a pas de date garantie. Le catalogue principal interrogé dans la recherche préliminaire exposait au plus service2024; cela ne prouve pas une absence universelle de données privées ou d’artefacts non examinés. Le runner doit recontrôler le catalogue et ne peut pas utiliser cette observation préliminaire comme un pass permanent.

## Statuts qui restent séparés

- **Captures/hashes valides:** preuve de disponibilité publique actuelle des inputs effectivement utilisés, pas preuve de disponibilité historique2019–24.
- **Forecast scellé:** véritable calcul prospectif conservé, pas encore métrique sur source cible.
- **Évaluation calculée:** requiert un fichier cible réel, des scores scellés valides et aucun refit sur le target.
- **Indépendance scientifiquement établie:** exige encore les conditions de non-consultation/usage prévues; les gates humaines non attestées ne passent pas implicitement.
- **Indépendance des observations:** non garantie par des NPIs disjoints ou un target futur; les drugs et les dépendances de réseau peuvent être partagés.

Une source absente ou une attestation manquante ne sont remplacées ni par une simulation médicale, ni par une métrique zéro, ni par un certificat d’assistant. Les fixtures synthétiques servent uniquement à exercer le logiciel d’évaluation différée. Les anciennes périodes/cohortes ne sont pas requalifiées à partir de ces fixtures.

## Exécution réelle et scellement conservé

`partd-prospective-001` a recapturé intégralement les sixCSV publics2019–24, dont les bytes/hashes concordent avec les sources conservées. Les trois catalogues à21:51:34,22:10:50 et22:28:54UTC le3octobre2026 ne listent aucun node annuel2025. Origine scellée22:10:50.231060UTC; forecast scellé22:28:54.610343UTC. Cette disponibilité est établie à ces instants réels, pas rétrospectivement à l’année de service.

La cohorte contient2000 NPIs disjoints des2518 NPIs de développement et des2288 NPIs du nouveau run de comparaison (ces derniers sont tous dans l’ancienne union). Sélection inchangée sur validation2023; sept vrais fits appris et deux heuristiques scorent2 112 688 candidats chacun, sans labels cibles ni tuning supplémentaire. Les états, neuf fichiers de scores, histoire/layout et reçus sont conservés.

`results/q2_partd_prospective_forecast_20261003.json` et `results/q2_partd_prospective_origin_20261003.json` sont les copies exactes des records scellés; le premier expose les empreintes individuelles des scores/checkpoints. Leur publication Git est l’ancrage externe, distinct des timestamps locaux de calcul. La source officielle2025 reste absente dans les catalogues capturés, aucune métrique cible n’est calculée et la gate humaine de non-consultation demeure `unknown`. Le statut reste `sealed_awaiting_official_target_publication`, **pas** une évaluation indépendante passée.
