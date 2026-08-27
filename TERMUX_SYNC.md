# Sincronizar SourceSeal y commander en Termux

Este procedimiento evita el error de rebase incompleta y el mensaje de GitHub
`Password authentication is not supported`.

## 1. Preparar la autenticación SSH una sola vez

En Termux:

```bash
pkg update -y
pkg install -y git openssh python python-pip nodejs curl nmap whois

mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "termux" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

Si ya existe `~/.ssh/id_ed25519`, no la sobrescribas. Copia la salida de
`cat` y agrégala en GitHub:

**GitHub → Settings → SSH and GPG keys → New SSH key**

Luego valida:

```bash
ssh -T git@github.com
```

GitHub puede terminar con código 1 aunque la autenticación sea correcta; lo
importante es que el mensaje confirme que la clave fue aceptada.

## 2. Sincronizar los dos repositorios

El script no borra trabajo silenciosamente:

- aborta una rebase o merge incompletos;
- guarda cambios sin commit en `git stash`;
- crea una rama `backup/termux-*` antes de alinear una rama divergente;
- actualiza ambos repositorios desde `origin/main`;
- no pone tokens ni contraseñas en la URL.

```bash
cd ~/Red-team-tauri
bash scripts/termux/sync_repositories.sh
```

Si las carpetas están en otra ubicación:

```bash
REDTEAM_DIR="$HOME/Red-team-tauri" \
COMMANDER_DIR="$HOME/commander" \
bash ~/Red-team-tauri/scripts/termux/sync_repositories.sh
```

## 3. Levantar SourceSeal

```bash
bash ~/Red-team-tauri/start-termux.sh
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8001`

Comprobación rápida:

```bash
curl http://127.0.0.1:8001/api/health
```

## 4. Levantar commander

Después de sincronizarlo:

```bash
cd ~/commander
python3 commander.py
```

Si vuelve a aparecer `ImportError` dentro de `cryptography`, ejecuta el
sincronizador; detecta esa importación y reinstala `cryptography` y `cffi` para
la versión actual de Python de Termux.

## 5. Recuperar cambios guardados

El sincronizador muestra el stash creado. Para revisarlo:

```bash
cd ~/Red-team-tauri       # o ~/commander
git stash list
git stash show --stat stash@{0}
```

No hagas `git stash pop` hasta confirmar que los cambios corresponden al repo
correcto y que quieres mezclarlos con la versión recién sincronizada.