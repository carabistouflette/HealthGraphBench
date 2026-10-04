# RC3.1 — assemblage distinct, preuves réelles et scellement

RC3.1 est une révision manuscrite pour des expériences ciblées exploratoires sur les périodes 2023–2025 déjà consultées. La question est l'information relationnelle incrémentale par rapport à l'historique individuel et à la popularité, et la complexité nécessaire pour l'exploiter ; ce n'est pas un nouveau classement général de modèles. Ce guide n'annonce aucun résultat et ne ferme aucune gate scientifique ou éditoriale.

Le français fourni par le responsable de l'analyse est canonique ; l'anglais est sa traduction fidèle. Les approbations des auteurs, déclarations, licences et conformité à une revue restent inconnues. L'évaluation temporelle indépendante et la reproduction externe humaine ne sont pas réalisées. Le DOI `10.5281/zenodo.22796551` reste celui du benchmark **v0.2.0**, pas de RC3.1. Aucune soumission, publication Zenodo, fusion ou étiquette n'est effectuée par ces outils.

## Conservation et dépendances

Le seul parent consommé est le ZIP RC3 de SHA-256 `6cc3005a46ac2c906daf42a7c27781dfae8953b5eaa78c874e41b622014dd402`. Chaque fichier parent est conservé octet pour octet dans `history/RC3/`, y compris les origines des résultats historiques et des intervalles. RC3 et RC2.2 ne sont jamais modifiés. Le contrôle parent est exclusivement un contrôle de consommation/conservation de bytes, pas une réexécution des audits scientifiques.

Le nouveau manuscrit principal inclut les tables historiques MAUDE/CMS/Part D et la table historique complète des intervalles, avec leurs légendes et origines RC3, dans sa section de contexte historique. Le supplément réutilise les tables C/D1/Q2 sans recalcul. Les définitions de tâches, filtres de cohortes et limites des données doivent être expliqués par le texte scientifique fourni ; les sources historiques intégrales restent accessibles, sans disparition silencieuse des chiffres.

Python 3.11 ou plus récent ; Matplotlib 3.7 ou plus récent pour les figures uniquement. La compilation utilise le `scripts/compile_pdfs.py` du parent, adapté aux quatre documents RC3.1, et nécessite latexmk, BibTeX et les packages LaTeX du parent. `pdfinfo` (Poppler) est requis au scellement pour confronter le nombre réel de pages au rapport visuel. Aucun outil n'entraîne, ne score ni ne recalcule d'intervalle.

## Entrées scientifiques réelles

`--run-root` désigne le répertoire réel terminé par `healthgraphbench.rc31.run`, par exemple `results/generated/rc31-cycle-20261004/experiment-001`. Les fichiers obligatoires à sa racine sont :

- `partd_experiments.json`, `maude_experiments.json`, `cms_experiments.json` ;
- `analysis.json`, `cycle.json` avec `status=completed_exploratory` ;
- `protocol_executed.json`, `source_provenance.json`, `resource_ledger.json`.

Le rendu refuse des données manquantes, une grille/année/graine attendue absente, des entrées incohérentes ou un cycle non terminé. Il n'utilise aucune valeur de secours ni résultat synthétique. Les valeurs nulles effectivement produites pour un dénominateur ou contraste non défini sont représentées par un tiret, sans imputation. Les min–max de graines sont descriptifs et séparés des IC appariés conditionnels aux ajustements fixes ; les IC ne couvrent ni sélection de configuration ni indépendance des périodes/réseaux. La marge 0,01 n'est pas un seuil clinique. CMS reste conditionnel à une inspection. Les liens observés et la charge de propositions n'établissent pas la justesse clinique.

Le renderer écrit les tables FR puis EN, les courbes de rappel/précision selon K et les contrastes par strates prédéfinies. `numeric_records.json` et `plot_records.json` contiennent tous les nombres/points effectivement consommés. `asset_manifest.json` épingle les huit fichiers d'entrée, le renderer, les sources scientifiques consommées et chaque asset. Les ressources, configurations, diagnostics d'apprentissage et tailles d'état sont conservés dans les enregistrements numériques ; une table de temps/paramètres/gates rapporte seulement les champs disponibles.

## Texte fourni par le responsable de l'analyse

Le schéma machine exact est `manuscript/rc31/narrative.schema.json` dans le dépôt et `release/narrative.schema.json` dans le paquet. Aucun champ supplémentaire n'est admis à la racine, dans `fr`/`en` ou dans un objet de section ; les contraintes d'ordre bilingue et de liaison des hashes ci-dessous sont également vérifiées par l'assembleur.

`--narrative-json` est un vrai JSON rédigé **après** l'analyse complète, pas un fichier de démonstration. Il contient :

- `canonical_language`: `fr` ; `english_role`: `faithful_translation` ;
- `analysis_sha256`: SHA-256 des bytes réels de `analysis.json` ;
- `translation_of_fr_sha256`: SHA-256 UTF-8 de `json.dumps(value['fr'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))` ;
- `fr` et `en` : chacun avec `title`, `abstract`, `sections`, `supplement`.

Chaque liste de sections contient des objets `id`, `heading` et **exactement un** champ `paragraphs` (liste non vide de paragraphes textuels, échappés pour LaTeX) ou `latex` (vrai contenu LaTeX non vide, avec formules/citations si nécessaire). Le résumé et le titre sont textuels. Les identifiants et leur ordre doivent être les mêmes en français et en anglais, sans doublons. Les sections principales obligatoires sont `question`, `data`, `methods`, `historical_context`, `results`, `interpretation`, `limits` ; des sections supplémentaires sont possibles. Le supplément doit également contenir du texte scientifique réel. Le contrôle structurel et la liaison des hashes ne certifient pas la fidélité scientifique/linguistique : elle relève de la revue effective du contenu.

Les tables historiques sont insérées automatiquement à la fin du texte `historical_context`. Les tables RC3.1 sont incluses automatiquement ; ne les recopier ni ne les inventer dans le texte. Les titres/gates techniques et les avertissements de périmètre sont ajoutés par le gabarit. Toute prose scientifique, définitions de tâches, cohortes, disponibilité historique, conclusions et interprétation des résultats appartient au texte fourni. `references.bib` est réutilisé du parent pour les citations LaTeX. Des références/citations non résolues interdisent le scellement.

## Registre de sorties complètes et entrées

`--evidence-registry` doit être un JSON réel avec `scope=external_full_outputs_and_inputs`, deux listes non vides `full_outputs` et `inputs`. Chaque entrée a `role`, `path`, `bytes`, `sha256`. Les chemins sont vérifiés sur les fichiers existants à l'assemblage puis conservés sous forme absolue. Les fichiers bruts/TAR ne sont pas copiés dans le ZIP manuscrit.

Exactement une entrée de `full_outputs` a `role=rc31_run` et un `run_prefix` : préfixe du répertoire réel dans le TAR (chaîne vide si ses fichiers sont à la racine). TAR, TAR.GZ/TGZ, TAR.XZ et TAR.BZ2 sont supportés. L'assembleur vérifie les empreintes exactes des huit JSON racine dans ce TAR et écrit `consumed_run_members_sha256`. Ce contrôle de consommation n'ouvre pas les checkpoints pour un nouvel audit ni ne réexécute la science. Les autres entrées peuvent épingler les archives scientifiques historiques réellement réutilisées. `inputs` épingle les fichiers préparés/raw réellement nécessaires, avec leur provenance/scope décrits par les champs additionnels du registre. Ces chemins peuvent devenir indisponibles ailleurs : l'archive est volontairement un paquet de **preuves compactes et chemins externes épinglés**, pas une livraison autonome de toutes les données brutes.

`--source-root` doit exposer les sources scientifiques **effectivement consommées**, aux chemins de `source_provenance.json`, avec les hashes indiqués. Un arbre courant correspondant ou des snapshots exacts conviennent ; aucun contrôle de HEAD global, de nouveaux outils de papier ou de documents utilisateurs n'est imposé. Les snapshots de ces sources sont livrés. Les `result.json`, `worker_status.json` et `supervisor_status.json` de toutes les phases du ledger sont requis et copiés comme preuves compactes.

L'entrée `inputs` de rôle `partd_historical_bpr_selection` est obligatoire et unique. Ses 2 429 octets de métadonnées de sélection effectivement consommées sont copiés sans changement sous `data/reused_inputs/partd_selection.json`, avec empreinte et membre ZIP consignés dans le registre livré. Ce petit JSON ferme l'entrée absente du TAR compagnon ; il ne réentraîne pas BPR et n'ajoute pas rétroactivement de comparateur au forecast. Pour rejouer le protocole, restaurer cette copie au chemin historique indiqué par le registre, avec les autres entrées du TAR et le clone des sources épinglées. Le ZIP du manuscrit seul n'est toujours pas une archive autonome de tous les raw ou fits.

## Commandes complètes — à exécuter seulement avec les vraies entrées

```bash
python -B manuscript/rc31/render_assets.py \
  --run-root results/generated/rc31-cycle-20261004/experiment-001 \
  --output-assets /tmp/hgb-rc31-assets

python -B scripts/build_manuscript_rc31.py assemble \
  --source-zip "$HOME/Downloads/HealthGraphBench_LaTeX_RC3.zip" \
  --output-dir /tmp/hgb-rc31/HealthGraphBench_RC3_1 \
  --run-root results/generated/rc31-cycle-20261004/experiment-001 \
  --assets-dir /tmp/hgb-rc31-assets \
  --narrative-json /chemin/reel/narrative_rc31.json \
  --evidence-registry /chemin/reel/evidence_registry_rc31.json \
  --source-root /chemin/aux/sources-consommees

python -B scripts/build_manuscript_rc31.py compile \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1 --timeout 120

python -B manuscript/rc31/check_package.py \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1
```

Le répertoire d'assets et la racine d'assemblage doivent être nouveaux. `assemble` ne compile pas. `compile` enregistre les hashes des sources/figures/PDF/logs et refuse les boîtes overfull ou références/citations non résolues. Une correction LaTeX avant livraison exige une nouvelle compilation et une nouvelle inspection des quatre PDF ; jamais de simple repin d'un vieux rapport. Les outils `compile`, `seal` et QA peuvent aussi être exécutés depuis `scripts/` du paquet assemblé avec `python -B`.

## Revue visuelle réelle et scellement

Le rapport `--surface-report` est un JSON avec `revision=RC3.1`, `reviewer`, `reviewed_at_utc`, et `documents` contenant exactement les quatre clés `main_fr.pdf`, `main_en.pdf`, `supplement_fr.pdf`, `supplement_en.pdf`. Chaque objet indique `sha256` du PDF réel, `visual_review_completed=true`, `page_count` réel, `reviewed_pages` égal à la liste ordonnée de toutes les pages de 1 à `page_count`, et les listes vides `blank_pages`, `unresolved_references`, `overfull_boxes` après correction. Il faut effectivement inspecter chaque page ; produire ce JSON n'est pas une revue à lui seul.

```bash
python -B scripts/build_manuscript_rc31.py seal \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1 \
  --surface-report /chemin/reel/surface_review_rc31.json \
  --archive-path "$HOME/Downloads/HealthGraphBench_LaTeX_RC3_1.zip" \
  --pdf-output-dir "$HOME/Downloads"

python -B manuscript/rc31/check_package.py \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1 --sealed
```

Le scellement confronte les hashes et nombres de pages réels, les diagnostics actuels, les assets dérivés des JSON et le manifeste complet. Aucune revue manquante/périmée ni référence/boîte overfull non résolue n'est tolérée. Les chemins ZIP, checksum, quatre PDF et manifeste de livraison doivent être nouveaux et extérieurs à la racine. Le ZIP a exclusivement la racine `HealthGraphBench_RC3_1/`. Sorties :

- `HealthGraphBench_LaTeX_RC3_1.zip` et `.zip.sha256` ;
- `HealthGraphBench_RC3_1_manuscrit_FR.pdf` ;
- `HealthGraphBench_RC3_1_manuscript_EN.pdf` ;
- `HealthGraphBench_RC3_1_supplement_FR.pdf` ;
- `HealthGraphBench_RC3_1_supplement_EN.pdf` ;
- `RC3_1_delivery_manifest.json`, à côté de la racine d'assemblage.

Le QA RC3.1 vérifie les dérivations numériques actuelles, les points/assets, les sources consommées, les gates/limites, le ledger, la conservation parent, puis au scellement les quatre revues et l'intégrité. Il n'exécute aucun ancien audit scientifique ni test de repin de prose historique. Une préparation technique prête pour revue n'est pas une validation scientifique indépendante, humaine, d'auteurs ou de revue.
