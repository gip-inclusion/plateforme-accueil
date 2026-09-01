# plateforme-accueil

Vitrine server-rendered pour le site **plateforme.inclusion.gouv.fr**, conçue
pour être embarquée en iframe.

> [!IMPORTANT]
> Contamination IA : ce projet a été développé avec l'aide de modèles de langage
> (outils de programmation assistés par IA).

## Développement

Prérequis : [uv](https://docs.astral.sh/uv/).

```bash
uv sync        # installer les dépendances
make dev       # serveur de dev sur http://localhost:8000
make test      # tests
make lint      # ruff
```

La base de données est **optionnelle** : sans `DATABASE_URL`, la page affiche les
textes du code. Pour travailler avec :

```bash
docker compose up -d                    # PostgreSQL sur le port 5434
export DATABASE_URL=postgres://postgres:password@localhost:5434/plateforme_accueil
uv run python manage.py migrate
uv run python manage.py sync_sections   # une ligne par section déclarée
```

Le port 5434 évite les collisions avec les bases d'autres projets ; il se change
avec `POSTGRES_PORT`.

En attendant l'interface d'édition, l'admin Django permet de réordonner, masquer
et surcharger les sections. Il n'est branché que si `ADMIN_ENABLED=1` (implicite
avec `DEBUG=1`) — jamais en production tant que l'authentification n'est pas en
place :

```bash
uv run python manage.py createsuperuser
make dev     # puis http://localhost:8000/admin/
```

Les images téléversées par les rédacteurs (`Illustration`) sont stockées sur un
bucket S3, configuré par les variables d'environnement `AWS_STORAGE_BUCKET_NAME`,
`AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID` et
`AWS_SECRET_ACCESS_KEY` ; il faut les cinq pour que le bucket soit utilisé, sinon
la page se contente des illustrations du code et l'interface refuse le
téléversement. Pour tester le téléversement en local sans bucket, sans jamais le
faire dépendre de `DEBUG` :

```bash
export LOCAL_UPLOADS_ENABLED=1   # stocke sur disque, sert /media/ en dev
```

`LOCAL_UPLOADS_ENABLED` ne doit **jamais** être positionnée sur un conteneur
déployé : elle sert les fichiers via `django.views.static.serve`, que Django
documente comme impropre à la production, et le disque du conteneur est
éphémère — tout fichier stocké ainsi disparaît au prochain déploiement.

Quand un rédacteur remplace une image depuis `/edition/`, le fichier posté est
recadré au format déclaré, réduit à la largeur utile de l'image sur la page,
converti en WebP et nommé d'après le hachage de son contenu. Deux
conséquences : un même fichier reposté deux fois ne crée jamais de doublon, et
le nom ne change jamais — le fichier peut donc être mis en cache
indéfiniment. Sans stockage durable configuré (ni bucket, ni
`LOCAL_UPLOADS_ENABLED`), l'interface n'offre simplement pas le
sélecteur de fichier.

Sans base de données, `make test` saute 141 tests sur 239 (édition,
téléversement, opérations sur les listes) : il vérifie seulement que la page
s'affiche, jamais qu'on peut la modifier. Pour une vérification complète,
lancer la suite avec `DATABASE_URL` positionnée.

Le déploiement est automatique à chaque push sur `main` ; il applique les
migrations avant de basculer la nouvelle révision, et ne fait rien de ce côté
si aucune base n'est configurée.

## Structure de la page

La page est une suite de sections. `index.html` n'est qu'une boucle ; le HTML
vit dans `accueil/templates/accueil/sections/`, un fichier par section.

Chaque section se déclare dans `accueil/sections/<key>.py` :

```python
@registry.register
class Testimonials(SectionType):
    key = "testimonials"
    label = "Témoignages"
    position = 70  # espacée de 10, pour insérer facilement
    template = "accueil/sections/testimonials.html"
```

Les textes sont écrits en dur dans le gabarit, et c'est très bien ainsi.

Pour qu'un texte devienne modifiable sans toucher au code — plus tard, depuis
une interface d'édition — on le déplace dans un formulaire, où sa valeur
`initial` reste la valeur affichée :

```python
    class Form(forms.Form):
        note = forms.CharField(label="Note sous la recherche", initial="Recherche libre…")
```

```html
<p class="hero__note">{{ content.note }}</p>
```

Pas de migration, rien à reprendre. Tout le contenu des sections est déclaré
ainsi, y compris les listes répétables (cartes, raccourcis, étapes, témoignages)
via `ListField`. Seule la mécanique de recherche du héros reste du code.

Avec une base, chaque section a une ligne qui porte son ordre, sa visibilité et
ses écarts de texte — une ligne vierge rend exactement le code. Sans base, ou si
elle est injoignable, la page rend les textes du code. Les réglages sont relus
au plus toutes les 30 secondes.

## Édition

L'interface d'édition est sur `/edition/` : le plan de la page, pour réordonner,
masquer et ouvrir chaque section. Elle n'est jamais embarquable et demande un
compte du groupe rédaction.

En local, sans ces variables, `DEBUG=1` suffit : `createsuperuser` puis
`/edition/`.

Une liste répétable (cartes, raccourcis, étapes…) s'édite sur une planche, à
même l'écran de la section : chaque élément y est montré en entier, jamais en
résumé. Ajouter, modifier, dupliquer, déplacer et supprimer sont des actions
de formulaire ordinaires, sans JavaScript — ouvrir un élément mène à un écran
dédié avec ses propres champs, y compris son image le cas échéant. Une liste
imbriquée dans un élément (les étapes d'un profil, par exemple) reste éditée
comme du JSON brut : c'est un plancher, pas une cible.

## Mesure d'audience

Le Tag Manager Matomo est chargé pour toutes les pages
(`accueil/static/accueil/js/matomo.js`). En plus des pages vues,
`analytics.js` publie un événement par interaction avec une section.

Le repère est posé dans les gabarits, sur l'élément cliquable :

```html
<a class="pastille-lien" href="…"
   data-matomo-category="emplois" data-matomo-action="raccourci"
   data-matomo-name="Industrie">Industrie</a>
```

Au clic (ou à l'envoi, pour un `<form>`), le script pousse un événement Matomo
ordinaire :

```js
window._paq.push(["trackEvent", "emplois", "raccourci", "Industrie"]);
```

`_paq` est la file du traqueur, pas la couche de données du Tag Manager : rien
à déclarer dans le conteneur, un nouveau repère est mesuré dès qu'il est dans un
gabarit. Le traqueur n'existant qu'une fois le consentement transmis par l'hôte,
la file attend jusque-là et rien ne part avant.

| Catégorie | Actions mesurées |
| --- | --- |
| `hero` | `onglet`, `recherche` |
| `emplois`, `services` | `raccourci`, `carte`, `voir-tout` |
| `accompagnateurs` | `recherche` |
| `pour-qui` | `onglet`, `inscription` |
| `modale-ville` | `recherche` |

Les deux attributs `category` et `action` vont toujours ensemble — un élément
qui n'en porte qu'un n'est jamais mesuré, et un test le vérifie.

## Embarquer la page en iframe

Le tag recommandé côté site hôte :

```html
<iframe
  src="https://<URL-DE-LA-VITRINE>/"
  title="La plateforme de l'inclusion"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-forms allow-scripts allow-top-navigation-by-user-activation"
  style="width: 100%; height: 600px; border: 0;"
  data-plateforme-accueil
></iframe>
```

Chaque jeton du `sandbox` est nécessaire, et la liste s'arrête là :

- `allow-forms` — **toute la recherche du héros est un formulaire**. Sans ce
  jeton l'iframe en bloque purement et simplement la soumission, et la
  recherche ne fonctionne pas.
- `allow-scripts` — l'autocomplétion des villes et le report de hauteur. La
  page reste utilisable sans, en dégradé.
- `allow-top-navigation-by-user-activation` — les recherches et les cartes
  ouvrent leur destination dans la fenêtre du haut (`target="_top"`), sur un
  geste du visiteur.

`allow-same-origin` est **délibérément absent** : combiné à `allow-scripts`, il
permettrait à la page embarquée de se soustraire au bac à sable. La page vit
donc dans une origine opaque, et les ressources qu'elle appelle sont servies
avec `Access-Control-Allow-Origin`.

Seuls certains domaines sont autorisés à embarquer la page (CSP
`frame-ancestors`) : `*.inclusion.gouv.fr`, `*.inclusion.beta.gouv.fr`,
`*.cleverapps.io`, `*.scalingo.io`.

Un hôte absent de cette liste s'ajoute **par déploiement**, sans toucher au
code, avec `CSP_EXTRA_FRAME_ANCESTORS` (origines séparées par des virgules) :

```
CSP_EXTRA_FRAME_ANCESTORS=http://localhost:8000,http://localhost:8080
```

C'est la voie à prendre pour développer l'embarquement depuis son poste contre
la page **déployée** : on l'ouvre sur la recette, jamais sur la production. Y
ajouter `localhost` en dur reviendrait à laisser n'importe quelle page servie
sur la machine d'un visiteur encadrer la page de production, pour la commodité
d'un poste de développement.

En local (`DEBUG=1`), `localhost` et `127.0.0.1` sont déjà autorisés sur tous
les ports : rien à poser pour embarquer une vitrine qui tourne elle aussi en
local.

### Ajustement automatique de la hauteur (optionnel)

La page fonctionne sans JavaScript : l'iframe garde alors la hauteur fixée par
le site hôte (`height`). Pour que l'iframe s'adapte à la hauteur réelle du
contenu, inclure le script hôte fourni :

```html
<script src="https://<URL-DE-LA-VITRINE>/static/accueil/js/iframe-embed.js" defer></script>
```

Le script écoute les messages `postMessage` émis par la page et ajuste la
hauteur de toute iframe portant l'attribut `data-plateforme-accueil`. La
hauteur suivant alors le contenu, l'ascenseur interne disparaît de lui-même.
Ne mettez jamais `scrolling="no"` sur l'iframe : sans JavaScript (ou si un
message se perd), l'ascenseur reste le seul moyen d'accéder au contenu qui
dépasse la hauteur de repli.

Le script publie aussi, en sens inverse, la portion de l'iframe réellement
visible à l'écran. L'iframe faisant la hauteur de son contenu, son propre
viewport couvre toute la page : sans cette information, une fenêtre modale se
centrerait au milieu du document plutôt que devant le visiteur. C'est un
confort, pas une dépendance — un hôte qui ne publie rien obtient le
centrage par défaut.

Protocole, si vous préférez l'implémenter vous-même.

La page émet vers son parent (`targetOrigin: "*"`, la hauteur n'est pas une
donnée sensible), au chargement puis à chaque changement de mise en page :

```json
{ "source": "plateforme-accueil", "type": "resize", "height": 842 }
```

L'hôte émet vers l'iframe, au scroll et au redimensionnement (au plus une fois
par frame, et seulement si la valeur a changé) :

```json
{ "source": "plateforme-accueil", "type": "viewport", "top": 320, "height": 700 }
```

L'hôte émet aussi, une fois que le visiteur a accepté la mesure d'audience chez
lui et jamais avant :

```json
{ "source": "plateforme-accueil", "type": "analytics", "consent": true,
  "visitorId": "1a2b3c4d5e6f7a8b", "siteId": 117 }
```

La page adopte cet identifiant de visiteur et ce site : ses hits rejoignent la
visite déjà en cours chez l'hôte, dans le site Matomo de l'hôte, au lieu d'en
ouvrir une seconde ailleurs. Le `siteId` transite plutôt que d'être figé dans le
container, pour qu'un environnement de recette n'écrive jamais dans le site de
production.

Le tag Matomo du container se déclenche sur l'événement `host-analytics` émis à
la réception de ce message, et non sur la page vue : le traqueur sérialise sa
requête dès que le tag se déclenche, donc une identité arrivée après coup ne
corrigerait plus la page vue. Le container exige en outre le consentement.

Le même message avec `"consent": false` **retire** le consentement : la page
appelle `forgetConsentGiven` et cesse de mesurer. L'hôte doit l'émettre si le
visiteur revient sur son choix — une iframe survit largement au clic qui révoque,
et sans ce message elle continuerait de mesurer quelqu'un qui a demandé l'arrêt.
Un consentement redonné ensuite reprend la mesure sans recompter la page vue.

L'hôte peut republier le message autant qu'il veut : une répétition est sans
effet. C'est ce qui lui permet de le renvoyer à chaque message reçu de l'iframe,
et de couvrir ainsi le cas où le consentement précède le chargement de celle-ci.

Un hôte qui n'implémente pas le protocole obtient donc une page non mesurée —
c'est voulu, la vitrine n'a pas de bandeau de consentement à elle.

Côté container, il reste à créer une variable de couche de données
`hostSiteId`, un déclencheur sur l'événement `host-analytics`, et à y brancher
la balise Matomo à la place de la page vue — dans l'interface du Tag Manager,
comme pour `accueil.interaction` plus haut. Tant que ce n'est pas fait,
l'événement poussé ici ne déclenche rien.

`top` et `height` décrivent la bande visible **dans le repère du document
embarqué**, c'est-à-dire `max(0, -rect.top)` et la hauteur restant dans la
fenêtre, où `rect` est le `getBoundingClientRect()` de l'iframe. Le document
embarqué ne scrollant pas, il n'y a pas d'autre décalage à réconcilier.

## Licence

AGPL-3.0-or-later — voir [LICENSE](LICENSE).
