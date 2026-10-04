# Cycle scientifique Q2 — protocole du 3 octobre 2026

Ce cycle renforce les expériences, la disponibilité des informations et la réutilisation. Il ne constitue ni une nouvelle clôture rédactionnelle de RC2.2, ni une garantie de quartile ou d’acceptation. RC2.2, C, D1, leurs packages, checkpoints, résultats et ledgers sont conservés. D2 et ClinicalTrials ne sont pas réintroduits; aucun merge, tag, dépôt ou envoi de manuscrit n’est automatique.

## Verrou avant tout fit médical

Le protocole exécutable est `configs/q2_scientific_protocol_20261003.json`, depuis le commit RC2.2 `6130e9cd35dd66ba9edab2dc69d1b24c2d8f3d91`. Les sources scientifiques réellement exécutées doivent être énumérées dans `locked_sources`, byte-identiques à leur blob dans HEAD, et publiées avec le prévol avant les fits médicaux. Le SHA256 du protocole est fourni explicitement au runner; une modification non committée d’une source verrouillée bloque l’exécution. Les quatre documents utilisateur laissés hors périmètre ne sont pas un motif pour ignorer ce verrou et ne sont pas ajoutés aux commits Q2.

Chaque run conserve le protocole exact, le commit, les SHA des sources, l’argumentaire d’exécution, Python, les versions des dépendances, les entrées et leur niveau de préparation. Les sorties Q2 sont distinctes des sorties historiques et un répertoire de phase existant ne peut pas être réutilisé. Les erreurs, checkpoints déjà produits et grilles incomplètes sont conservés; une grille incomplète ne donne aucune sélection.

## Budget de recherche et initialisations

Chaque famille réglable dispose de **six configurations publiées**, avec le même nombre d’opportunités de choix et des plafonds communs. Ce n’est pas un coût de calcul identique: dimensions, nombre de paramètres et répétitions diffèrent; les coûts effectivement mesurés sont rapportés.

Les fits véritablement stochastiques utilisent les trois seeds appariés **103, 211, 307**. Le choix porte sur une configuration et la moyenne de validation, jamais sur le meilleur seed. Les modèles déterministes ne sont ajustés qu’une fois. Pour `HistGradientBoostingClassifier` scikit-learn **1.8.0**, les bins sont sous-échantillonnés au-delà de **200 000 lignes exactes de training**: trois fits dans ce cas, un seul au seuil ou en-dessous. La règle est réévaluée à chaque refit; `early_stopping=False` et `max_features=1` ne suffisent pas seuls à établir le déterminisme. Les nombres de lignes et états aléatoires sont conservés.

Les plafonds sont **1 800 s**, **4 GiB de RSS agrégée contrôleur + worker** et **1 GiB de fichiers par phase**, **21 600 s par famille de validation**, **86 400 s par run** et **16 GiB de sorties totales**. Le superviseur Linux contrôle ces plafonds et conserve son état. Les modèles n’utilisent pas de workers de calcul supplémentaires; pour la démonstration wheel, `exec` remplace le PID supervisé au lieu de créer un descendant non compté. Les bibliothèques numériques sont effectivement limitées à un thread. Une capture publique en streaming compte dans le temps du run mais ne duplique pas les CSV dans les sorties.

L’environnement Q2 est séparé de l’environnement historique. L’extra Q2 fixe NumPy **2.3.5**, scikit-learn **1.8.0** et Numba **0.68.0**; les autres versions réellement utilisées sont enregistrées. L’absence du backend Numba requis n’est pas masquée par un fallback Python. Le NumPy/Numba du cycle ne doit pas remplacer les dépendances de l’analyse RC2.2.

## P1 — comparaisons renforcées

Les trois sources sont préparées à nouveau depuis les vrais raw vérifiés. Le snapshot compact C/D1 ne remplace pas les informations fabricant/multiplicités MAUDE ni les raw CMS. Les résultats sur les cohortes et périodes de développement déjà consultées restent **exploratoires**, même après réglage et réplication.

### MAUDE

Training jusqu’à 2022Q4; choix sur micro Recall@10 de validation2023; refit annuel avant les tests2024 et2025. Le contexte de candidats/éligibilité et les features temporelles sont actualisés après chaque trimestre évalué, sans fit sur le trimestre cible. Les états latents appris au refit restent ceux du début d’année.

| Famille | Six configurations | Paramètres fixes |
|---|---|---|
| Logistique | `C=.01,.1,1,10,100,1000` | LBFGS, balanced,1000 itérations,tol1e-8,scaler training-only |
| HGB | `(itérations,feuilles,L2)=(100,7,0),(100,15,0),(300,7,0),(300,15,0),(600,7,.1),(600,15,.1)` | LR.1,early stopping désactivé,max_features1,max_bins255,min_samples_leaf20 |
| Spectral | rang8/16 × power iterations12/18/24 | initialisation seedée, aucune régularisation artificielle |
| BPR + moyenne fixe | dimension8/16 × régularisation.001/.0001/0 | 30 époques,LR.03,moyenne de tous voisins historiques |
| GraphSAGE `mean` | dimension8/16 × régularisation.0005/.000005/0 | 30 époques,LR.02,fanout8 |
| GraphSAGE `none` | même grille | 30 époques,LR.02,aucun voisin |

Popularité globale et fréquence des voisins ont zéro opportunité de tuning. Les embeddings BPR/GraphSAGE Q2 sont initialisés par normales de sigma.05; GraphSAGE démarre avec transformation propre identité et transformation voisine .25 identité. Les kernels BPR MAUDE sont séquentiels par arête/époque, choisissent un départ négatif par mélange entier déterministe du seed, de l’époque et des indices, puis parcourent cycliquement le vocabulaire jusqu’au premier problème hors histoire du produit. Cette règle nouvelle est publiée dans le code: on ne prétend pas rejouer exactement les initialisations ou trajectoires C/D1. Les gradients du nouveau kernel sont contrôlés numériquement; fidélité à la formule n’est pas identité avec un run historique.

**Gate d’apprentissage, avant sélection:** probe BPR fixe construit exclusivement dans l’histoire du fit, au plus20 000 triplets, partagé à historique égal entre `mean`/`none`. Changement de l’état persistant et baisse relative de perte de données ≥**1 %** pour **chacun des trois seeds**. Les six configurations sont toutes exécutées et leurs échecs de gate conservés; parmi elles, seules celles passant les trois gates sont admissibles. La métrique de validation choisit ensuite la meilleure configuration admissible. Aucune configuration admissible: run non concluant, pas contrôle « apprenant » inventé. Le refit sélectionné doit également passer la gate avant scoring de test. Une baisse de training n’est pas une preuve de généralisation.

`none=tanh(W_self x)` ne propage ni voisins ni gradients via voisins. La capacité n’est pas égalisée: `mean` active2d² scalaires de transformation, `none` d², auxquels s’ajoutent les vecteurs de nœuds. Le réglage séparé et une différence de métriques ne constituent pas un effet causal d’agrégation à capacité égale. La perte presque plate de D1 reste un fait conservé, pas la preuve d’un bug d’optimisation.

### Part D

Cohorte pré-cible2000; histoire complète2019–22 pour validation2023, puis2019–23 pour test2024. Identité médicament: generic name trim exact. Tous les candidats ont été observés dans le vocabulaire antérieur de la cohorte et sont absents de toute l’histoire du provider. La cible est une relation nouvelle **observée dans les données publiées**, non une première prescription clinique. Les suppressions de petites cellules restent une limite.

| Famille | Six configurations | Fixes |
|---|---|---|
| Logistique | C.1/1/10 × class_weight None/balanced | LBFGS,1000,tol1e-8,scaler training-only |
| BPR | `(d,LR,L2,négatifs)=(16,.01,.001,3),(16,.03,.001,3),(16,.03,.01,3),(32,.01,.001,3),(32,.03,.001,3),(32,.03,.001,5)` | 30 époques,poids spécialité.35 |
| HGB | `(LR,itérations,feuilles,L2)=(.03,100,15,0),(.05,100,15,0),(.1,100,15,0),(.05,200,15,0),(.05,100,31,0),(.05,100,15,1)` | early stopping désactivé,max_features1,max_bins255,min_samples_leaf20 |

Le training tabulaire reprend les liens de l’histoire et son échantillonnage négatif5× au maximum. BPR initialise les facteurs par normales de sigma1/√d, parcourt les arêtes triées et tire uniformément avec remise dans le complément historique de chaque provider. Les seeds portent à la fois les initialisations et les tirages négatifs: ce n’est pas une intervention isolée sur l’initialisation. Les deux heuristiques, popularité de spécialité et overlap d’histoire, ne sont pas réglées. Choix sur moyenne du micro Recall@10 validation2023; égalité exacte départagée par l’ordre publié.

### CMS nursing

Features `facility_history` et `facility_plus_combined_ownership`; pour chaque ensemble, logistique aux sixC MAUDE (class_weight None) et HGB aux six configurations Part D. États/scalers sont appris dans le training strictement antérieur au target year. Choix ROC-AUC validation2023, refits2024/2025; prévalence non réglée après le verrou. Les streams poolés couvrent les mêmes années: si HGB change de régime, le fit déterministe est réutilisé dans chaque stream sans être réentraîné ou compté comme répétition aléatoire.

Les sept raw CMS sont exactement ceux du manifeste figé. La source complète propriétaires119 419 lignes a été restaurée par pagination jusqu’à page vide, puis JSON compactUTF-8 sans newline; **125 653 423 octets**, SHA256 `ba0a61e19765256a57efee604e795ecbb993ae9c439ff682efb010ce444ad866`. Les deux erreurs de collecte sont consignées dans `results/q2_cms_raw_recovery_20261003.json`. Le source-set n’a pas été remplacé silencieusement.

Ces snapshots rétrospectifs août2026 ne prouvent pas la disponibilité publique à l’origine des années de service. Les épisodes2026 peuvent déjà avoir contribué aux agrégats du préparateur historique: CMS2026 n’est pas déclarée intacte.

## P2 — disponibilité et évaluation indépendante

Voir [la règle de disponibilité et ses gates](availability_fr.md). On ne rebaptise pas les nouvelles métriques principales2023–25 « indépendantes ». La piste prospective Part D est distincte: recapturer publiquement les bytes2019–24, sceller l’origine, exclure tous les NPIs déjà utilisés et produire les scores de la prochaine publication officielle service2025 avant ouverture de ses labels. C’est une prévision de relation publiée, pas une prévision clinique à l’année de service. La date de publication future n’est pas promise. Les prévisions scellées ne valent pas évaluation réalisée; celle-ci requiert réellement le fichier cible officiel et les preuves/attestations prévues.

## P3 — réutilisation et modèle hors paquet

Voir [le parcours de migration et de réutilisation](reuse_fr.md). La préparation raw, les fits numériques, scores, checkpoints et métriques doivent être observés dans un environnement wheel propre. Le nouveau cosine top50 est appris sur incidence historique binaire via `PartDHistoryView`, sans whitelist dans le package. Son fit est non supervisé; aucune perte d’optimiseur inexistante n’est rapportée. Le baseline SDK historique n’est pas le gagnant de grille Q2 par simple renommage.

La preuve technique réalisée par assistant/agent n’est ni une expérience par utilisateur humain extérieur, ni une évaluation indépendante. Un participant réel, son environnement/commande, ses écarts et son résultat demeurent des preuves séparées. Les noms/auteurs/affiliations, déclarations, licence de manuscrit, support et approbation restent des gates humains.

## Reprise MAUDE après sérialisation — même protocole

`maude-comparison-001` a achevé les84 fits de validation, les six grilles et la sélection verrouillée avant tout scoring test; le premier worker heuristique2024 a ensuite refusé `newline="\\n"`. Les deux littéraux de fin de ligne sont corrigés sans changer les calculs. Le prévol réel du worker sur un bundle synthétique vérifie les deux heuristiques, les archives JSONL décodables et deux positifs/rangs connus; la régression temporelle couvre plusieurs lignes indépendantes.

La reprise `scripts/run_q2_maude.py --complete-validation <root001> ...` conserve ce root en lecture seule, utilise un nouveau root et refuse toute grille incomplète, seed manquant, sélection divergente ou résultat de phase différent. Elle compare les sources consommatrices aux blobs du commit de validation: seules les deux corrections exactes de newline sont permises dans MAUDE; le contrôleur publié est étendu et l’adapter CMS modifié n’est pas consommé. Le protocole JSON, ses54 sources verrouillées, ses grilles, seeds, gates et SHA256 restent inchangés. Le nouveau commit/source-set est enregistré séparément.

Les durées et octets du run précédent, y compris la phase échouée, sont déduits des plafonds cumulatifs avant les nouveaux refits test. Aucun fit de validation réussi n’est relancé. Checkpoints et gates des nouveaux refits restent obligatoires avant scoring; l’erreur initiale, la sélection et la préparation restent conservées. Preuves: `results/q2_maude_first_run_failure_20261003.json`, `results/q2_maude_completion_preflight_20261003.json`.
