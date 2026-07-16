# CLAUDE.md — Règles du projet

Vitrine server-rendered pour le site plateforme.inclusion.gouv.fr, embarquée en
iframe. Django 6, sans base de données pour l'instant (des fonctionnalités CMS
arriveront plus tard).

## Règles d'or

### Séparation des responsabilités

HTML, CSS et JS vivent dans des fichiers distincts. Jamais de `<style>` ni de
`<script>` inline, jamais d'attributs `style="…"` ou `onclick="…"`. Les
templates sont dans `accueil/templates/`, les statiques dans `accueil/static/`.

### JavaScript : vanilla et parcimonieux

- JS vanilla uniquement. Pas de framework, pas de bibliothèque sans nécessité
  démontrée et discutée.
- **Amélioration progressive, toujours** : la page doit être complète et
  fonctionnelle sans JavaScript. Le JS n'apporte que du confort en plus.
- Chaque script est petit, autonome, et documente son rôle en tête de fichier.

### CSS : politique simple et stricte

- CSS sémantique de préférence : des classes qui nomment le contenu
  (`.accueil__titre`), pas la présentation.
- La page est découpée en **modules** : chaque module a sa section dans
  `main.css` (ou son fichier dédié si le CSS grossit), délimitée par un
  bandeau de commentaire. Nommage BEM léger : `.module__element--variante`.
- L'intégration d'utilitaires venus d'itou-theme ou du DSFR est permise, mais
  **cantonnée** : les classes utilitaires ne se mélangent pas aux classes
  sémantiques dans une même règle CSS, et chaque import de thème est
  documenté (provenance, version, raison).
- Mobile-first : les media queries élargissent (`min-width`), jamais
  l'inverse. La page est responsive par défaut.

### Templating

Côté serveur uniquement (templates Django). **Pas de templating JS**, pas de
rendu client, pas de gros framework JS.

### Iframe

La page est embarquée en iframe par des sites tiers autorisés (CSP
`frame-ancestors` dans `config/settings.py`) :

- Ne jamais réintroduire `X-Frame-Options` ni retirer la CSP.
- La page publie sa hauteur au parent via `postMessage`
  (`resize-reporter.js`) et doit continuer à le faire quand la mise en page
  change. Le protocole est documenté dans le README.
- La page doit rester agréable à lire quelle que soit la largeur de l'iframe.

### Secrets

**Aucun secret dans le code ou le dépôt.** Pas de clés, pas de tokens, pas
d'URL internes — pas même le nom de l'hébergeur dans le README. La
configuration sensible passe par des variables d'environnement.

## Commandes

- `make dev` — serveur de dev sur :8000
- `make test` — tests
- `make lint` / `make fmt` — ruff
