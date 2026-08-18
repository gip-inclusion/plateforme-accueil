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

Le déploiement est automatique à chaque push sur `main`.

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

Pas de migration, rien à reprendre : les autres textes restent en dur. Un seul
champ est ouvert pour l'instant (`hero.py`), à titre d'exemple.

Avec une base, chaque section a une ligne qui porte son ordre, sa visibilité et
ses écarts de texte — une ligne vierge rend exactement le code. Sans base, ou si
elle est injoignable, la page rend les textes du code. Les réglages sont relus
au plus toutes les 30 secondes.

## Embarquer la page en iframe

Le tag recommandé côté site hôte :

```html
<iframe
  src="https://<URL-DE-LA-VITRINE>/"
  title="La plateforme de l'inclusion"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
  style="width: 100%; height: 600px; border: 0;"
  data-plateforme-accueil
></iframe>
```

Seuls certains domaines sont autorisés à embarquer la page (CSP
`frame-ancestors`) : `*.inclusion.gouv.fr`, `*.inclusion.beta.gouv.fr`,
`*.cleverapps.io`, `*.scalingo.io`.

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

Protocole, si vous préférez l'implémenter vous-même — la page émet vers son
parent (`targetOrigin: "*"`, la hauteur n'est pas une donnée sensible), au
chargement puis à chaque changement de mise en page :

```json
{ "source": "plateforme-accueil", "type": "resize", "height": 842 }
```

## Licence

AGPL-3.0-or-later — voir [LICENSE](LICENSE).
