# HealthGraphBench — première version candidate du dossier de publication

**RC1 • 30 septembre 2026 • identifiant `manuscript-rc1`.** Base scientifique : R6 après application des deux révisions mineures. Le texte scientifique principal, les résultats, les intervalles, les tableaux, les figures, les entrées préparées et le code de calcul sont conservés. Le changement porte sur l'identification et le conditionnement de la livraison.

Archive : `HealthGraphBench_FAIA_LaTeX_RC1.zip`. Dossier racine : `HealthGraphBench_RC1`. Identité : `release.json`; filiation et opérations : `provenance.json`; statut scientifique conservé : `data/revision_status_R6.json`.

**RC1 désigne le paquet manuscrit, pas le benchmark v0.2.0.** Aucun tag distant, GitHub Release, dépôt Zenodo ou DOI n'a été créé. Les noms d'artefacts R2–R6 sont conservés afin de ne pas casser la provenance. Aucun statut d'acceptation éditoriale n'est revendiqué.

## Documents

| Pièce | Usage |
|---|---|
| `main_fr.pdf` / `main_en.pdf` | Manuscrit français / anglais. |
| `supplement_fr.pdf` / `supplement_en.pdf` | Suppléments scientifiques; S10 contient les effectifs d'entraînement et la couverture MAUDE. |
| `response_reviewers_fr.pdf` | Réponse aux deux corrections mineures de l'avis R6, à valider par les auteurs. |
| `RELEASE_NOTES_FR.md` / `RELEASE_NOTES_EN.md` | Périmètre de RC1, conservation et étapes éditoriales restantes. |
| `verification/rc1/` | Vérifications exécutées lors du conditionnement; les contrôles historiques restent séparés. |

Les sources LaTeX correspondantes sont à la racine; `sections/`, `tables/`, `figures/` et `references.bib` complètent la compilation. Les champs d'auteur sont dans `metadata_fr.tex` et `metadata_en.tex`. **Ils restent à renseigner : RC1 n'est pas encore une version administrativement prête à soumettre.**

## Vérifier avant de modifier

Environnement d'analyse consigné dans `requirements-review.txt` et `verification/rc1/environment.json`; Poppler fournit `pdftotext` et `pdfinfo`. Depuis la racine extraite :

```bash
sha256sum -c SHA256SUMS
python scripts/check_review_package.py
python -m unittest discover -s tests -v
```

Le manifeste couvre les fichiers livrés, pas les PDF d'une future recompilation. `release/protected_payload.json` fixe les empreintes du contenu scientifique protégé par rapport à l'archive R6 de départ. Les tests ne remplacent ni les données ni la responsabilité des auteurs.

## Rejouer les analyses conservées hors ligne

Le nouvel outil d'orchestration emploie les scripts scientifiques inchangés. Il rejoue les deux bootstraps, les métriques CMS, les descriptifs MAUDE et la synthèse de couverture, puis compare les sorties aux références. Aucun modèle de santé n'est entraîné.

```bash
OUT="/tmp/hgb-manuscript-rc1-replay"
test ! -e "$OUT" || exit 1
python scripts/verify_rc1_replays.py --output-dir "$OUT"
```

Le répertoire doit être nouveau et extérieur au paquet. `checks.json` distingue les comparaisons numériques à tolérance absolue `1e-12` des cinq sorties MAUDE reproduites octet pour octet. Les horodatages des nouveaux rejeux restent distincts. Les compacts CMS, MAUDE et Part D sont dans `data/real_R4/`; les instantanés préparés MAUDE et les descripteurs sont dans `data/real_R6/maude_B/`.

Pour rejouer seulement B1/B2 :

```bash
OUT="/tmp/hgb-manuscript-rc1-maude-B"
test ! -e "$OUT" || exit 1
python scripts/audit_maude_B.py replay   --input-dir data/real_R6/maude_B   --output-dir "$OUT"
```

**Limite.** Ce rejeu part des contributions et instantanés préparés livrés. Il ne réacquiert pas les archives FDA/CMS, ne relance pas leur parseur original, ne vérifie pas à nouveau les sources distantes et ne reconstruit pas des checkpoints. La collecte historique R6 est documentée dans `verification/real_R6/` et la provenance du bundle; elle ne devient pas une opération RC1. Le guide `README_MAUDE_B_FR.md` décrit séparément cette collecte amont.

## Compiler dans une copie

Avec une distribution LaTeX disposant de `latexmk`, BibTeX et des paquets employés :

```bash
BUILD="/tmp/hgb-manuscript-rc1-build"
test ! -e "$BUILD" || exit 1
cp -a . "$BUILD"
cd "$BUILD"
python scripts/compile_pdfs.py
python scripts/check_review_package.py --skip-manifest
```

La recompilation peut changer les octets du PDF sans changer son contenu. Ne pas appliquer le manifeste de livraison aux PDF reconstruits comme s'il s'agissait des mêmes fichiers. Les entrées `submission_ios_fr.tex` et `submission_ios_en.tex` sont conservées mais non compilées ici; les PDF de RC1 utilisent la maquette de lecture.

## Gel et diffusion

Conserver le ZIP RC1 et sa somme SHA-256 externe. Ne pas remplacer silencieusement un fichier RC1 : un correctif ultérieur doit recevoir RC2 ou un autre identifiant explicite. Transmettre le paquet entier avec les PDF pour permettre la vérification. Le tag `manuscript-rc1` est uniquement un nom proposé pour une publication future; il n'a pas été créé.

Avant soumission : validation scientifique et bibliographique humaine, identités et affiliations, contributions, financements, conflits, position éthique, conditions d'utilisation et assistance réellement reçue, choix du volume et de ses instructions, puis archivage pérenne. Aucune déclaration négative ou dispense n'est supposée. Le DOI déclaré du benchmark n'identifie pas cette archive manuscrit.
