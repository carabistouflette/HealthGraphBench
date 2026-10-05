## Objet et lot de la roadmap

Changement, motif et lot A–F concerné, ou hors cycle explicitement justifié.

## Preuves et vérification

Commandes réellement exécutées, résultats observés et limites. Pour un changement scientifique : protocole, configuration, entrées, identifiant de run et sorties conservées.

## Contrôle avant fusion

- [ ] Branche cible conforme à [Gitflow](https://github.com/carabistouflette/HealthGraphBench/blob/develop/CONTRIBUTING.md#gitflow) : une feature vise `develop` ; fix/chore peuvent aussi viser une release/hotfix en stabilisation, jamais `main`.
- [ ] RC1, tags, résultats historiques et actifs publiés non remplacés.
- [ ] Nouvelles sorties isolées ; manifestes, provenance et documentation mis à jour.
- [ ] Résultats historiques, rejeux, reconstructions, entraînements et confirmation indépendante distingués.
- [ ] Contrôle synthétique non présenté comme un diagnostic MAUDE ; périodes déjà consultées non présentées comme intactes.
- [ ] Aucune nouvelle donnée brute, checkpoint ou sortie volumineuse ajoutée dans Git.
- [ ] Vérification du chemin modifié consignée ; CI passée ; revue effectuée.

## Pour une release ou un hotfix

Tag prévu, commit à publier, empreintes, limites connues et décision des auteurs si soumission. Identifier les PR de retour vers `develop` et, pour un hotfix, vers toute release en stabilisation ; ne pas supprimer la branche avant ces retours.
