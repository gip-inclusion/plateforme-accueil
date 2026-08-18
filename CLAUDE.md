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

### Sections

La page est une liste de sections, pas un gros gabarit. `index.html` ne contient
qu'une boucle : **on n'y ajoute jamais de HTML.**

Une section = deux fichiers, même clé :

- `accueil/sections/<key>.py` — une classe `SectionType` décorée par
  `@registry.register`, avec `key`, `label`, `position` et `template`.
  `position` est espacée de 10, pour insérer sans tout renuméroter.
- `accueil/templates/accueil/sections/<key>.html` — le HTML, avec
  `{% load static %}` en tête s'il en a besoin.

Les textes vivent en dur dans le gabarit. **C'est l'état normal**, y compris à
long terme : un contenu qui change une fois par an n'a rien à gagner à devenir
éditable.

Pour rendre un texte éditable, deux lignes et aucune migration : un champ dans
`Form` dont `initial` reprend le texte exact, et `{{ content.<name> }}` à la
place du littéral dans le gabarit. On ouvre un champ à la fois, quand le besoin
est réel — voir `hero.py`, seul exemple ouvert à ce jour.

Les valeurs `initial` sont du contenu de production : elles se relisent en revue
comme du texte, pas comme du code.

### Base de données

Optionnelle, et elle doit le rester : **la page s'affiche sans base**, avec les
textes du code. Toute lecture passe par `accueil/content.py`, qui retombe sur
les défauts si la base est absente, injoignable ou pas encore migrée. Aucune
section ne doit dépendre d'une requête pour s'afficher.

Ce qui est stocké n'est qu'un écart : `Section.content` vide = rendu du code.
`sync_sections` crée les lignes manquantes et **ne supprime jamais rien**, pour
qu'un déploiement annulé ne perde pas le travail d'un rédacteur.

### Langue

Comme sur `les-emplois` et `Autometa` :

- **Les identifiants sont en anglais. Strictement.** Modules, classes,
  fonctions, variables, champs de modèles, noms de tests, clés de section,
  noms de fichiers de code. `page_sections()`, jamais
  `sections_de_la_page()`.
- Les commentaires sont en anglais de préférence, comme le code existant ; le
  français est toléré.
- **Messages de commit en anglais**, titres et descriptions de PR **en
  français**.

Le français reste la langue du contenu affiché, des `verbose_name` et `label`,
des noms de classes CSS sémantiques et de la documentation en prose (README,
ce fichier).

### Mesure d'audience

Toutes les pages rendues doivent charger le Tag Manager Matomo
(`accueil/static/accueil/js/matomo.js`) dans leur `<head>`.

- Le script est branché une seule fois, dans
  `accueil/templates/accueil/base.html`. **Toute page publique étend ce
  gabarit** — on ne recopie pas le squelette HTML ailleurs.
- Ne jamais retirer ni déplacer plus bas la balise `<script>` du tag manager,
  ne jamais lui ajouter `defer` ou `async` : le conteneur doit démarrer avant
  le reste de la page.
- Toute nouvelle vue hérite de `base.html` et est couverte par un test du type
  `test_index_loads_analytics`.

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
