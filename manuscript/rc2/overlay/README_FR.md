# HealthGraphBench — révision de travail RC2

**2 octobre 2026 • `manuscript-rc2` • non soumise, non approuvée par les auteurs.**
Archive : `HealthGraphBench_FAIA_LaTeX_RC2_traduction_FR.zip`; racine : `HealthGraphBench_RC2`.
RC1 fournie est conservée intacte (SHA-256 `2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be`).

**Révision linguistique du 3 octobre 2026.** Le français est la référence ; le manuscrit et le supplément anglais sont ses traductions fidèles, non des réécritures indépendantes. Les sources scientifiques françaises restent inchangées. Titres, paragraphes, légendes, formules, résultats, limites et déclarations sont conservés ; syntaxe et ponctuation numérique sont adaptées à l'anglais. La concordance de 26 paires de fichiers est documentée dans `verification/rc2_translation/language_concordance.json`. Les PDF anglais traduits ont 15 et 20 pages. Le ZIP RC2 précédent reste une livraison historique distincte.

## Contenu et portée

- `main_fr.pdf`, `main_en.pdf` : manuscrits intégrant C et D1; résultats historiques conservés séparément.
- `supplement_fr.pdf`, `supplement_en.pdf` : méthodes et provenance; S10 garde les inventaires B1/B2 historiques, S11 documente C/D1 et la réserve RSS de l'audit D1; éléments ouverts en S12.
- `response_reviewers_fr.pdf` : réponse **historique** à l'avis R6, annotée comme telle; pas de nouvel avis, d'approbation RC2 ni d'envoi.
- Sources LaTeX, tableaux, figures et bibliographie; auteurs/affiliations encore à renseigner dans les fichiers `metadata_*.tex`.
- `data/post_rc1/` : manifestes A/B/C/D1, CSV, métriques exactes et neuf checkpoints d'inférence. `verification/post_rc1/` garde protocoles, audits et rapports datés.
- `vendor/post_rc1/` : sources du noyau et des contrôleurs pour inspection; ce n'est pas une distribution autonome d'entraînement.
- `history/RC1/` : métadonnées et contrôle de conditionnement hérités; leurs statuts restent historiques.

C sélectionne 30 époques sur validation 2023 avant ses tests; R@10 groupé 2024–2025 : 2775/13174 = 0,210642. Le test historique à trois époques n'est pas réentraîné dans C. D1 réutilise `mean30` C et ajoute seulement `none30` : 469/13174 = 0,035600, contraste +0,175042. `none` est self-only non-GNN, avec 64 contre 128 coefficients actifs de transformations partagées et perte proche de ln(2). Ce n'est pas un effet causal pur de l'agrégation.

Toutes ces périodes étaient déjà consultées : analyses exploratoires, sans confirmation indépendante ni nouvel intervalle. Aucune expérience, graine, optimisation, D2, ingestion brute ou nouvel audit exhaustif n'est lancé pour préparer RC2.

## Vérifier la livraison

Depuis la racine extraite, avant toute modification :

```bash
sha256sum -c SHA256SUMS
python scripts/check_review_package.py
```

Le contrôle vérifie l'identité, les bytes historiques protégés, les ratios et contrastes conservés, les checkpoints et les PDF. Il ne relance ni fit ni audit scientifique réussi. `release/protected_payload.json` protège les données, anciennes tables/figures, bibliographie et outils scientifiques; le texte principal est volontairement révisé.

## Compiler dans une copie

Avec LaTeX, `latexmk`, BibTeX et Poppler :

```bash
BUILD="/tmp/hgb-manuscript-rc2-build"
test ! -e "$BUILD" || exit 1
cp -a . "$BUILD"
cd "$BUILD"
python scripts/compile_pdfs.py
python scripts/check_review_package.py --skip-manifest
```

Les cinq PDF utilisent la **maquette de lecture**, pas un format de soumission approuvé. Les entrées `submission_ios_*.tex` sont préparées mais non compilées/validées pour un support final. Une recompilation change potentiellement les octets des PDF; ne pas lui appliquer les anciennes sommes de livraison.

## Reproductibilité et limites

Les compacts historiques et instantanés MAUDE préparés restent inclus. Les gros flux de prédictions candidates C/D1 et les archives FDA/CMS brutes **ne sont pas inclus**. Les chemins dans les manifestes C/D1 désignent les exécutions d'origine dans le dépôt, pas des fichiers tous présents dans ce ZIP. Les neuf checkpoints servent à l'inférence, sans reprise d'entraînement; les analyses C/D1 ne deviennent pas des réacquisitions brutes.

L'audit D1 conserve deux mesures RSS discordantes : VmHWM 118292480 B et ru_maxrss 571580416 B, sans lecture initiale. Les trois phases scientifiques respectent séparément leurs plafonds; aucun plafond RSS global de l'audit n'est certifié. Le probe non médical `exec` montre une différence possible de portée, pas la cause certaine du pic.

Les rejeux historiques restent accessibles via `scripts/verify_rc1_replays.py`; le nom indique leur périmètre RC1, pas la version du paquet courant. Ils ne sont pas relancés pour confirmer des résultats déjà vérifiés.

## Avant soumission

Validation humaine des résultats/références, identités, affiliations, correspondant, contributions, financement, conflits, éthique, conditions d'usage, déclaration d'assistance par IA, support et consignes officielles restent à obtenir. Aucune déclaration négative ni acceptation n'est présumée. Le DOI `10.5281/zenodo.22796551` identifie le **benchmark v0.2.0**, pas RC2. Aucun nouveau tag, DOI ou dépôt de publication n'est créé. Conserver RC1 et RC2 distinctes; une correction ultérieure exige une nouvelle révision et provenance.
