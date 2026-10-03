# Contribuer à HealthGraphBench

Le benchmark et le manuscrit sont deux objets versionnés distincts. Les tags
`v0.1.0`, `v0.1.1`, `v0.1.2` et `v0.2.0`, leurs résultats et leurs actifs publiés
restent inchangés. Le paquet manuscrit RC1 n'est ni un nouveau benchmark ni une
acceptation éditoriale ; son DOI n'est pas celui du benchmark.

## Gitflow

| Branche | Origine | Destination | Usage |
|---|---|---|---|
| `main` | Historique stable | — | Versions livrées ; pas de travail direct. |
| `develop` | `main` au démarrage | Une branche `release/…` | Intégration du cycle en cours. |
| `feature/<sujet>` | `develop` | `develop` | Changement scientifique ou fonctionnel borné. |
| `fix/<sujet>` | Branche affectée | `develop`, `release/…` ou `hotfix/…` | Correction non publiée, sans extension du périmètre. |
| `chore/<sujet>` | Branche affectée | `develop`, `release/…` ou `hotfix/…` | Documentation, outillage et conditionnement. |
| `release/<identifiant>` | `develop` | `main`, puis `develop` | Stabilisation ; plus de nouvelles fonctionnalités. |
| `hotfix/<identifiant>` | `main` | `main`, puis `develop` et toute release ouverte | Correction urgente d'une version livrée. |

Noms : minuscules ASCII, chiffres, tirets ; points autorisés pour les versions.
Exemples : `feature/maude-duration-diagnostic`, `fix/temporal-cutoff`,
`chore/consolidation-post-rc1`, `release/manuscript-rc2`, `hotfix/v0.2.1`.
Une seule composante après `/`, pas d'espaces ni de suffixe ambigu.

Chaque PR est revue et fusionnée par **merge commit** (`--no-ff` en local,
**Create a merge commit** sur GitHub). Pas de squash/rebase des branches
partagées, de force-push, de réécriture des tags ou de suppression d'un résultat
historique. Un commit est une unité cohérente ; son message décrit le changement
et, si pertinent, le lot A–F et l'identifiant du run. Ne jamais ajouter en bloc
le travail non lié d'une autre personne.

La CI vérifie les noms et directions des PR avec
[`scripts/check_gitflow.py`](scripts/check_gitflow.py). Elle ne prouve ni
l'origine d'une branche, ni une approbation scientifique, ni la reproductibilité
d'un entraînement. `main` → `develop` est aussi autorisé pour une resynchronisation
explicite ; ce n'est pas une voie de développement vers `main`.

### Base d'intégration et publication

`develop` a été créé depuis le `main` stable du benchmark v0.2.0. L'organisation
initiale a été préparée sur `chore/consolidation-post-rc1`, puis la consolidation
technique A/B a été commitée et publiée sur `feature/post-rc1-verification`.
La PR correspondante cible `develop` et reste soumise à revue ; publication et
CI réussie ne valent pas approbation scientifique ni fusion dans une version livrée.

Sélectionner les seuls fichiers et hunks du lot, faire un commit cohérent sur la
branche de travail, puis publier `develop` et cette branche. Exemple A/B :

```bash
git push -u origin develop
git push -u origin feature/post-rc1-verification
gh pr create --draft --base develop --head feature/post-rc1-verification
```

Les commandes `gh` sont facultatives : les mêmes PR peuvent être ouvertes dans
GitHub. L'espace de consolidation est documenté dans
[`docs/consolidation-post-RC1/`](docs/consolidation-post-RC1/README.md).

### Travail courant

Depuis un arbre propre, après publication de `develop` :

```bash
git fetch origin
git switch develop
git pull --ff-only origin develop
git switch -c feature/maude-duration-diagnostic
```

Modifier uniquement le périmètre annoncé ; conserver les résultats nouveaux
hors des chemins historiques. Avant la PR :

```bash
python -m pip install -e .
python scripts/check_gitflow.py --base develop --head feature/maude-duration-diagnostic
python -m unittest discover -s tests -v
```

Exercer aussi le chemin modifié : une réussite de tests seule ne démontre pas
une analyse scientifique. Consigner la commande, l'environnement et le résultat
observé dans la PR et le journal du lot. Commiter les seuls fichiers concernés,
puis publier et ouvrir la PR :

```bash
git push -u origin feature/maude-duration-diagnostic
gh pr create --base develop --head feature/maude-duration-diagnostic
```

Après revue et CI, fusionner par merge commit. Une branche de travail ordinaire
peut être supprimée après fusion ; une release/hotfix doit d'abord revenir dans
toutes les branches concernées.

### Release et hotfix

1. Depuis `develop` à jour, ouvrir `release/<identifiant>` quand le périmètre est
   figé. N'y accepter que corrections, documentation, conditionnement et retours
   de hotfix. Pour une correction publiée urgente, partir de `main` et ouvrir
   `hotfix/<identifiant>`.
2. Vérifier les critères de fin du lot concerné, les nouveaux manifestes et leurs
   empreintes. Les sorties de vérification vont dans un nouveau répertoire ;
   aucune ancienne release n'est régénérée en place. Pour le manuscrit, appliquer
   aussi la [checklist de soumission](docs/consolidation-post-RC1/submission_checklist.md).
3. Publier la branche et ouvrir une PR vers `main`. Fusionner seulement après
   revue et CI par merge commit. Noter le SHA exact du merge approuvé.
4. Ouvrir une PR de la **même branche** vers `develop` et la fusionner par merge
   commit. Pour un hotfix pendant une stabilisation, ouvrir aussi une PR vers la
   release active : sa future livraison ne doit pas perdre la correction.
5. Créer un tag annoté sur le **SHA approuvé dans `main`**, pas sur un `HEAD`
   courant ou un `origin/main` susceptible d'avoir avancé. Publier ce tag et les
   actifs versionnés avec leurs empreintes. Ne supprimer la branche source
   qu'après tous les retours ; ne pas activer la suppression automatique avant eux.

Tags du benchmark : `v<version>`, avec cohérence `pyproject.toml`, citation et
manifestes. Tags du manuscrit : `manuscript-<version-candidate>`, uniquement si le
commit et ses manifestes identifient réellement le paquet publié et ses sources.
Ne pas créer rétrospectivement `manuscript-rc1` sur le code du benchmark : RC1
existe ici comme archive locale conservée, pas comme un snapshot Git du manuscrit.
Une correction du paquet RC1 reçoit RC2 ou un nouvel identifiant explicite.
Un dépôt de manuscrit doit avoir son propre identifiant pérenne ; ne pas lui
attribuer le DOI d'un autre objet.

### Protections GitHub à activer avant le travail partagé

Les fichiers de CI sont versionnés ; **ils ne configurent pas les protections du
serveur**. Un mainteneur doit publier les branches et appliquer ces règles :

- Sur `main` et `develop`, ainsi que `release/**` et `hotfix/**` : PR obligatoire,
  au moins une approbation, résolutions des discussions et check requis
  **Gitflow and tests**. Si aucun second lecteur n'est disponible, l'approbation
  reste un blocage à décider explicitement, pas une validation supposée.
- Interdire force-push et suppression de `main`/`develop` ; limiter les bypass
  administrateurs. Exiger un historique linéaire serait incompatible avec les
  merge commits de ce Gitflow : ne pas activer cette option.
- Autoriser les merge commits ; désactiver squash/rebase pour l'intégration.
  Ne pas supprimer automatiquement les branches de release/hotfix.
- Protéger les tags `v*` et `manuscript-*` contre mise à jour et suppression ;
  réserver leur création aux mainteneurs chargés de la publication.

Tant que ces règles ne sont pas appliquées, la politique est documentée et la CI
est préparée, mais les pushes directs ne sont pas bloqués côté serveur.

## Organisation des fichiers et niveau de preuve

| Emplacement | Contenu | Versionnement |
|---|---|---|
| `healthgraphbench/`, `tests/`, `scripts/`, `configs/` | Code, contrats et contrôles | Git. |
| `docs/ROADMAP_HealthGraphBench.md` | Roadmap scientifique importée | Git, source canonique du plan. |
| `docs/consolidation-post-RC1/` | Pilotage, inventaire, décisions et checklist | Git ; livrables scientifiques ajoutés quand produits. |
| `results/SHA256SUMS_manuscript_rc1` | Empreintes externes des cinq pièces RC1 conservées | Git. |
| `results/generated/manuscript-rc1/` | ZIP et quatre PDF originaux copiés en lecture seule | Local ignoré ; intégrité vérifiable, pas stockage WORM. |
| `results/generated/consolidation-post-RC1/<run-id>/` | Journaux, sorties, checkpoints et compilations nouvelles | Local ignoré ; manifestes compacts dans Git, actifs publiés séparément. |
| `data/raw/` ou un répertoire externe | Instantanés sources FDA/CMS | Jamais ajoutés à Git. |

Pour vérifier les copies RC1 locales depuis la racine du dépôt :

```bash
sha256sum -c results/SHA256SUMS_manuscript_rc1
```

Un clone neuf ne contient pas les cinq binaires ignorés. Copier les fichiers
portant les noms exacts de l'inventaire dans `results/generated/manuscript-rc1/`
depuis une source autorisée, refuser tout écrasement, puis vérifier ces empreintes.
Cette étape ne promet pas de téléchargement permanent : RC1 n'est pas publiée.
Travailler et compiler dans une copie séparée, jamais dans le socle RC1.

Un fichier présent n'est pas un résultat reproduit. Utiliser les statuts de la
roadmap : historique rapporté, rejeu sur sorties conservées, entrées reconstruites,
entraînement réexécuté, confirmation sur données non consultées. Un contrôle
synthétique ne remplace pas MAUDE ; un test déjà consulté ne devient pas intact
après un rejeu. P2 reste limité à une analyse. La règle d'arrêt est une décision
de soumission fondée sur les preuves et le dossier, pas l'attente d'un score ou
d'un quartile plus favorable.
