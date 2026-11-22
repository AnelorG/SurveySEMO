# Modifications du 14/11/2026 (d'après « Questionnaire_validation.docx », version du 12/11/2026)

1. **Vocabulaire** : « patient » -> « participant » et « médecin » -> « investigateur » dans les pages participant et investigateur
   (accueil, connexion, tableau de bord, dossiers, formulaires, export Excel, rapport HTML).
   Conservés volontairement : « médecin traitant » (note d'information), « prescrits par un médecin » (item MV14 du PSQI) et les conseils
   « parlez-en à votre médecin » du rapport participant (médecin personnel du participant) ; titre officiel de l'étude inchangé.
   Les anciens liens `?acces=patient` / `?acces=medecin` fonctionnent toujours. Les noms internes (fonctions, tables, clés de session) ne changent pas.
2. **Modules 1 à 4** : questions identiques au document (aucune différence de libellé, d'option ni de borne relevée).
3. **Nouveau module 5 – Réserve cognitive (QEV/LEQ)** : `modules/05_reserve_cognitive.yaml` (généré, 3 périodes). Les périodes « 30 à 65 ans » et
   « depuis 65 ans » ne sont posées qu'aux personnes de l'âge concerné.
4. **Cotations** (`cotations.py`) : seuils MEDAS de la version originale (MV22 < 7 portions/semaine, MV23 < 1, MV24 < 1, MV28 < 3, inégalités strictes) ;
   pourcentages de normalisation (PSQI/21, MEDAS/14, LSNS-6/30, HAD-D/21, ENV/maximum du bloc, IPAQ/150 min) ; repères alcool Santé publique France
   (≤ 10/semaine, ≤ 2/jour, jours sans alcool) ; sous-scores généraux LEQ (0-35 par période, somme /105).
   NON calculés (barème « à confirmer » dans le document) : scores spécifiques LEQ et score total LEQ.
5. **Moteur** : conditions multiples (`si` en liste) et condition sur l'âge (`question: _age`) dans `logique.py` ; export Excel adapté.

# Ajout du 21/11/2026 : pages légales et bandeau de cookies
- `legal/` : vos trois textes (mentions légales, données personnelles, politique des cookies), en Markdown modifiable sans toucher au code.
- `legal.py` : affichage des pages + liens en pied de la page d'accueil (« Mentions légales », « Données personnelles », « Politique des cookies », « Gérer mes cookies »).
  Liens directs : `?acces=mentions`, `?acces=donnees`, `?acces=cookies`.
- `cookies.py` : bandeau « Essentiels uniquement » / « Accepter tous les cookies » (même présentation) affiché tant qu'aucun choix n'est fait ; choix mémorisé 6 mois
  dans le cookie `semo_cookie_consent` (all | essential). L'app ne dépose aucun cookie de mesure d'audience : si Matomo est ajouté par l'hébergeur,
  ne le charger que si `cookies.mesure_audience_autorisee()` est vrai.
- À VÉRIFIER dans un vrai navigateur après déploiement : cliquer sur un choix, recharger la page (le bandeau ne doit plus apparaître), puis
  Outils développeur > Application > Cookies : `semo_cookie_consent` doit exister.
