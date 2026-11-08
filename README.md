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
## Import de toutes les anciennes vidéos et Shorts (une fois)

1. Ouvrir [Google Cloud Console](https://console.cloud.google.com/projectcreate), créer un projet (« Site chaîne du bricolage ») et le sélectionner.
2. Ouvrir la [bibliothèque YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) et cliquer sur **Activer**.
3. Ouvrir [Identifiants](https://console.cloud.google.com/apis/credentials) et choisir **Créer des identifiants → Clé API**. Copier la clé sans la publier.
4. Dans Google Cloud, limiter de préférence la clé dans **Restrictions relatives aux API** à **YouTube Data API v3**. Comme le programme s'exécute sur GitHub Actions et non dans un navigateur fixe, éviter une restriction par référent HTTP qui empêcherait le script de fonctionner.
5. Sur GitHub : [Settings → Secrets and variables → Actions](https://github.com/lachainedubricolage/la-chaine-du-bricolage/settings/secrets/actions) → **New repository secret**. Nom exact : `YOUTUBE_API_KEY` ; valeur : la clé Google. Enregistrer. Ne jamais la coller dans un fichier du dépôt ni dans un message.
6. Dans [Actions](https://github.com/lachainedubricolage/la-chaine-du-bricolage/actions/workflows/site-auto.yml), sélectionner « Site — mise à jour YouTube et publication » et cliquer sur **Run workflow**. Le rapport d'exécution affiche le nombre de vidéos récupérées. Si aucun rapport d'import complet n'apparaît, vérifier les étapes et la clé.

L'import lit la playlist publique des mises en ligne de la chaîne et récupère les métadonnées des vidéos par lots. Les vidéos privées ne sont pas affichées. Le classement des Shorts par durée est indicatif : une vidéo courte n'est pas automatiquement un Short au sens de YouTube. Le script conserve les vidéos précédemment enregistrées si l'API est momentanément indisponible.


## Référencement Google, Bing et recherche IA

- Le lecteur YouTube est présent dans le HTML de chaque vidéo (iframe), sans clic initial.
- Chaque page utilise une URL canonique, les métadonnées VideoObject avec les données YouTube, et des instructions d'indexation ouvertes.
- Le sitemap.xml est enrichi avec la section video:video : titre, description, miniature, date, durée et URL du lecteur. Il est régénéré automatiquement.
- Les chapitres ne sont affichés que lorsqu'ils sont effectivement présents dans les descriptions YouTube. Aucun conseil technique n'est inventé par le site.
- La découverte par Google ou les agents IA dépend des moteurs et n'est pas une garantie de classement ou de recommandation.

### Pour valider l'indexation (action du propriétaire)
1. Google Search Console : https://search.google.com/search-console/welcome → ajouter la propriété avec le préfixe `https://lachainedubricolage.github.io/la-chaine-du-bricolage/` et suivre la validation Google.
2. Dans Search Console, aller dans **Sitemaps** et soumettre `https://lachainedubricolage.github.io/la-chaine-du-bricolage/sitemap.xml`.
3. Bing Webmaster Tools : https://www.bing.com/webmasters/ → importer la propriété Google Search Console ou vérifier la propriété, puis soumettre le même sitemap.
4. Ajouter le lien du site dans les liens de la chaîne YouTube et les descriptions des vidéos concernées.
5. Vérifier le rapport Vidéos, les impressions et les clics dans Search Console ; aucune indexation n'est garantie.

**Attention** : un fichier robots.txt placé sous `/la-chaine-du-bricolage/` n'a pas l'autorité sur le robots.txt du domaine racine `github.io` ; les directives `meta robots` de chaque page restent utiles.
