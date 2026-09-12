# AI GRID Assistant Frontend

Documentation courte du frontend réalisé pour le projet de stage.

## 1. Prerequisites

- Linux/WSL avec Bash
- Node.js et npm via NVM
- Python avec l'environnement virtuel du backend
- Docker et Docker Compose

Vérifier les outils :

```bash
node --version
npm --version
python3 --version
docker --version
docker compose version
```

## 2. NVM et Node.js

Si NVM n'est pas encore disponible :

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install --lts
nvm alias default lts/*
```

Vérifier que Bash utilise bien les versions NVM :

```bash
command -v node
command -v npm
nvm current
```

Les chemins doivent pointer vers `~/.nvm/`, et non vers `/mnt/c/Program Files/nodejs/`.

## 3. Installer les dépendances frontend

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm install
```

## 4. Démarrer Qdrant et PostgreSQL

Depuis la racine du projet :

```bash
cd /home/belkacem/agentic-rag
docker compose up -d
docker compose ps
```

Vérifier les services :

```bash
curl http://localhost:6333/healthz
docker compose exec -T postgres pg_isready -U postgres -d agentic_rag
```

Arrêter les services :

```bash
docker compose down
```

Le fichier `docker-compose.yml` utilise le stockage local `qdrant_storage/` pour conserver la collection `documents`.

## 5. Démarrer le backend RAG

Dans un terminal séparé :

```bash
cd /home/belkacem/agentic-rag
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API et documentation :

- API : http://localhost:8000
- Swagger : http://localhost:8000/docs

Tester directement le chat :

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  --data '{"question":"What is AI GRID?"}'
```

## 6. Démarrer le frontend

Dans un autre terminal :

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
source ~/.bashrc
npm run dev -- --host 0.0.0.0
```

Frontend : http://localhost:5173/

Le proxy Vite redirige `/api/chat` vers le backend local `http://localhost:8000/chat`.

Arrêter le serveur frontend :

Dans le terminal où `npm run dev` tourne, appuyer sur :

```text
Ctrl+C
```

Cela arrête uniquement Vite. Le backend FastAPI et les conteneurs Docker continuent de tourner.

Pour arrêter le backend, utiliser `Ctrl+C` dans son terminal également. Pour arrêter Qdrant et PostgreSQL :

```bash
cd /home/belkacem/agentic-rag
docker compose down
```

## 7. Vérifier le frontend

Lint :

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm run lint
```

Build de production :

```bash
npm run build
```

Prévisualiser le build :

```bash
npm run preview
```

Le build final est généré dans :

```text
ai-grid-widget/dist/
```

## 8. Fonctionnalités du widget

- Widget flottant réductible
- Mode plein écran
- Conversation avec session PostgreSQL
- État `Thinking...`
- Interruption avec `Stop`
- Message après interruption et action `Try again`
- Actions `Retry` et `Copy` sous les réponses
- Rendu Markdown : titres, listes, liens, code et tableaux
- Bouton `Copy` pour les blocs de code
- Layout responsive mobile

## 9. Où chercher les bugs

### Bug d'affichage ou d'interaction

Fichiers principaux :

```text
ai-grid-widget/src/App.css
ai-grid-widget/src/index.css
ai-grid-widget/src/App.jsx
ai-grid-widget/src/App.css
ai-grid-widget/src/index.css
```

Dans le navigateur :

1. Ouvrir les outils développeur avec `F12`.
2. Vérifier l'onglet **Console** pour les erreurs JavaScript.
3. Vérifier l'onglet **Network** pour `/api/chat`.
4. Contrôler le statut HTTP et la réponse JSON.

### Bug de proxy ou de connexion frontend/backend

Fichier :

```text
ai-grid-widget/vite.config.js
```

Tester :

```bash
curl -i -X POST http://localhost:5173/api/chat \
  -H 'Content-Type: application/json' \
  --data '{"question":"What is AI GRID?"}'
```

### Bug FastAPI ou RAG

Regarder le terminal où Uvicorn tourne. Tester aussi :

```bash
curl -i http://localhost:8000/docs
curl http://localhost:6333/collections
docker compose ps
```

### Bug PostgreSQL ou Qdrant

```bash
docker compose logs postgres
docker compose logs qdrant
docker compose ps
```

## 10. Intégration sur la plateforme AI GRID

Le frontend peut être intégré sans modifier la page hôte avec un iframe.

Construire le frontend :

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm run build
```

Copier le contenu de `dist/` sur la VM, par exemple :

```bash
scp -r dist/* user@ai-grid-vm:/var/www/ai-grid-assistant/
```

Exemple d'intégration :

```html
<iframe
  src="/ai-grid-assistant/"
  title="AI GRID Assistant"
  style="position:fixed;right:24px;bottom:24px;width:430px;height:680px;border:0;z-index:9999;"
></iframe>
```

Le backend doit rester sur la VM ou derrière un proxy sécurisé. Les clés API, mots de passe PostgreSQL et clés Langfuse ne doivent jamais être ajoutés au frontend.

## 11. Démarrage rapide complet

Terminal 1 :

```bash
cd /home/belkacem/agentic-rag
docker compose up -d
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 :

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
source ~/.bashrc
npm install
npm run dev -- --host 0.0.0.0
```

Puis ouvrir : http://localhost:5173/
