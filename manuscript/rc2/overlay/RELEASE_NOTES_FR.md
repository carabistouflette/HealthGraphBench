# HealthGraphBench — RC2, révision de travail

**2 octobre 2026 • `manuscript-rc2`.** Parent : ZIP RC1 fourni, SHA-256 `2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be`, conservé intact.

## Changements scientifiques documentaires

- Résumés, méthodes, résultats, tableaux complémentaires, discussion et conclusions FR/EN intègrent les analyses MAUDE C et D1 réellement achevées.
- Résultats historiques GraphSAGE à trois époques, tables et intervalles conservés; nouveau C30 présenté séparément, pas comme un test apparié nouveau 3-vs-30.
- D1 : `mean30` conservé de C, seulement `none30` nouvellement entraîné au stade D1; durée commune, capacité 128/64, contrôle non-GNN et perte proche de ln(2) explicités. Aucun effet causal pur, IC nouveau ou confirmation indépendante.
- Nouveau supplément S11 : sélections datées, populations, métriques, pertes/coûts, audits et réserve RSS D1. S12 conserve les gates humains/éditoriaux ouverts.
- Nouvelles figures dérivées des sorties terminées, sans recalcul scientifique ni nouveaux fits; neuf checkpoints d'inférence, CSV/manifestes/audits ajoutés séparément.

## Conditionnement et filiation

`release.json`, `provenance.json`, VERSION, guides et contrôle du paquet identifient RC2. Les métadonnées et contrôles RC1 sont conservés dans `history/RC1`; leurs affirmations restent historiques. Les empreintes des données, tables/figures historiques, bibliographie et outils scientifiques sont protégées dans `release/protected_payload.json`. La réponse R6 est annotée comme historique, non envoyée et sans approbation de RC2. Le contrôle courant ne relance pas les audits scientifiques réussis.

## Limites de livraison et gates

Les gros exports de scores candidats et les archives FDA/CMS brutes ne sont pas inclus; leurs chemins dans les manifestes sont des chemins d'origine. Les neuf checkpoints sont d'inférence, pas de reprise. La disponibilité publique historique reste non démontrée. L'audit RSS D1 n'est pas certifié globalement sous 512 MiB. Les tests déjà consultés restent exploratoires.

RC2 est une révision à relire, pas une soumission ni une version validée par les auteurs. Identités, affiliations, contributions, financement, conflits, éthique, usage des données, déclaration d'IA, références, support et approbations restent à compléter/vérifier. La maquette de lecture n'atteste pas le format final IOS. Aucun nouveau tag, DOI, release de benchmark ou envoi éditorial. Le DOI benchmark n'identifie pas RC2.

## 3 octobre 2026 — anglais traduit depuis la référence française

À la demande de l'utilisateur, le français devient la source canonique. L'anglais est retraduit paragraphe par paragraphe, y compris les résumés, méthodes, résultats, discussion, conclusions, suppléments, légendes et déclarations ; les ajouts anglais sans équivalent français sont retirés et les omissions rétablies. Les indices mathématiques textuels sont traduits sans changer les formules. Les originaux historiques protégés restent intacts ; quatre tables dérivées traduisent leurs intitulés.

Concordance vérifiée sur 26 paires de fichiers : valeurs, formules, structure et références. Les 53 sources françaises LaTeX conservées n'ont pas changé ; le texte extrait des trois PDF français est identique à celui de la livraison précédente. Les nouveaux PDF anglais, compilés et examinés, ont 15 pages pour le manuscrit et 20 pour le supplément. Aucun résultat scientifique ni gate humain ne change. Le nouveau ZIP `HealthGraphBench_FAIA_LaTeX_RC2_traduction_FR.zip` est distinct de la précédente livraison.

