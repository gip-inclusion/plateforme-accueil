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

Le déploiement est automatique à chaque push sur `main`.

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
hauteur de toute iframe portant l'attribut `data-plateforme-accueil`.

Protocole, si vous préférez l'implémenter vous-même — la page émet vers son
parent (`targetOrigin: "*"`, la hauteur n'est pas une donnée sensible), au
chargement puis à chaque changement de mise en page :

```json
{ "source": "plateforme-accueil", "type": "resize", "height": 842 }
```

## Licence

AGPL-3.0-or-later — voir [LICENSE](LICENSE).
