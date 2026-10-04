# HealthGraphBench — audit de la consolidation MAUDE RC2

## Avis

**Avis scientifique favorable pour le positionnement d’article de ressource exploratoire, après deux corrections documentaires mineures.** La réserve portant sur le rapprochement GraphSAGE30–voisins est traitée. Le résultat nouveau est maintenant accompagné d’un appariement explicite, d’un intervalle conditionnel reproductible et d’une présentation proportionnée. Le diagnostic D1 est correctement secondaire. Aucune nouvelle architecture, expérience de durée ou collecte n’est demandée dans cet avis.

Cet avis ne constitue ni une décision éditoriale, ni une approbation des auteurs, ni une validation clinique. Les documents reçus n’ont pas été modifiés.

## Pièces et identité

Archive reçue : `HealthGraphBench_FAIA_LaTeX_RC2_consolidation_MAUDE.zip`.

SHA-256 calculé : `0dabeab0a95cbe956315866ebcb97ce1b6ad780dfeb2e304648e72359910726a`.

La somme calculée correspond au fichier `.sha256` reçu. L’archive comprend 526 fichiers, dont son manifeste ; les **525 entrées du manifeste** correspondent aux octets reçus. Les quatre PDF transmis séparément sont identiques aux quatre PDF scientifiques de l’archive. Les **106 fichiers scientifiques protégés** ont en outre été confrontés directement au ZIP RC1 reçu antérieurement : ils sont inchangés.

Les références documentaires de ce rapport concernent exclusivement les quatre PDF portant `RC2_consolidation_MAUDE`, non les PDF RC2 antérieurs conservés dans la conversation.

## 1. Ce qui a été exécuté pendant cet audit

Les vérifications ont été effectuées dans un répertoire distinct. Aucun modèle de santé n’a été entraîné.

| Vérification | Résultat |
|---|---|
| Contrôleur du paquet | 694 contrôles, tous réussis |
| Tests distribués dans ce ZIP | 61 tests exécutés, 61 réussis |
| Rejeu fourni du nouvel intervalle | Estimation et intervalle identiques ; CSV des contributions et 1 000 tirages reproduits octet pour octet |
| Reconstruction des représentations depuis les neuf checkpoints bruts | 252 400 coordonnées vérifiées ; écart absolu maximal avec les représentations enregistrées : 2,23 × 10⁻¹⁶ (borne arrondie vers le haut) |
| Reconstruction indépendante de l’inférence C30 et de l’heuristique | 2 975 156 scores candidats C30 reconstruits ; hits C30 et voisins concordants pour les 6 370 observations de test |
| Identités et dénominateurs | Pour les 6 370 observations : candidats, empreintes de listes et de positifs, soutien historique et nombres de positifs concordants |
| Bootstrap indépendant | 1 000 tirages refaits par multiplicité des produits ; différence maximale avec les tirages livrés : 2,78 × 10⁻¹⁷ (borne arrondie vers le haut) |
| Compilation | Cinq PDF recompilés ; mêmes paginations et même texte après normalisation des espaces |
| Présentation | Contact sheets des quatre documents scientifiques examinées ; contrôle détaillé de la figure nouvelle et des sections appariées |

Les 61 tests exécutés dans le paquet ne sont pas les 64 tests du dépôt mentionnés dans le README. Le nombre de 64 est celui d’une exécution amont consignée dans les preuves reçues ; cet audit ne la présente pas comme sa propre exécution.

### Indépendance du calcul

Le programme `scripts/independent_primary.py` de cet audit **n’importe aucun module du projet**. Il reconstruit les vecteurs par les transformations et la fonction tanh à partir des états bruts, puis calcule le score scalaire de chaque candidat. Les historiques sont reconstruits à partir des instantanés préparés inclus ; les voisinages de l’heuristique sont calculés par opérations sur des ensembles de bits, et non par l’implémentation du projet. Les classements utilisent le score, le soutien global et l’ordre lexicographique des codes.

Le bootstrap indépendant tire les mêmes positions de produits sous la graine 20261003, convertit les tirages en multiplicités et calcule séparément les deux rapports avant leur soustraction. Les quantiles sont interpolés explicitement sur les valeurs triées, sans appeler l’estimateur d’intervalle fourni.

## 2. Le contraste central est retrouvé

| Prédiction | Liens retrouvés | Liens positifs | Rappel micro à 10 |
|---|---:|---:|---:|
| GraphSAGE sélectionné, 30 époques | 2 775 | 13 174 | 0,210642173979 |
| Fréquence des voisins | 2 530 | 13 174 | 0,192044936997 |
| Différence GraphSAGE30 − voisins | +245 nets | Même dénominateur | **+0,018597236982** |

L’intervalle indépendant retrouvé est **[+0,011975077183 ; +0,025570110820]** après arrondi. Il correspond au tableau 4 du manuscrit français (page 8) et à S11.3 du supplément français (page 19).

Les 2 026 produits sont rééchantillonnés avec tous leurs trimestres. Le dénominateur et le nombre de hits sont recalculés après chaque tirage. Aucun des 1 000 tirages n’est indéfini.

### Vérification trimestrielle

Ces comptes sont issus du recalcul de cet audit, sans nouvel entraînement ni nouvel intervalle trimestriel.

| Trimestre | Produit–trimestres | Positifs | Candidats | Hits C30 | Hits voisins |
|---|---:|---:|---:|---:|---:|
| 2024T1 | 722 | 1 514 | 333 657 | 323 | 311 |
| 2024T2 | 781 | 1 731 | 362 816 | 329 | 304 |
| 2024T3 | 729 | 1 387 | 338 245 | 267 | 249 |
| 2024T4 | 718 | 1 371 | 333 018 | 287 | 272 |
| 2025T1 | 695 | 1 266 | 321 242 | 267 | 240 |
| 2025T2 | 926 | 2 051 | 434 467 | 453 | 394 |
| 2025T3 | 888 | 1 985 | 418 866 | 430 | 359 |
| 2025T4 | 911 | 1 869 | 432 845 | 419 | 401 |

L’avantage ponctuel est retrouvé dans chacun de ces huit trimestres. Les trimestres ne sont pas des répétitions indépendantes et aucun nouveau test de signes n’est effectué.

### Interprétation

Le résultat établit un avantage observé de cette configuration sélectionnée sur cette heuristique, dans ces cohortes, avec une incertitude conditionnelle par produit. Il ne démontre pas la supériorité générale de GraphSAGE, ni que seule la durée provoque l’écart, ni une performance prospective non biaisée. Le manuscrit distingue maintenant correctement l’appariement des prédictions et le contrôle expérimental d’une différence de durée.

## 3. Les trois demandes de consolidation sont traitées

**Rapprochement historique–nouveau.** S11.2 décrit séparément commit d’exécution historique, état source cité et commit C. Le tableau 16 précise les éléments de calcul conservés et l’instrumentation ajoutée. Les preuves de comparaison amont sont reçues, non une nouvelle acquisition de tous les commits dans cet audit. La reconstruction d’inférence et de l’heuristique effectuée ici renforce le raccordement numérique pour les observations de test livrées.

**Hiérarchie des résultats.** Le résultat C30 et son intervalle ont un tableau propre dans l’article, et la courbe de validation y apparaît désormais. Les résultats historiques ne sont pas remplacés. Le résumé ne promet plus l’identification de conditions générales de succès des graphes. D1 n’y occupe plus la place d’une démonstration explicative.

**D1 et synchronisation.** Le texte explique que le contrôle sans propagation apprend encore à partir des arêtes et de BPR, que sa durée lui est imposée et que sa perte presque plate ne valide pas un réglage efficace. La différence de capacité est déclarée sans en faire une explication. Les deux suppléments commencent maintenant par les méthodes, puis la carte des preuves ; ils donnent la même structure pour le code, l’appariement et D1. La définition CMS dans les deux langues porte sur des enregistrements datés d’avant l’inspection, sans garantie de disponibilité publique historique.

Les résultats CMS, Part D et B1/B2 n’ont pas été refaits dans cet audit ciblé ; leur conservation par rapport à RC1 a été vérifiée pour les fichiers protégés. Aucune réserve déjà levée n’est réintroduite par défaut.

## 4. Deux corrections mineures

### E1 — Légende de la figure 2 du manuscrit

Emplacements : français page 9 ; anglais page 8 ; `sections/body_fr.tex` et `sections/body_en.tex`, légende de `fig:duration-main`.

La figure représente **uniquement le rappel micro à 10 en validation**. La légende annonce également la perte de données BPR, qui n’y est pas tracée. Ce n’est pas une erreur de valeurs, mais une discordance entre la légende et son graphique.

Proposition française :

> Exploration complémentaire MAUDE, distincte du benchmark historique : rappel micro à 10 en validation selon la durée de fits indépendants à 0, 3, 10 et 30 époques. La relation observée n’est pas monotone ; seule la durée retenue sur validation est évaluée dans les tests C. Les pertes d’entraînement sont rapportées en S11.

Proposition anglaise :

> Complementary MAUDE exploration, separate from the historical benchmark: validation micro recall at 10 for independent fits at 0, 3, 10, and 30 epochs. The observed relationship is non-monotonic; only the validation-selected duration is evaluated in the C tests. Training losses are reported in S11.

Le titre « grille indépendante / independent grid » pourrait aussi être remplacé par « fits indépendants / independent fits », afin de désigner sans ambiguïté l’absence de warm start, et non une indépendance des données. Ce dernier changement est facultatif.

### E2 — Renvoi à la carte des preuves

La référence bibliographique sur les implémentations conserve « Source map in the accompanying scientific supplement, Section S1 ». Après la réorganisation, **S1 décrit les méthodes et S2 la carte des preuves**. Harmoniser le renvoi : S1 pour les définitions ; S2 pour la carte des preuves. Les deux langues sont concernées par le même fichier bibliographique.

Ces deux corrections n’exigent ni nouvelle donnée, ni réévaluation de score, ni nouvelle méthode.

## 5. Compilation, intégrité et limites

| Document | Pages reçues et recompilées | Texte normalisé identique |
|---|---:|---|
| Manuscrit français | 17 | Oui |
| Manuscrit anglais | 16 | Oui |
| Supplément français | 23 | Oui |
| Supplément anglais | 22 | Oui |
| Réponse historique R6 | 2 | Oui |

Les journaux finaux ne contiennent ni référence indéfinie ni débordement `Overfull`. L’identité bit à bit des PDF recompilés n’est pas revendiquée. Le manifeste du paquet reçu a été contrôlé de nouveau après les opérations et reste intact.

L’amont reste hors de cet audit : acquisition des neuf archives FDA, parsing original, entraînement effectif des nouveaux modèles, comparaison réseau complète des commits et comparaison directe aux flux C/D1 de scores originaux non joints. Les checkpoints permettent cependant de refaire l’inférence et les hits du contraste principal, ce qui a été réalisé ici. La cohérence technique ne prouve pas la disponibilité publique historique de chaque champ, une validation externe ou une utilité clinique.

La validation scientifique des auteurs, leurs identités et déclarations, le support éditorial exact et l’archivage pérenne restent à finaliser. Ils ne sont pas présentés comme réalisés ni comme de nouvelles objections expérimentales.

## Conclusion

**La consolidation demandée est obtenue dans le périmètre exploratoire annoncé.** Le contraste GraphSAGE30–voisins est vérifiable au-delà du seul JSON de résultat : ses contributions, les scores d’inférence reconstruits et le rééchantillonnage concordent. L’apport principal de C et le statut secondaire de D1 sont correctement distingués. Après les deux corrections documentaires, le dossier peut être transmis pour une nouvelle évaluation sans ajouter d’expérience pour répondre à cet avis.

### Fichiers de preuve de cet audit

- `results/audit_summary.json` : résumé machine des contrôles.
- `results/independent_primary.json` : inférence reconstruite, concordances et résultat indépendant.
- `results/independent_bootstrap_draws.json` : les 1 000 tirages indépendants.
- `results/provided_replay/` : résultats du script fourni, exécuté ici.
- `results/direct_RC1_retention.json` : comparaison directe des 106 fichiers protégés avec RC1.
- `logs/tests.log`, `logs/package_check.json`, `logs/compilation.log` : journaux de cette exécution.
- `scripts/independent_primary.py` : programme distinct utilisé pour le recalcul, avec deux arguments : racine du paquet RC2 puis destination nouvelle.

Commande de recalcul indépendant, depuis cet audit extrait :

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/independent_primary.py \
  /chemin/vers/HealthGraphBench_RC2 /chemin/vers/nouveau-resultat-audit
```
