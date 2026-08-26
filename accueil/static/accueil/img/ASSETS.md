# Assets de la landing

Les fichiers sources fournis en PNG ont été **optimisés** pour les perfs :
photos → JPEG, images transparentes → WebP. Total du dossier : ~320 Ko.

| Fichier                         | Rôle                                   | Format |
| ------------------------------- | -------------------------------------- | ------ |
| `hero.webp`                     | Visuel du hero (3 portraits)           | WebP   |
| `emploi-restauration.jpg`       | Carte « restauration »                 | JPEG   |
| `emploi-batiment.jpg`           | Carte « bâtiment »                     | JPEG   |
| `service-mobilite.jpg`     | Carte « mobilité »                | JPEG   |
| `service-numerique.jpg`         | Carte « numérique »                    | JPEG   |
| `stat-emploi.webp`              | Pictogramme stat emploi                | WebP   |
| `stat-insertion.webp`           | Pictogramme stat insertion             | WebP   |
| `stat-prescripteurs.webp`       | Pictogramme stat prescripteurs         | WebP   |
| `temoignages-illustration.webp` | Illustration guillemet                 | WebP   |

Le fond du hero est un **dégradé CSS** (aucun fichier image) — voir `.hero`
dans `css/main.css`.

## Remplacer un asset

Redépose un fichier au **même nom/format** pour l'écraser. Pour repartir d'un
PNG source, préviens-moi : je le ré-optimise et j'ajuste la référence si le
format change.

Ces fichiers ne sont que le **défaut du code** : un rédacteur peut remplacer
n'importe laquelle de ces images depuis `/edition/`, sans toucher au dépôt —
le fichier posté est alors recadré, réduit et converti, et stocké à part.

Ce que ramène « Revenir au texte du code » dépend de l'image :

- `hero.webp` et `temoignages-illustration.webp` sont des champs à part
  entière (`hero.visual`, `testimonials.illustration`) : leur propre
  « Revenir au texte du code » ramène exactement le fichier listé ici, sans
  toucher au reste de la section.
- `stat-emploi.webp`, `stat-insertion.webp`, `stat-prescripteurs.webp`
  (pictogrammes des indicateurs) et `emploi-*.jpg`/`service-*.jpg` (images
  des cartes de recherche) appartiennent chacune à un élément d'une liste
  (`figures.indicators`, `jobs.cards`, `services.cards`). Il n'existe pas de
  retour au défaut pour une seule de ces images : seul un retour **pour la
  liste entière** est possible, et il annule alors aussi toute autre
  modification faite aux éléments de cette liste.
