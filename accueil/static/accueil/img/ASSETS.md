# Assets de la landing

Les fichiers sources fournis en PNG ont été **optimisés** pour les perfs :
photos → JPEG, images transparentes → WebP. Total du dossier : ~320 Ko.

| Fichier                         | Rôle                                   | Format |
| ------------------------------- | -------------------------------------- | ------ |
| `hero.webp`                     | Visuel du hero (3 portraits)           | WebP   |
| `emploi-espacesverts.jpg`       | Carte « espaces verts »                | JPEG   |
| `emploi-aidedomicile.jpg`       | Carte « service à la personne »        | JPEG   |
| `emploi-restauration.jpg`       | Ancienne carte « restauration »        | JPEG   |
| `emploi-batiment.jpg`           | Ancienne carte « bâtiment »            | JPEG   |
| `service-mobilite.jpg`     | Carte « mobilité »                | JPEG   |
| `service-numerique.jpg`         | Carte « numérique »                    | JPEG   |
| `stat-emploi.webp`              | Pictogramme stat emploi                | WebP   |
| `stat-insertion.webp`           | Pictogramme stat insertion             | WebP   |
| `stat-prescripteurs.webp`       | Pictogramme stat prescripteurs         | WebP   |
| `temoignages-illustration.webp` | Illustration guillemet                 | WebP   |

Le fond du hero est un **dégradé CSS** (aucun fichier image) — voir `.hero`
dans `css/main.css`.

## Provenance

Les deux photos des cartes emploi viennent de Pexels, sous [licence
Pexels](https://www.pexels.com/license/) : usage libre, y compris commercial,
sans attribution obligatoire. Le crédit est tout de même porté par le champ
`image_credit` de chaque carte, dans `accueil/sections/jobs.py`.

| Fichier                   | Auteur              | Source                                                        |
| ------------------------- | ------------------- | ------------------------------------------------------------- |
| `emploi-espacesverts.jpg` | Biekir Litovchenko  | <https://www.pexels.com/photo/30467599/>                       |
| `emploi-aidedomicile.jpg` | Jsme MILA           | <https://www.pexels.com/photo/29372733/>                       |

La licence Pexels ne vaut pas autorisation de droit à l'image : elle couvre le
fichier, pas les personnes qu'il montre. Sur `emploi-aidedomicile.jpg` aucun
visage n'est identifiable, ce qui est la raison du cadrage retenu.

Les deux fichiers portent la forme de marque incrustée, comme les visuels
qu'ils remplacent — elle est dans le JPEG, pas en CSS.

## Deux fichiers gardés exprès

`emploi-restauration.jpg` et `emploi-batiment.jpg` ne sont plus référencés par
le code, et **ne doivent pourtant pas être supprimés**. La section emploi est
surchargée en base : la production a changé les textes des cartes mais garde
ces deux chemins d'images. Les effacer afficherait deux images cassées en
ligne. Ils pourront partir une fois la section ré-éditée depuis `/edition/`.

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
