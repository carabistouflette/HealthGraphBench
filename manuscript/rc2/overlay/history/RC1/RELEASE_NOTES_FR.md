# HealthGraphBench — RC1 du dossier de publication

**Date : 30 septembre 2026.** Identifiant : `manuscript-rc1`. Base scientifique : **R6 après révisions mineures**. Archive : `HealthGraphBench_FAIA_LaTeX_RC1.zip`.

## Nature de cette version

RC1 est la première version candidate du paquet manuscrit, constituée après les corrections de couverture MAUDE et de formulation inductive. Elle rassemble le manuscrit bilingue, les deux suppléments, la réponse au dernier avis, les sources LaTeX et les éléments exécutables. Le benchmark reste à la version 0.2.0 et au commit `b010d5a49eae56837a920b2e30dece41c42c0c44`.

Cette préparation ne publie rien sur GitHub ou Zenodo. Elle ne crée ni tag ni DOI, ne vaut pas acceptation éditoriale et ne modifie pas le dépôt source.

## Changements depuis la R6 corrigée

L'identification RC1 est appliquée aux cinq documents, à leurs métadonnées et aux guides de lecture. `release.json` sépare explicitement l'identité du manuscrit de celle du benchmark. `VERSION`, les notes de version et le manifeste permettent de désigner sans ambiguïté le candidat livré. Les anciens fichiers modifiés sont conservés sous `history/R6_minor/`.

Les résultats, intervalles, tableaux, figures, données préparées, scripts scientifiques et texte scientifique principal sont inchangés. Le manifeste `release/protected_payload.json` enregistre leurs empreintes de départ. Aucun entraînement, score ou nouvel effet scientifique n'est ajouté.

Un script d'orchestration, `scripts/verify_rc1_replays.py`, permet de vérifier en une commande les rejeux existants. Il ne remplace ni ne modifie leurs fonctions scientifiques. Les vérifications RC1 sont conservées séparément dans `verification/rc1/`.

## Gel du candidat

Vérifier `SHA256SUMS` avant modification ou compilation. Construire les PDF dans une copie. Les horodatages et métadonnées d'une recompilation peuvent modifier les octets; seule l'archive distribuée et sa somme externe définissent cette livraison RC1. Tout changement ultérieur doit recevoir un nouvel identifiant, sans remplacer les octets sous le même nom.

Le sous-paquet de données préparées permet des rejeux hors ligne; il ne constitue pas une nouvelle ingestion FDA/CMS. Les attestations historiques de collecte restent qualifiées comme telles. Les vérifications automatisées ne remplacent pas la validation humaine.

## Avant la version de soumission

Les identités, affiliations, contributions et déclarations ne sont pas renseignées ni signées à la place des auteurs. Leur validation scientifique et bibliographique, les modalités du volume/conférence et l'archivage pérenne du paquet restent à finaliser. Les PDF sont des maquettes de lecture; aucune conformité finale au format IOS n'est attestée. Le DOI déclaré du benchmark n'est pas celui de RC1.

**Statut : candidat à relire et à archiver, non soumis et non publié.**
