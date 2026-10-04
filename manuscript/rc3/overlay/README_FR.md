# HealthGraphBench — RC3, intégration des comparaisons renforcées

**4 octobre 2026 · `manuscript-rc3` · maquette de lecture, non soumise et non approuvée par les auteurs.**
Archive : `HealthGraphBench_LaTeX_RC3.zip`; racine : `HealthGraphBench_RC3/`.
Parent RC2.2 conservé intact : SHA-256 `a1731aa9eb02d8f31179adfea62d1d70a168594910aa2002780aa66e8f83c4f9`.
Le français a été stabilisé avant la traduction anglaise fidèle; les preuves de compilation, concordance et lecture RC3 sont dans `verification/rc3/`.

## Documents et résultats

- `main_fr.pdf`, `main_en.pdf` : méthodes, résultats et limites sur MAUDE, inspections CMS et Medicare Part D; tableaux historiques distingués des nouveaux ajustements Q2.
- `supplement_fr.pdf`, `supplement_en.pdf` : S1–S11 historiques, S12 grilles/sélection/pertes/ressources, S13 forecast scellé, S14 API et réutilisation, S15 décisions humaines ouvertes.
- `response_reviewers_fr.pdf` : réponse **historique** R6, non réponse au cycle Q2 et non approbation RC3.
- Sources LaTeX, tableaux et figures bilingues; entrées `submission_ios_*.tex` héritées, non compilées et non validées pour une revue choisie.

Les comparaisons Q2 ont utilisé 150 ajustements de validation et 43 refits test déjà exécutés avant RC3. La sélection compare six configurations par famille sur validation 2023, pas des budgets de calcul égaux. Les périodes MAUDE/CMS 2024–2025 et Part D 2024 avaient déjà été consultées : résultats exploratoires.
Le BPR réglé dépasse les heuristiques fixes sur MAUDE et Part D; l'incrément CMS lié aux propriétaires reste faible et variable. Les GraphSAGE Q2 `mean` et `none` retenus passent leurs critères d'apprentissage, avec configurations, dimensions et capacités différentes : aucun effet causal d'agrégation à capacité égale. La perte presque plate D1 est conservée, sans déclarer un bug historique établi. Aucun nouvel IC, bootstrap, fit ou score n'a été calculé pour préparer RC3.

Le forecast Part D scelle des scores pour la publication officielle future des relations de l'année de service 2025. **Aucune cible officielle 2025 ni métrique 2025 n'a été acquise/calculée; aucune évaluation indépendante n'a passé.** L'absence du nœud annuel est attestée seulement aux instants des catalogues capturés. Les NPIs disjoints ne garantissent pas l'indépendance statistique. Les attestations humaines de non-consultation restent `unknown`.
La réutilisation raw–wheel par l'assistant démontre un parcours API réel et un modèle cosine hors paquet, pas une étude réalisée par un humain extérieur. Aucun participant extérieur n'est inventé. ClinicalTrials reste historique et séparé; D2 n'est pas engagé.

## Preuves incluses et archives séparées

- `data/q2/` : protocole exact, rapports JSON et ledgers reçus, chronologie/publication du forecast, index des preuves et des archives externes.
- `data/q2/source_snapshots/index.json` : quatre archives des sources Git réellement consommées (validation MAUDE/Part D, reprise MAUDE, CMS, wheel). `vendor/q2/` et `scripts/q2/` sont le snapshot d'intégration du commit `6b4ae00ebc4b701d757260616ccb0df16f51467b`, pas une réattribution rétroactive des runs.
- `data/q2/reuse/` : wheel exact, driver cosine exécuté et deux checkpoints NPZ du témoin; leurs scores de contrôle après rechargement sont une preuve datée Q2, non une nouvelle exécution RC3.
- `data/post_rc1/`, `verification/post_rc1/`, `vendor/post_rc1/` et les audits RC2 restent historiques. Tous les bytes du parent sont retenus selon `release/parent_payload_RC2_2.json`; les fichiers remplacés sont sous `history/RC2.2/`.
- Les données brutes FDA/CMS, 193 checkpoints des comparaisons et neuf flux complets du forecast **ne sont pas inclus**. Les cinq archives expérimentales distinctes sont identifiées par taille/SHA-256 dans `data/q2/external_archive_registry.json`. Les chemins originaux dans les manifestes ne promettent pas ces fichiers dans le ZIP manuscrit.

## Contrôler le paquet reçu

Depuis la racine extraite, avant modification :

```bash
sha256sum -c SHA256SUMS
python -B scripts/check_review_package.py
```

Le checker RC3 vérifie la conservation des bytes, les tableaux contre les JSON reçus, les structures/nombres bilingues et les empreintes des PDF inspectés. Il ne relance aucun audit scientifique historique. Les anciens checkers et rapports restent datés; celui de RC2.2 est archivé sous `history/RC2.2/scripts/`.

## Compiler ou rendre dans une copie

Avec LaTeX, latexmk, BibTeX et Poppler :

```bash
BUILD=/tmp/hgb-manuscript-rc3-reading-copy
test ! -e "$BUILD" || exit 1
cp -a . "$BUILD"
cd "$BUILD"
python scripts/compile_pdfs.py
python -B scripts/check_review_package.py --skip-manifest --allow-unsealed
```

Une recompilation peut changer les bytes des PDF : le rapport visuel scellé et les anciens SHA ne couvrent pas une nouvelle compilation. `--allow-unsealed` sert seulement au contrôle avant une nouvelle inspection des surfaces.
Le rendu Q2 utilise les dépendances de `requirements-rc3-render.txt`, puis :

```bash
python scripts/render_q2_assets.py --evidence-dir data/q2 --output-root .
```

Cette commande produit six paires de tableaux et deux paires de figures depuis les seuls résultats reçus, sans fit/score/IC. Les étendues min–max des seeds ne sont pas des intervalles de confiance.

## Reproduction scientifique historique

Les commandes C/D1 et du bootstrap apparié restent documentées dans `history/RC2.2/README_FR.md`, ainsi que S6/S11; `scripts/analyze_maude_paired_comparison.py`, `scripts/verify_rc1_replays.py` et leurs inputs conservés ne sont pas relancés dans RC3.
Le recalcul initial GraphSAGE30–voisins comparait les candidats C à l'histoire préparée et aux cardinalités/positifs historiques : les listes historiques complètes n'étaient pas exportées. Les neuf checkpoints C/D1 sont destinés à l'inférence, sans reprise d'entraînement. La réserve RSS de l'audit D1 demeure, sans certification d'un plafond global.
Les commandes des runs Q2 sont documentées en S14 et `scripts/q2/`; toute exécution scientifique exige les inputs bruts externes et une nouvelle destination. Une réexécution du forecast aurait une nouvelle origine; elle ne remplace pas les sorties scellées. L'évaluation différée devra utiliser les scores originaux sans refit et satisfaire les conditions de source et attestations.

## Gates avant soumission

Voir `submission/author_gates_RC3.md`. Identités, affiliations, correspondant, CRediT, financement, conflits, éthique/data-use, déclaration IA, licence/support du manuscrit, revue et consignes officielles nécessitent des décisions et validations humaines. Aucun « aucun », dispense ou approbation n'est inféré.
Le DOI `10.5281/zenodo.22796551` identifie le **benchmark v0.2.0**, pas RC3 ni les ajouts Q2. Aucun nouveau DOI/tag/Zenodo/merge/soumission n'est créé. Aucun journal précis n'est sélectionné; les maquettes FAIA/IOS héritées ne valent pas conformité finale, classement Q2 ou acceptation.
