# Simple start — get the Content Engine running on your Hostinger VPS

Two places: your **Windows PC** (push code to GitHub, once) and your **VPS**
(run it). Follow in order. Copy-paste each command exactly.

============================================================================
PART 1 — Put the code on GitHub  (do this on your Windows PC, once)
============================================================================
1. Open a browser, go to github.com, log in.
2. Click the "+" at the top right -> "New repository".
3. Repository name: content-engine
   Choose: Private (or Public if you don't mind the code being visible).
   Do NOT tick "Add a README". Click "Create repository".
4. GitHub shows a URL like:
   https://github.com/hasangeeky-hue/content-engine.git
   Copy it and send it to me — I'll push the code for you (your GitHub login
   is already saved on this PC).

============================================================================
PART 2 — Open your VPS terminal  (Hostinger)
============================================================================
1. Log in at hpanel.hostinger.com
2. Left menu -> VPS -> click your server.
3. Click "Browser terminal" (a black screen opens, already logged in as root).
   That is where you type the commands below.

============================================================================
PART 3 — On the VPS: is Docker there?
============================================================================
Type:
    docker ps
- If you see a table (even empty) -> good, Docker is installed. Continue.
- If it says "command not found" -> type this, wait for it to finish:
    curl -fsSL https://get.docker.com | sh

============================================================================
PART 4 — On the VPS: get the code
============================================================================
Type (replace the URL with YOURS from Part 1):
    cd /opt
    git clone https://github.com/hasangeeky-hue/content-engine.git
    cd content-engine

If it asks for a username/password (private repo): username = your GitHub
name; password = a GitHub token (github.com -> Settings -> Developer settings
-> Personal access tokens -> Fine-grained -> generate, give it access to this
one repo). Tell me if you get stuck here.

============================================================================
PART 5 — On the VPS: add your keys
============================================================================
Type:
    cp deploy/.env.example deploy/.env
    nano deploy/.env
A text editor opens. Change two lines:
    POSTGRES_PASSWORD=   -> type any long random text after the =
    ANTHROPIC_API_KEY=   -> paste your Claude key (from console.anthropic.com)
Save and exit: press Ctrl+O, then Enter, then Ctrl+X.

============================================================================
PART 6 — On the VPS: start it
============================================================================
Type:
    docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
Wait ~2 minutes (it builds the first time). Then check:
    docker compose -f deploy/docker-compose.yml ps
You want to see db, api, worker as "running".

============================================================================
PART 7 — Check it works
============================================================================
Type:
    curl -s http://127.0.0.1:8000/health
Look for  "healthy": true  and  anthropic: ok.

Done — the engine is running.

============================================================================
OPTIONAL (later) — hard 50 GB cap
============================================================================
The engine uses ~10 GB, so you do NOT need this to start. If you later want a
hard ceiling so it can never exceed 50 GB (never run fdisk/parted — that can
wipe your other system):
    sudo fallocate -l 50G /var/lib/content-engine.img
    sudo mkfs.ext4 /var/lib/content-engine.img
    sudo mkdir -p /mnt/content-engine
    sudo mount -o loop /var/lib/content-engine.img /mnt/content-engine
    echo '/var/lib/content-engine.img /mnt/content-engine ext4 loop 0 0' | sudo tee -a /etc/fstab
Then in deploy/docker-compose.yml, change the db volume to:
    - /mnt/content-engine/pgdata:/var/lib/postgresql/data
and restart:  docker compose -f deploy/docker-compose.yml up -d

============================================================================
SEE THE DASHBOARD in your browser
============================================================================
On your Windows PC, open a terminal and type (replace the IP):
    ssh -L 8000:127.0.0.1:8000 root@YOUR_VPS_IP
Leave it open, then open http://localhost:8000/ in your browser -> the job list.
