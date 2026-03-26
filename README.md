# 🎵 Resonance — Self-hosted Music App

Application web musicale self-hosted avec comptes locaux, intégration Last.fm par utilisateur, recommandations et feed de nouveautés.

---

## Fonctionnalités

- 🔍 **Recherche** d'artistes, morceaux et albums (Last.fm + MusicBrainz)
- 👤 **Comptes locaux** avec authentification JWT
- 🔑 **Clés API par utilisateur** — chaque compte gère sa propre clé Last.fm dans l'interface
- 🔐 **Chiffrement** — les clés API sont chiffrées (Fernet/AES) avant stockage en base
- 🔗 **Intégration Last.fm** — liez votre compte et importez vos artistes favoris
- ❤️ **Suivi d'artistes** — suivez/désabonnez des artistes
- 🆕 **Feed de nouveautés** — dernières sorties via MusicBrainz
- ✨ **Recommandations** — artistes similaires via Last.fm
- 🔒 **Changement de mot de passe** depuis les paramètres
- ⚡ **Recherche avec debounce** — résultats en temps réel après 480ms
- ⌨️ **Raccourcis clavier** — `Ctrl+K` pour rechercher, `Échap` pour fermer la modale

---

## Prérequis

- Python 3.11+ **ou** Docker
- Clé API Last.fm (gratuite) : https://www.last.fm/api/account/create  
  *(chaque utilisateur renseigne la sienne depuis les Paramètres de l'app)*

---

## Installation sans Docker

```bash
# 1. Cloner et créer l'environnement
git clone <votre-repo>
cd musicapp
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt

# 2. Configurer
cp .env.example .env
# Éditez .env — seule SECRET_KEY est obligatoire

# 3. Lancer
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Ouvrez **http://localhost:8000**, créez un compte, puis allez dans **Paramètres → Last.fm** pour renseigner votre clé API.

> **Générer une SECRET_KEY sécurisée :**
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## Installation avec Docker

```bash
cp .env.example .env
# Éditez .env avec votre SECRET_KEY

docker-compose up -d
```

L'app est disponible sur **http://localhost:8000**.  
Les données SQLite sont persistées dans `./data/`.

---

## Migration base existante

Si vous avez une base créée avant la v2 (sans colonnes `lastfm_api_key`), l'app applique automatiquement les migrations au démarrage. Vous pouvez aussi le faire manuellement :

```bash
python migrate.py
```

---

## Structure du projet

```
musicapp/
├── main.py                  # Point d'entrée FastAPI + auto-migration
├── config.py                # Settings (SECRET_KEY, DATABASE_URL)
├── crypto.py                # Chiffrement Fernet des clés API
├── database.py              # Engine SQLAlchemy async
├── models.py                # Modèles ORM (User, FollowedArtist)
├── schemas.py               # Schemas Pydantic
├── auth.py                  # JWT, bcrypt, middleware
├── migrate.py               # Script de migration manuel
├── routers/
│   ├── auth_router.py       # register, login, me, link-lastfm, change-password
│   ├── search.py            # artistes, morceaux, albums
│   ├── artists.py           # follow, unfollow, import Last.fm
│   ├── feed.py              # nouvelles sorties MusicBrainz
│   └── recommendations.py  # artistes similaires Last.fm
├── services/
│   ├── lastfm.py            # Wrapper Last.fm (clé par requête)
│   └── musicbrainz.py       # Wrapper MusicBrainz (pas de clé)
├── frontend/
│   └── index.html           # SPA vanilla JS
├── migrations/              # Migrations Alembic
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## API — Endpoints principaux

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/api/auth/register` | — | Créer un compte |
| POST | `/api/auth/login` | — | Se connecter |
| GET | `/api/auth/me` | ✓ | Profil utilisateur |
| POST | `/api/auth/link-lastfm` | ✓ | Lier Last.fm + sauvegarder clés |
| DELETE | `/api/auth/unlink-lastfm` | ✓ | Supprimer liaison Last.fm |
| POST | `/api/auth/change-password` | ✓ | Changer le mot de passe |
| GET | `/api/search/artists?q=` | ✓ | Rechercher des artistes |
| GET | `/api/search/tracks?q=` | ✓ | Rechercher des morceaux |
| GET | `/api/search/releases?q=` | ✓ | Rechercher des albums (MusicBrainz) |
| GET | `/api/search/artist/{name}` | ✓ | Détail + top tracks d'un artiste |
| GET | `/api/artists/following` | ✓ | Artistes suivis |
| POST | `/api/artists/follow` | ✓ | Suivre un artiste |
| DELETE | `/api/artists/unfollow/{name}` | ✓ | Se désabonner |
| POST | `/api/artists/import-lastfm` | ✓ | Import top artistes Last.fm |
| GET | `/api/feed/releases` | ✓ | Nouvelles sorties |
| GET | `/api/recommendations/artists` | ✓ | Recommandations |

Documentation Swagger interactive : **http://localhost:8000/docs**

---

## Sécurité

- Les mots de passe sont hashés avec **bcrypt**
- Les clés API Last.fm sont chiffrées avec **Fernet (AES-128-CBC + HMAC-SHA256)**  
  dérivé depuis votre `SECRET_KEY` — personne d'autre ne peut les lire
- Les tokens JWT expirent après **7 jours**
- Les clés ne sont **jamais** exposées dans les réponses API (`has_lastfm_api_key: bool` seulement)

# Tidown
