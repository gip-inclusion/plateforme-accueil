# theme-inclusion (vendorisé)

- **Provenance** : `gip-inclusion/les-emplois`,
  `itou/static/vendor/theme-inclusion/`, copie du 2026-08-19 — c'est-à-dire
  exactement ce que sert `plateforme.inclusion.gouv.fr`, qui est le futur nom
  des emplois. Le dépôt d'origine du thème est `gip-inclusion/itou-theme`
  (build Bootstrap 5.3) ; la copie des emplois est plus récente que le `dist/`
  de ce dépôt, c'est donc elle qui fait foi.
- **Pourquoi vendorisé plutôt que pointé en ligne** : le chemin servi est haché
  (`app.<hash>.css`), donc instable, et l'alias sans hachage ne tient qu'à leur
  configuration de stockage. L'édition ne doit pas dépendre du déploiement d'un
  autre site pour rester lisible.
- **Raison** : donner à l'interface d'édition l'apparence de la maison (boutons,
  boîtes, tags) sans redessiner un back-office. Le thème n'est chargé **que**
  par `/edition/` ; la page publique garde son CSS sémantique écrit à la main et
  ne le charge jamais.
- **Ce qui n'est pas repris** : les images décoratives (3,3 Mo) et la police
  d'icônes Remixicon (10 Mo) — l'édition n'utilise ni l'une ni l'autre. Quelques
  `url()` du thème pointent donc dans le vide ; elles ne concernent que des
  composants que nous n'affichons pas.
- **Mise à jour** : recopier `stylesheets/app.css` et `fonts/marianne/*.woff2`
  depuis les-emplois, puis vérifier `/edition/` à l'œil. Ne pas modifier ces
  fichiers à la main.
