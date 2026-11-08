# La chaîne du bricolage — Site web officiel
Site créé avec les couleurs, le logo et la bannière de **La chaîne du bricolage**. La page publique est publiée sur GitHub Pages.

## Fonctionnement
Le programme **.github/workflows/site-auto.yml** synchronise la chaîne YouTube environ toutes les six heures et lors des modifications du dépôt. Le script **scripts/build_site.py** ajoute au catalogue **data/catalogue.json** les nouvelles vidéos découvertes, puis régénère le dossier **site/** et le publie automatiquement sur GitHub Pages.

- Adresse : https://lachainedubricolage.github.io/la-chaine-du-bricolage/
- Chaîne : https://www.youtube.com/@Lachainedubricolage
- Synchronisation sans clé : les quinze dernières vidéos du flux RSS YouTube et conservation de celles déjà récupérées.
- Historique complet (facultatif) : configurer un secret GitHub Actions nommé `YOUTUBE_API_KEY` après activation de la YouTube Data API v3 dans Google Cloud.
- Les Shorts sont détectés par les mots-clés et, lorsque l'API est configurée, par leur durée. Le classement peut être approximatif.

## Première publication
1. **Settings → Pages → Source : GitHub Actions**.
2. **Actions → Site — mise à jour YouTube et publication → Run workflow** pour lancer la première synchronisation.
3. Vérifier qu'un voyant vert de succès apparaît et ouvrir l'adresse Pages ci-dessus.
4. Si la récupération du flux YouTube échoue, consulter les logs de l'étape « Synchroniser YouTube et fabriquer le site » et relancer.

## Structure
- `assets/` : fichiers du design et de la chaîne.
- `data/catalogue.json` : archive des vidéos.
- `scripts/build_site.py` : synchronisation RSS / API et génération.
- `site/` : fichiers publics générés pour GitHub Pages.
- `tests/test_site.py` : tests unitaires.
- `.github/workflows/site-auto.yml` : automatisation de mise à jour et publication.

La maquette `apercu-local.html` est conservée à titre de référence. Elle n'est pas le site publié et contient des cartes d'exemple.

Le programme utilise seulement des métadonnées YouTube publiques. Les vidéos sont hébergées sur YouTube.