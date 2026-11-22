# Guide technique – Application Mon Profil Santé

*Notice destinée aux personnes qui ont accès au code, au dépôt Git et au serveur UGA. Version du 22/11/2026. Ce document n'est destiné ni** aux investigateurs ni aux participants.*

## 1. Vue d'ensemble

L'application est un site web écrit en **Python avec Streamlit**. Elle fait passer des questionnaires de santé en ligne à des participants, calcule des scores, affiche un rapport au participant et offre aux investigateurs un tableau de bord (suivi, export Excel, gestion des participants).

Points à retenir :

- Deux espaces depuis l'accueil : **Participant** (connexion par numéro de randomisation + date de naissance) et **Investigateur** (identifiant et mot de passe définis dans `config.py`).
- Les données sont stockées dans **deux fichiers SQLite** (`questionnaire.db` et `identites.db`), créés automatiquement à côté du code. Il n'y a pas de serveur de base de données.
- Les questionnaires sont décrits dans des **fichiers YAML** (dossier `modules/`), pas dans le code.
- Les **scores** sont calculés à la volée à partir des réponses brutes (ils ne sont pas stockés) : une correction de cotation s'applique donc aussi aux données déjà collectées.
- Versions testées : Python 3.12, Streamlit 1.60 et 1.67. `requirements.txt` doit demander `streamlit>=1.60`.

## 2. Organisation du dépôt

Fichiers du dossier `SurveySEMO` (le dossier interne, celui qui contient `app.py` et `.git`) :

- `app.py` : point d'entrée, routage des pages, questionnaire participant.
- `accueil.py` : page d'accueil, style, logo, écran de connexion.
- `admin.py` : espace investigateur (tableau de bord, dossiers, ajout/modification/suppression de participants, export).
- `db.py` : toute la gestion des bases SQLite (participants, réponses, identités, suivi, journal d'audit).
- `logique.py` : chargement des modules YAML, questions conditionnelles, calcul de l'étape suivante.
- `cotations.py` : calcul de tous les scores et liste des variables exportées.
- `report.py` : rapport affiché au participant (un rapport par module).
- `suivi.py`, `export_excel.py`, `rendu_html.py` : suivi de complétion, export Excel, rapport HTML téléchargeable.
- `legal.py`, `cookies.py`, dossier `legal/` : pages légales (mentions légales, données personnelles, politique des cookies) et bandeau de consentement.
- `config.py` : réglages (identifiants investigateur, autorisation de repasser le questionnaire).
- `modules/` : les questionnaires actifs (YAML). `archives_modules/` et `exemples_modules/` ne sont pas chargés.
- `.streamlit/config.toml` : thème et réglages Streamlit (la collecte de statistiques d'usage est désactivée).

Scripts à lancer en ligne de commande :

- `reinitialiser_base.py` : vider tout ou partie de la base.
- `importer_participants.py` : créer des participants depuis un CSV.
- `donnees_demo.py` : créer des participants FICTIFS (base de test uniquement).
- `exporter_donnees.py` : export CSV brut des réponses.
- `creer_participant.py` : ancien script (voir section 5, à éviter).

`LISEZMOI.md` est ancien (il parle encore de Spyder) : ce guide le remplace.

## 3. Installation et lancement en local

Prérequis : Python 3.12 et Git.

```
git clone https://github.com/AnelorG/SurveySEMO.git
cd SurveySEMO
pip install -r requirements.txt
streamlit run app.py
```

Si le dépôt cloné contient un double dossier `SurveySEMO/SurveySEMO`, placez-vous dans le dossier qui contient `app.py` avant de lancer les commandes. Le navigateur s'ouvre sur l'application. Au premier lancement, les deux bases vides sont créées.

Pour essayer l'application avec des données fictives (sur votre poste, jamais sur le serveur) :

```
python donnees_demo.py
```

Cela crée 14 participants fictifs (numéros P012, P047, P188…) avec des réponses aléatoires. Identifiants de l'espace investigateur : voir `config.py`.

## 4. Les bases de données

### 4.1 Contenu

- `questionnaire.db` : table `participants` (numéro, sel, empreinte de la date de naissance, nombre d'échecs de connexion), table `reponses` (une ligne par réponse, avec le numéro, le passage et l'identifiant de la question, la valeur étant stockée en JSON) et table `meta`.
- `identites.db` : table `identites` (nom, prénom, date de naissance, groupe, date d'inclusion, source), table `suivi` (événements et remarques de suivi) et table `journal` (journal d'audit : créations, modifications, suppressions, déblocages).

La séparation est volontaire : les réponses de santé (`questionnaire.db`) ne contiennent que le numéro de randomisation, tandis que les données d'identité sont dans un fichier distinct. La date de naissance sert de « mot de passe » du participant et n'est stockée dans `questionnaire.db` que sous forme d'empreinte salée.

### 4.2 Règle absolue : les bases ne vont jamais dans Git

Les fichiers `.db` contiennent des données personnelles et des réponses de santé. Ils sont binaires : Git ne sait pas les fusionner et provoque des conflits insolubles. Ils ne doivent donc **jamais** être versionnés. Le `.gitignore` du dépôt doit contenir :

```
__pycache__/
*.pyc
*.db
sauvegarde_*
attribution_*.csv
liste*.csv
Export_*.xlsx
```

Pour retirer du suivi des fichiers déjà versionnés (sans les supprimer du disque) :

```
git rm --cached identites.db questionnaire.db
git commit -m "Retrait des bases du suivi Git"
```

Un `git pull` supprime chez les collègues les fichiers retirés du suivi : ils doivent copier leurs bases hors du dépôt avant de tirer, puis les remettre.

Conséquence importante : **chaque environnement a sa propre base** (poste de chaque développeur, serveur de production). Aucune donnée ne circule par Git.

### 4.3 Sauvegarde

L'application peut tourner pendant une copie, mais une copie de fichier faite en pleine écriture peut être incohérente. Méthode sûre, à lancer dans le dossier de l'application :

```
python -c "import sqlite3; s=sqlite3.connect('questionnaire.db'); d=sqlite3.connect('copie_questionnaire.db'); s.backup(d); d.close(); s.close()"
python -c "import sqlite3; s=sqlite3.connect('identites.db'); d=sqlite3.connect('copie_identites.db'); s.backup(d); d.close(); s.close()"
```

À planifier régulièrement sur le serveur (tâche cron ou planificateur), avec stockage des copies dans un emplacement sécurisé, chiffré, hors du dossier de l'application. Les sauvegardes contiennent des données de santé : mêmes règles d'accès que la base.

### 4.4 Restauration

1. Arrêter l'application.
2. Remplacer `questionnaire.db` et `identites.db` par les copies (en gardant les noms d'origine).
3. Relancer l'application et vérifier la connexion d'un participant et le tableau de bord.

## 5. Gérer les participants

### 5.1 Numéro de randomisation et groupe

Le groupe est **déduit du numéro** (fonction `groupe_pour` de `db.py`) : de P001 à P499, groupe **TEST** ; de P500 à P999, groupe **CONTROL**. Attribuer un numéro revient donc à attribuer un groupe. Un participant se connecte avec son numéro et sa date de naissance. Après 5 échecs consécutifs, le compte est bloqué (réglage `MAX_TENTATIVES` dans `db.py`).

### 5.2 Créer des participants depuis l'interface

Espace investigateur > « Ajouter un nouveau participant » : saisie du nom, du prénom et de la date de naissance ; un numéro est proposé au hasard parmi les numéros libres (P001 à P999), ce qui donne un groupe au hasard. Convient pour des ajouts ponctuels.

### 5.3 Créer des participants depuis le terminal (méthode recommandée pour une liste)

1. Préparer un fichier CSV avec, en **ligne 1, les en-têtes** (les participants commencent en ligne 2) :

```
Nom;Prénom;Date de naissance
Dupont;Éloïse;14/03/1958
```

Colonnes facultatives : `numero` (numéro imposé, par exemple P017) et `groupe` (TEST ou CONTROL). Les accents et la casse des noms de colonnes sont indifférents ; le séparateur peut être `;` ou `,` ; les dates peuvent être au format JJ/MM/AAAA ou AAAA-MM-JJ. Pour une étude pseudonymisée, on peut ne renseigner que des initiales (une lettre dans `Nom`, une dans `Prénom`).

2. Lancer l'**aperçu** (n'écrit rien) :

```
python importer_participants.py liste.csv
```

3. Si l'aperçu est correct, créer réellement les participants :

```
python importer_participants.py liste.csv --appliquer
```

Le script tape `OUI` pour confirmation, puis crée les participants et un fichier `attribution_AAAAMMJJ_HHMMSS.csv` (nom, prénom, naissance, numéro, groupe).

Règles d'attribution :

- colonne `numero` renseignée : ce numéro est utilisé, le groupe en découle ;
- sinon, colonne `groupe` renseignée : un numéro libre est tiré au hasard dans la plage du groupe ;
- sinon : attribution par blocs permutés de 4 (2 TEST et 2 CONTROL dans un ordre aléatoire), puis tirage d'un numéro libre dans la plage du groupe. Si le protocole impose une liste de randomisation officielle, la fournir dans les colonnes `numero` ou `groupe`.

Le script refuse (avec un message par ligne) les dates invalides, les numéros mal formés ou déjà pris, les incohérences numéro/groupe, et les doublons (même nom, prénom et date de naissance, déjà inscrits ou présents deux fois dans le fichier). Deux personnes différentes ayant les mêmes initiales et la même date de naissance doivent recevoir un numéro imposé dans la colonne `numero`.

**Où lancer ce script :** il écrit dans les bases du dossier où il est exécuté. Pour la production, il doit être lancé **sur le serveur**. Le fichier d'attribution est une donnée sensible : le ranger en lieu sûr, ne jamais le versionner, supprimer le CSV d'origine après import.

`creer_participant.py` est un ancien script (liste écrite en dur, lancé sous Spyder) qui crée un participant sans identité et peut écraser un participant existant : ne pas l'utiliser en production.

### 5.4 Autres opérations (espace investigateur)

- **Débloquer un compte** (après 5 échecs) : dossier du participant, bouton de déblocage. En terminal : `python -c "import db; db.debloquer('P001')"`.
- **Corriger une date de naissance, un nom** : « Modifier un participant ». Les réponses ne sont pas touchées ; l'opération est inscrite au journal.
- **Supprimer un participant** : onglet « Supprimer le participant », un motif est exigé. L'opération est journalisée et le numéro est réservé : il ne sera pas réattribué.
- **Repasser le questionnaire** : si `AUTORISER_REPASSAGE = True` dans `config.py`, un participant peut refaire tout ou partie du questionnaire ; chaque remplissage est un « passage » numéroté et les passages précédents sont conservés.

### 5.5 Vider les bases

```
python reinitialiser_base.py tout
```

Efface participants, identités, réponses, suivi, journal d'audit et numéros réservés (remise à zéro complète), après une confirmation à taper (`OUI`). L'application n'a pas besoin d'être arrêtée. Autres modes : `reponses` (efface toutes les réponses, garde les participants) et `participant P012` (efface les réponses d'un seul participant).

Le script crée d'abord deux copies `sauvegarde_AAAAMMJJ_HHMMSS.db` et `sauvegarde_..._identites.db`. Si elles contiennent des données fictives, les supprimer ; si elles contiennent des données réelles, les traiter comme une sauvegarde sensible. Cette commande est **irréversible** sans la sauvegarde : à ne jamais lancer sur la base de production sans accord explicite du responsable de l'étude.

## 6. Modules et questionnaires

### 6.1 Principe

Chaque fichier de `modules/` est un module, chargé dans l'ordre alphabétique des noms de fichiers (`00_...`, `01_...`). Le module `00_accueil_consentement.yaml` est « unique » (affiché une seule fois). Modules actuels : 1 Mode de vie, 2 Exposome psychosocial, 3 Expositions environnementales, 4 Santé générale, 5 Réserve cognitive (QEV/LEQ).

Un module contient un `id`, un `titre`, une `introduction` et une liste de `questions`. Types de questions disponibles : `section`, `info`, `texte_libre`, `texte_court`, `nombre` (avec `min`, `max`, `pas`), `choix_unique`, `oui_non`, `choix_multiple` (avec `exclusives` pour les réponses incompatibles), `case_a_cocher`, `heure`. Les options à points portent une liste `scores`.

Une question peut être **conditionnelle** avec `si` : `egal` (une valeur ou une liste de valeurs), `contient` (choix multiples), `sup` (nombre supérieur à), `rempli: true`. `si` peut être une liste de conditions (toutes doivent être vraies). La pseudo-question `_age` désigne l'âge du participant (utilisée par le module 5).

### 6.2 Règles à respecter

- **Ne jamais renommer l'`id` d'une question ou d'un module une fois la collecte commencée.** Les réponses sont rattachées à ces identifiants : un renommage rend les anciennes réponses invisibles. Pour modifier une question, ajouter une nouvelle question avec un nouvel `id`.
- Pour modifier un libellé ou une option sans changer le sens, on peut éditer le YAML sans risque. Changer le sens d'une question ou la liste des options après le début de la collecte invalide la comparabilité : à décider avec le responsable scientifique et à documenter.
- Après modification, recharger l'application, ouvrir le module avec un participant de test et vérifier les conditions.

### 6.3 Ajouter un module

1. Copier un module existant, le renommer (`06_nom.yaml`), changer l'`id` et le `titre`.
2. Écrire les questions.
3. Si le module doit produire des scores : ajouter une fonction dans `cotations.py`, déclarer ses variables (liste `VARIABLES`) et l'enregistrer dans `REGISTRE`.
4. Si le module doit avoir un rapport participant spécifique : ajouter une fonction dans `report.py` et l'inscrire dans son `REGISTRE`.
5. Tester avec un participant de test, puis vérifier l'export Excel.

## 7. Cotations, rapport et exports

- **Cotations** : tout est dans `cotations.py` (IPAQ, PSQI, MEDAS, alcool, tabac, LSNS-6, HAD-D, expositions environnementales, santé, LEQ général). Les seuils et règles y sont commentés avec référence au document de validation.
- **Rapport participant** : `report.py`, affiché après le questionnaire. Les conseils du type « parlez-en à votre médecin » désignent le médecin personnel du participant.
- **Export Excel** : espace investigateur > « Exporter les données » : feuilles de listing, réponses, scores calculés, suivi et journal, avec légende des variables. C'est la source principale pour les analyses.
- **Export CSV brut** : `python exporter_donnees.py` écrit `export_reponses.csv` (une ligne par participant et par passage). Cet export n'est pas pseudonymisé au-delà du numéro : fichier sensible.
- **Rapport HTML** : bouton « Générer le rapport de synthèse » dans le dossier d'un participant.

Les exports contiennent des données de santé : ne jamais les versionner, les stocker dans un espace sécurisé de l'UGA.

## 8. Pages légales et cookies

- Les trois textes sont des fichiers Markdown dans `legal/` : `mentions_legales.md`, `donnees_personnelles.md`, `politique_cookies.md`. Les modifier ne demande aucune compétence en programmation. Les liens sont en pied de la page d'accueil ; accès direct par `?acces=mentions`, `?acces=donnees`, `?acces=cookies`.
- Le bandeau de cookies (`cookies.py`) propose « Essentiels uniquement » et « Accepter tous les cookies » (même présentation). Le choix est mémorisé 6 mois dans le cookie `semo_cookie_consent` (valeurs `all` ou `essential`). L'application ne dépose aucun cookie de mesure d'audience. Si un outil de mesure est ajouté par l'hébergeur, il ne doit être chargé que si `cookies.mesure_audience_autorisee()` est vrai, et la politique des cookies doit être mise à jour.
- **À vérifier dans un vrai navigateur après chaque déploiement** : cliquer sur un choix, recharger la page (le bandeau ne doit plus apparaître), puis contrôler dans les outils développeur (Application > Cookies) la présence de `semo_cookie_consent`.
- La cohérence entre les textes légaux, la note d'information aux participants et le promoteur de l'étude (CHU Grenoble Alpes pour le consentement actuel) doit être validée par le DPO.

## 9. Travailler avec Git

### 9.1 Routine à respecter

Toujours travailler dans le dossier qui contient `app.py` et `.git` (vérifier que l'invite du terminal se termine par `...\SurveySEMO\SurveySEMO`). Dans VSCodium : Fichier > Ouvrir le dossier, puis choisir ce dossier.

1. Début de session : `git pull origin main`.
2. Travailler, puis `git status` pour voir les fichiers modifiés.
3. `git add <fichiers>` puis `git commit -m "message clair"`. Commiter **avant** tout `pull`.
4. Avant d'envoyer : `git pull origin main`, puis `git push origin main`.

Jamais de `git push --force` (il efface le travail des autres). Jamais de `git add` sur une base, un export ou un fichier d'attribution.

### 9.2 En cas de conflit de fusion

Symptômes : `You have unmerged paths`, ou `Pulling/Committing is not possible because you have unmerged files`, ou push refusé (`non-fast-forward`) parce que le dépôt distant contient des commits que vous n'avez pas.

1. Faire une copie de sauvegarde du dossier du projet.
2. `git status` : repérer les fichiers « both modified » ou « both added ».
3. Ouvrir chaque fichier : les zones en conflit sont encadrées par `<<<<<<<`, `=======` et `>>>>>>>`. Choisir pour chacune : modification actuelle (la vôtre), entrante (celle des collègues) ou les deux, puis supprimer tous les marqueurs.
4. Vérifier qu'il ne reste aucun marqueur (PowerShell) :

```
Get-ChildItem -Recurse -Include *.py,*.md,*.yaml,*.txt | Select-String -Pattern '^(<<<<<<<|=======|>>>>>>>)'
```

5. Vérifier la syntaxe de tous les fichiers Python :

```
Get-ChildItem *.py | ForEach-Object { python -m py_compile $_.Name; if ($LASTEXITCODE -ne 0) { "ERREUR dans $($_.Name)" } }
```

6. `git add <fichiers résolus>`, `git commit -m "Fusion avec les modifications distantes"`, puis `git push origin main`.
7. Lancer l'application et tester la connexion participant, l'espace investigateur et un questionnaire.

Pour abandonner une fusion : `git merge --abort` (revient à l'état d'avant). Les fichiers `.db` ne se fusionnent pas : s'ils apparaissent en conflit, les retirer du suivi (section 4.2).

### 9.3 Erreurs fréquentes après une fusion

- **IndentationError ou SyntaxError** dans `app.py` : un bloc a été dupliqué ou coupé par « Accepter les deux ». Comparer avec une version saine du fichier, ne garder qu'un seul exemplaire du bloc, puis relancer `python -m py_compile app.py`.
- **Une phrase parasite s'affiche sur le site** : Streamlit affiche automatiquement tout texte isolé (docstring ou chaîne) placé directement dans le script, hors d'une fonction. Le transformer en commentaire (`#`) ou le remettre dans sa fonction.
- **`fatal: not a git repository`** : le terminal est dans le mauvais dossier (le dossier extérieur au lieu du dossier interne). Faire `cd` vers le dossier qui contient `.git`.
- **Le terminal ne réagit plus après un plantage** : Streamlit tourne encore dans ce terminal. Ouvrir un second terminal, ou faire Ctrl+C.

## 10. Déploiement sur le serveur UGA

*Section à compléter avec la DSI : système, accès, chemins.*

### 10.1 Principe

L'application se lance avec `streamlit run app.py`. Sur un serveur, on utilise en général :

```
streamlit run app.py --server.port 8501 --server.headless true
```

Il faut un gestionnaire de service (systemd, Docker ou équivalent) pour la redémarrer automatiquement, et un reverse proxy HTTPS (nginx, Apache) devant elle. **Le proxy doit autoriser les WebSockets**, sans quoi l'application affiche une page vide ou se déconnecte.

À confirmer avec la DSI : système d'exploitation, utilisateur du service, dossier d'installation, nom de domaine, certificat HTTPS, politique de sauvegarde, accès SSH.

### 10.2 Mise à jour du code

Sur le serveur, dans le dossier de l'application : `git pull origin main`, puis redémarrage du service. Comme les bases ne sont pas dans Git, elles ne sont pas modifiées par la mise à jour. Si les dépendances ont changé : `pip install -r requirements.txt` avant le redémarrage.

### 10.3 Liste de vérification AVANT l'ouverture aux participants

- [ ] Identifiants de l'espace investigateur (`config.py`) remplacés : les valeurs actuelles sont provisoires et figurent dans l'historique Git. Prévoir, à terme, de les lire depuis des variables d'environnement plutôt que depuis le code.
- [ ] Bases de production **vierges** : lancer `python reinitialiser_base.py tout` sur le serveur (jamais de données de test dans la base de production), puis supprimer les fichiers `sauvegarde_*` générés.
- [ ] Participants créés **sur le serveur** (section 5.3). Les participants créés sur un poste de travail n'existent pas sur le serveur.
- [ ] Aucun fichier `.db`, export ou fichier d'attribution dans le dépôt Git (`git ls-files | Select-String "\.db"` ne doit rien afficher).
- [ ] `requirements.txt` à jour (`streamlit>=1.60`).
- [ ] HTTPS actif, WebSockets autorisés par le proxy.
- [ ] Sauvegardes automatiques des deux bases planifiées, et restauration testée.
- [ ] Accès au serveur et aux sauvegardes limités aux personnes habilitées.
- [ ] Pages légales validées par le DPO (responsable de traitement, durée de conservation, contact) ; bandeau de cookies testé dans un vrai navigateur.
- [ ] Question de l'hébergement des données de santé (certification HDS) tranchée avec le DPO et la DSI.
- [ ] Test complet de bout en bout : un participant de test remplit les cinq modules, consulte son rapport ; l'investigateur voit le dossier et exporte les données ; puis suppression du participant de test.

## 11. Dépannage

- **Un participant n'arrive pas à se connecter** : vérifier le numéro (la casse et les espaces sont ignorés) et la date de naissance saisie à la création. Si le compte est bloqué (5 échecs), le débloquer depuis son dossier. En cas d'erreur de date à la création : « Modifier un participant ».
- **Message « Votre version de Streamlit est trop ancienne »** : `pip install --upgrade streamlit` puis relancer.
- **L'application affiche une page vide ou se déconnecte sur le serveur** : en général un reverse proxy qui bloque les WebSockets.
- **`database is locked`** : deux écritures simultanées. Réessayer ; si le problème persiste, vérifier qu'aucun script ne garde la base ouverte et qu'elle n'est pas sur un partage réseau (SQLite ne supporte pas les disques réseau).
- **Les participants créés ont disparu** : l'application tourne avec d'autres fichiers `.db` que ceux où le script a écrit (autre dossier, autre serveur). Les bases sont toujours celles situées à côté de `db.py`.
- **Des scores sont vides dans l'export** : c'est voulu quand une réponse manque ou vaut « Je ne sais pas » (voir les commentaires de `cotations.py`).
- **Le bandeau de cookies réapparaît à chaque visite** : le cookie `semo_cookie_consent` n'est pas enregistré (navigateur qui bloque les cookies ou problème d'écriture). Vérifier dans les outils développeur.
- **Un module modifié ne s'affiche pas comme prévu** : vérifier l'indentation YAML (`python -c "import yaml; yaml.safe_load(open('modules/XX.yaml', encoding='utf-8'))"` signale l'erreur), puis recharger la page.

## 12. Commandes utiles (aide-mémoire)

```
streamlit run app.py                        # lancer l'application
python -m py_compile app.py                 # vérifier la syntaxe d'un fichier
python importer_participants.py liste.csv   # aperçu d'un import de participants
python importer_participants.py liste.csv --appliquer   # créer les participants
python reinitialiser_base.py tout           # vider les bases (irréversible)
python exporter_donnees.py                  # export CSV brut des réponses
python donnees_demo.py                      # participants fictifs (base de test)
git status                                  # état du dépôt
git pull origin main                        # récupérer le travail des autres
git push origin main                        # envoyer son travail (après un pull)
git merge --abort                           # abandonner une fusion en cours
```

## 13. Points ouverts à traiter

- Choisir l'emplacement, le système et le mode d'exploitation du serveur UGA (section 10).
- Déplacer les identifiants investigateur hors du code (variables d'environnement).
- Définir avec le responsable scientifique le barème des scores spécifiques et du score total du LEQ (non calculés pour l'instant).
- Migrer l'aperçu du rapport HTML de l'espace investigateur : il utilise `st.components.v1.html`, que Streamlit est en train de retirer.
- Actualiser ou supprimer `LISEZMOI.md`, `creer_participant.py` et `exporter_donnees.py`, dont les consignes mentionnent encore Spyder.
