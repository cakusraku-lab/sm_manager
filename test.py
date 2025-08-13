# Recreate project files cleanly (fixing previous error) and zip them
import os, shutil, zipfile, datetime, textwrap, pathlib

base = "/mnt/data/solo-creator-app"
if os.path.exists(base):
    shutil.rmtree(base)
os.makedirs(f"{base}/assets", exist_ok=True)

# schema.sql
open(f"{base}/schema.sql","w").write(textwrap.dedent("""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL CHECK(platform IN ('youtube_long','youtube_short','instagram','tiktok')),
    title TEXT NOT NULL,
    description TEXT,
    publish_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('idea','in_production','ready','scheduled','published')) DEFAULT 'idea',
    tags TEXT,
    series_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT,
    status TEXT NOT NULL CHECK(status IN ('open','done')) DEFAULT 'open',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    days_of_week TEXT NOT NULL,
    platforms TEXT NOT NULL
);

INSERT INTO users (email, password_hash)
SELECT 'admin@example.com', '$2y$10$wH0CThsoH3CNk1tIQO1xQeGqzq6k2Q7p7FY5w5a6m2NQJdLni5mSa'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email='admin@example.com');
""").strip()+"\n")

# db.php
open(f"{base}/db.php","w").write(textwrap.dedent("""
<?php
function db() {
    static $pdo;
    if ($pdo) return $pdo;
    $dbPath = __DIR__ . '/data.sqlite';
    $isNew = !file_exists($dbPath);
    $pdo = new PDO('sqlite:' . $dbPath, null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
    $pdo->exec("PRAGMA foreign_keys = ON");
    if ($isNew) {
        $schema = file_get_contents(__DIR__ . '/schema.sql');
        $pdo->exec($schema);
    }
    return $pdo;
}

function json_input() {
    $raw = file_get_contents('php://input');
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function respond($data, $code=200) {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data);
    exit;
}
?>
"""))

# auth.php
open(f"{base}/auth.php","w").write(textwrap.dedent("""
<?php
session_start();

function require_login() {
    if (!isset($_SESSION['user_id'])) {
        http_response_code(401);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'unauthorized']);
        exit;
    }
}

function csrf_token() {
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
    }
    return $_SESSION['csrf'];
}

function verify_csrf($token) {
    return isset($_SESSION['csrf']) && hash_equals($_SESSION['csrf'], $token ?? '');
}
?>
"""))

# api.php with heredoc for multi-line SQL
api_php = """
<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/auth.php';

$pdo = db();
$input = json_input();
$action = $_GET['action'] ?? ($input['action'] ?? '');

switch ($action) {
    case 'login':
        $email = $input['email'] ?? '';
        $password = $input['password'] ?? '';
        $stmt = $pdo->prepare("SELECT id, password_hash FROM users WHERE email = ?");
        $stmt->execute([$email]);
        $user = $stmt->fetch();
        if ($user && password_verify($password, $user['password_hash'])) {
            $_SESSION['user_id'] = $user['id'];
            respond(['ok' => true, 'csrf' => csrf_token()]);
        } else {
            respond(['ok' => false, 'error' => 'invalid_credentials'], 401);
        }
        break;

    case 'logout':
        session_destroy();
        respond(['ok' => true]);
        break;

    case 'me':
        if (isset($_SESSION['user_id'])) {
            respond(['id' => $_SESSION['user_id'], 'csrf' => csrf_token()]);
        } else {
            respond(['id' => null]);
        }
        break;

    case 'posts_list':
        require_login();
        $platform = $_GET['platform'] ?? null;
        $status = $_GET['status'] ?? null;
        $q = $_GET['q'] ?? null;
        $sql = "SELECT p.*, s.name as series_name FROM posts p LEFT JOIN series s ON s.id = p.series_id WHERE 1=1";
        $params = [];
        if ($platform) { $sql .= " AND p.platform = ?"; $params[] = $platform; }
        if ($status) { $sql .= " AND p.status = ?"; $params[] = $status; }
        if ($q) { $sql .= " AND (p.title LIKE ? OR p.description LIKE ? OR p.tags LIKE ?)"; $params[]="%$q%"; $params[]="%$q%"; $params[]="%$q%"; }
        $sql .= " ORDER BY COALESCE(p.publish_at, p.created_at) ASC";
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        respond($stmt->fetchAll());
        break;

    case 'posts_create':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $post = $input['post'] ?? [];
        $platform = $post['platform'] ?? '';
        $desc = $post['description'] ?? '';
        $title = $post['title'] ?? '';
        $errors = [];
        if (!$title) $errors[] = 'Brak tytułu';
        $allowed = ['youtube_long','youtube_short','instagram','tiktok'];
        if (!in_array($platform, $allowed)) $errors[] = 'Zła platforma';

        $limits = ['youtube_long'=>5000, 'youtube_short'=>150, 'instagram'=>2200, 'tiktok'=>2200];
        $maxDesc = $limits[$platform] ?? 1000;
        if (mb_strlen($desc) > $maxDesc) $errors[] = "Opis zbyt długi (max $maxDesc)";
        if ($errors) respond(['ok'=>false,'errors'=>$errors],400);

        $stmt = $pdo->prepare("INSERT INTO posts (platform,title,description,publish_at,status,tags,series_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))");
        $stmt->execute([
            $platform,
            $title,
            $desc,
            $post['publish_at'] ?? null,
            $post['status'] ?? 'idea',
            $post['tags'] ?? '',
            $post['series_id'] ?? null
        ]);
        respond(['ok'=>true,'id'=>$pdo->lastInsertId()]);
        break;

    case 'posts_update':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $id = intval($input['id'] ?? 0);
        $post = $input['post'] ?? [];
        if (!$id) respond(['error'=>'no_id'],400);
        $fields = ['platform','title','description','publish_at','status','tags','series_id'];
        $set = [];
        $params = [];
        foreach ($fields as $f) {
            if (array_key_exists($f, $post)) { $set[] = "$f = ?"; $params[] = $post[$f]; }
        }
        if (!$set) respond(['error'=>'no_changes'],400);
        $params[] = $id;
        $sql = "UPDATE posts SET ".implode(',', $set).", updated_at = datetime('now') WHERE id = ?";
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        respond(['ok'=>true]);
        break;

    case 'posts_duplicate_to_platforms':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $id = intval($input['id'] ?? 0);
        $platforms = $input['platforms'] ?? [];
        $stmt = $pdo->prepare("SELECT * FROM posts WHERE id=?");
        $stmt->execute([$id]);
        $src = $stmt->fetch();
        if (!$src) respond(['error'=>'not_found'],404);
        $ids = [];
        foreach ($platforms as $pf) {
            $ins = $pdo->prepare("INSERT INTO posts (platform,title,description,publish_at,status,tags,series_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))");
            $ins->execute([$pf,$src['title'],$src['description'],$src['publish_at'],'idea',$src['tags'],$src['series_id']]);
            $ids[] = $pdo->lastInsertId();
        }
        respond(['ok'=>true,'new_ids'=>$ids]);
        break;

    case 'ideas_list':
        require_login();
        $stmt = $pdo->query("SELECT * FROM ideas ORDER BY created_at DESC");
        respond($stmt->fetchAll());
        break;

    case 'ideas_create':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $stmt = $pdo->prepare("INSERT INTO ideas (title, description, category, created_at) VALUES (?,?,?,datetime('now'))");
        $stmt->execute([$input['title'] ?? '', $input['description'] ?? '', $input['category'] ?? '']);
        respond(['ok'=>true,'id'=>$pdo->lastInsertId()]);
        break;

    case 'todos_list':
        require_login();
        $stmt = $pdo->query("SELECT * FROM todos ORDER BY COALESCE(due_date, created_at) ASC");
        respond($stmt->fetchAll());
        break;

    case 'todos_create':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $stmt = $pdo->prepare("INSERT INTO todos (title, description, due_date, status, created_at) VALUES (?,?,?,?,datetime('now'))");
        $stmt->execute([$input['title'] ?? '', $input['description'] ?? '', $input['due_date'] ?? null, 'open']);
        respond(['ok'=>true,'id'=>$pdo->lastInsertId()]);
        break;

    case 'todos_toggle':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $id = intval($input['id'] ?? 0);
        $stmt = $pdo->prepare("UPDATE todos SET status = CASE status WHEN 'open' THEN 'done' ELSE 'open' END WHERE id = ?");
        $stmt->execute([$id]);
        respond(['ok'=>true]);
        break;

    case 'series_list':
        require_login();
        $stmt = $pdo->query("SELECT * FROM series ORDER BY name ASC");
        respond($stmt->fetchAll());
        break;

    case 'series_create':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $stmt = $pdo->prepare("INSERT INTO series (name, description) VALUES (?, ?)");
        $stmt->execute([$input['name'] ?? '', $input['description'] ?? '']);
        respond(['ok'=>true,'id'=>$pdo->lastInsertId()]);
        break;

    case 'templates_list':
        require_login();
        $stmt = $pdo->query("SELECT * FROM templates ORDER BY name ASC");
        respond($stmt->fetchAll());
        break;

    case 'templates_create':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $stmt = $pdo->prepare("INSERT INTO templates (name, days_of_week, platforms) VALUES (?, ?, ?)");
        $stmt->execute([$input['name'] ?? '', $input['days_of_week'] ?? '', $input['platforms'] ?? '']);
        respond(['ok'=>true,'id'=>$pdo->lastInsertId()]);
        break;

    case 'templates_instatiate_week':
        require_login();
        if (!verify_csrf($input['csrf'] ?? '')) respond(['error'=>'bad_csrf'],400);
        $template_id = intval($input['template_id'] ?? 0);
        $start_date = $input['start_date'] ?? '';
        $t = $pdo->prepare("SELECT * FROM templates WHERE id=?");
        $t->execute([$template_id]);
        $tpl = $t->fetch();
        if (!$tpl) respond(['error'=>'not_found'],404);
        $days = array_map('trim', explode(',', $tpl['days_of_week']));
        $platforms = array_map('trim', explode(',', $tpl['platforms']));
        $created = [];
        foreach ($days as $d) {
            $date = new DateTime($start_date);
            $map = ['Mon'=>1,'Tue'=>2,'Wed'=>3,'Thu'=>4,'Fri'=>5,'Sat'=>6,'Sun'=>7];
            $dow = $map[$d] ?? null;
            if ($dow) {
                $isoDow = (int)$date->format('N');
                $offset = $dow - $isoDow;
                $date->modify(($offset>=0?"+$offset":"$offset") . " day");
                foreach ($platforms as $pf) {
                    $ins = $pdo->prepare("INSERT INTO posts (platform,title,description,publish_at,status,tags,series_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))");
                    $ins->execute([$pf,"[TPL] ".$tpl['name'],"", $date->format('Y-m-d 10:00:00'), 'scheduled', '', null]);
                    $created[] = $pdo->lastInsertId();
                }
            }
        }
        respond(['ok'=>true,'created'=>$created]);
        break;

    case 'report_weekly':
        require_login();
        $start = $_GET['start'] ?? (new DateTime('monday this week'))->format('Y-m-d');
        $end = (new DateTime($start))->modify('+6 days')->format('Y-m-d');
        $sql = "SELECT platform, status, COUNT(*) as cnt
                FROM posts
                WHERE date(publish_at) BETWEEN date(?) AND date(?)
                GROUP BY platform, status";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([$start, $end]);
        respond(['start'=>$start,'end'=>$end,'rows'=>$stmt->fetchAll()]);
        break;

    case 'report_series_effectiveness':
        require_login();
        $sql = "SELECT s.name as series, p.status, COUNT(*) as cnt
                FROM posts p
                LEFT JOIN series s ON s.id = p.series_id
                GROUP BY s.name, p.status
                ORDER BY s.name";
        $stmt = $pdo->query($sql);
        respond($stmt->fetchAll());
        break;

    default:
        respond(['error' => 'unknown_action', 'action' => $action], 404);
}
?>
"""
open(f"{base}/api.php","w").write(api_php)

# export_csv.php
open(f"{base}/export_csv.php","w").write(textwrap.dedent("""
<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/auth.php';
require_login();

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="posts_export.csv"');

$out = fopen('php://output', 'w');
fputcsv($out, ['id','platform','title','description','publish_at','status','tags','series_id']);
$stmt = db()->query("SELECT id, platform, title, description, publish_at, status, tags, series_id FROM posts ORDER BY id ASC");
while ($row = $stmt->fetch(PDO::FETCH_NUM)) {
    fputcsv($out, $row);
}
fclose($out);
?>
"""))

# export_ics.php
open(f"{base}/export_ics.php","w").write(textwrap.dedent("""
<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/auth.php';
require_login();

header('Content-Type: text/calendar; charset=utf-8');
header('Content-Disposition: attachment; filename="posts_calendar.ics"');

$rows = db()->query("SELECT id, title, publish_at, platform FROM posts WHERE publish_at IS NOT NULL AND status IN ('scheduled','published') ORDER BY publish_at ASC")->fetchAll();

echo "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SoloCreator//Planner//EN\r\n";
foreach ($rows as $r) {
    $dt = (new DateTime($r['publish_at']))->format('Ymd\\THis\\Z');
    $uid = $r['id'] . "@solocreator";
    $title = addcslashes($r['title'], ",;\\n");
    $desc = strtoupper($r['platform']);
    echo "BEGIN:VEVENT\\r\\nUID:$uid\\r\\nDTSTAMP:$dt\\r\\nDTSTART:$dt\\r\\nSUMMARY:$title\\r\\nDESCRIPTION:$desc\\r\\nEND:VEVENT\\r\\n";
}
echo "END:VCALENDAR\\r\\n";
?>
"""))

# backup.php
open(f"{base}/backup.php","w").write(textwrap.dedent("""
<?php
require_once __DIR__ . '/auth.php';
require_login();

$path = __DIR__ . '/data.sqlite';
if (!file_exists($path)) {
    http_response_code(404);
    echo "Database not found";
    exit;
}
header('Content-Type: application/octet-stream');
header('Content-Disposition: attachment; filename=\"backup_' . date('Ymd_His') . '.sqlite\"');
readfile($path);
?>
"""))

# index.php
open(f"{base}/index.php","w").write(textwrap.dedent("""
<?php require_once __DIR__ . '/auth.php'; ?>
<!doctype html>
<html lang="pl" data-theme="light">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Solo Creator Planner</title>
  <link rel="stylesheet" href="assets/style.css"/>
</head>
<body>
  <header class="topbar">
    <button id="menuBtn" aria-label="Menu">☰</button>
    <h1>Solo Creator Planner</h1>
    <div class="spacer"></div>
    <button id="themeToggle" title="Przełącz motyw">🌓</button>
  </header>

  <nav id="sidebar" class="sidebar">
    <a data-view="dashboard">📊 Dashboard</a>
    <a data-view="calendar">🗓 Kalendarz</a>
    <a data-view="kanban">🧩 Kanban</a>
    <a data-view="posts">📝 Posty</a>
    <a data-view="ideas">💡 Bank pomysłów</a>
    <a data-view="todo">✅ To‑do</a>
    <a data-view="templates">📐 Szablony</a>
    <a data-view="reports">📈 Raporty</a>
    <a data-view="settings">⚙️ Ustawienia</a>
    <hr/>
    <a id="loginLink" data-view="login">🔐 Logowanie</a>
    <a id="logoutLink" style="display:none">🚪 Wyloguj</a>
  </nav>

  <main id="app" class="app"></main>

  <script>window.__APP_VERSION__ = "1.0.0";</script>
  <script src="assets/app.js"></script>
</body>
</html>
"""))

# style.css
open(f"{base}/assets/style.css","w").write(textwrap.dedent("""
:root {
  --bg: #ffffff;
  --text: #111111;
  --muted: #6b7280;
  --card: #f3f4f6;
  --accent: #2563eb;
  --border: #e5e7eb;
}
html[data-theme="dark"] {
  --bg: #0b0f19;
  --text: #e5e7eb;
  --muted: #9ca3af;
  --card: #111827;
  --accent: #60a5fa;
  --border: #1f2937;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text);
}
.topbar {
  display: flex; align-items: center; gap: 0.5rem;
  padding: .5rem .75rem; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg); z-index: 5;
}
.topbar .spacer { flex: 1 }
button, input, select, textarea {
  background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: .5rem .6rem; font-size: 1rem;
}
button.primary { background: var(--accent); color: white; border-color: transparent; }
.sidebar {
  position: fixed; top: 3rem; left: 0; bottom: 0; width: 260px; background: var(--bg);
  border-right: 1px solid var(--border); transform: translateX(-100%); transition: transform .2s ease; z-index:4; padding: .5rem;
}
.sidebar.open { transform: translateX(0); }
.sidebar a { display:block; padding: .6rem .4rem; border-radius: 6px; text-decoration: none; color: var(--text); cursor:pointer; }
.sidebar a:hover { background: var(--card); }
.app { padding: 1rem; margin-top: .5rem; }
.grid { display: grid; grid-template-columns: 1fr; gap: .75rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: .75rem; }
.section-title { font-weight: 600; margin: .25rem 0 .5rem; }
.table { border-collapse: collapse; width: 100%; }
.table th, .table td { padding: .5rem; border-bottom: 1px solid var(--border); text-align: left; }
.table th { font-weight: 600; }
.kanban { display: grid; grid-template-columns: repeat(5, minmax(180px, 1fr)); gap: .75rem; overflow-x: auto; }
.column { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: .5rem; min-height: 200px; }
.column h4 { margin-top: 0; }
.card-item { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: .5rem; margin-bottom: .5rem; }
.calendar { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; border: 1px solid var(--border); }
.calendar .day { padding: .5rem; min-height: 80px; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.calendar .day header { font-size: .9rem; color: var(--muted); }
@media (min-width: 900px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
  .sidebar { transform: translateX(0); }
  .app { margin-left: 260px; }
}
"""))

# app.js
open(f"{base}/assets/app.js","w").write(textwrap.dedent("""
// SPA-like front-end with fetch() to PHP API
const $ = (sel, el=document) => el.querySelector(sel);
const $$ = (sel, el=document) => [...el.querySelectorAll(sel)];

const state = {
  me: null,
  csrf: null,
  posts: [], ideas: [], todos: [], templates: [], series: [],
  filters: { platform:'', status:'', q:'' },
  view: 'dashboard'
};

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}
(function initTheme(){
  setTheme(localStorage.getItem('theme') || 'light');
})();

async function api(action, payload={}, method='POST', qs={}) {
  const params = new URLSearchParams({ action, ...qs }).toString();
  const res = await fetch('api.php?' + params, {
    method, headers: { 'Content-Type':'application/json' },
    body: method === 'GET' ? undefined : JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function checkMe() {
  const me = await api('me', {}, 'GET');
  state.me = me.id ? me : null;
  state.csrf = me.csrf || null;
  $('#logoutLink').style.display = state.me ? '' : 'none';
  $('#loginLink').style.display = state.me ? 'none' : '';
}

function toast(msg) { alert(msg); }

function platformLabel(p) {
  return {youtube_long:'YouTube (Long)', youtube_short:'YouTube (Short)', instagram:'Instagram Reels', tiktok:'TikTok'}[p] || p;
}
function statusLabel(s) {
  return {idea:'Pomysł', in_production:'W produkcji', ready:'Gotowy', scheduled:'Zaplanowany', published:'Opublikowany'}[s] || s;
}

function navTo(view) { state.view = view; render(); }

function shortcutSetup() {
  document.addEventListener('keydown', (e)=>{
    if (e.target.matches('input,textarea,select')) return;
    if (e.key === 'n') { e.preventDefault(); navTo('posts'); setTimeout(()=>$('#newPostBtn')?.click(), 0); }
    if (e.key === 'f') { e.preventDefault(); navTo('posts'); setTimeout(()=>$('#filterQ')?.focus(), 0); }
    if (e.key === '?') { e.preventDefault(); toast('Skróty: n = nowy post, f = filtruj, g d = dashboard, g k = kalendarz, g p = posty'); }
    if (e.key === 'g') {
      document.addEventListener('keydown', function once(ev){
        if (ev.key === 'd') navTo('dashboard');
        if (ev.key === 'k') navTo('calendar');
        if (ev.key === 'p') navTo('posts');
        document.removeEventListener('keydown', once, true);
      }, true);
    }
  });
}

async function loadAll() {
  if (!state.me) return;
  const [posts, ideas, todos, templates, series] = await Promise.all([
    api('posts_list', {}, 'GET', state.filters),
    api('ideas_list', {}, 'GET'),
    api('todos_list', {}, 'GET'),
    api('templates_list', {}, 'GET'),
    api('series_list', {}, 'GET')
  ]);
  Object.assign(state, {posts, ideas, todos, templates, series});
}

function render() {
  const app = $('#app');
  if (!state.me) { app.innerHTML = renderLogin(); return; }
  switch (state.view) {
    case 'dashboard': app.innerHTML = renderDashboard(); break;
    case 'calendar': app.innerHTML = renderCalendar(); break;
    case 'kanban': app.innerHTML = renderKanban(); break;
    case 'posts': app.innerHTML = renderPosts(); break;
    case 'ideas': app.innerHTML = renderIdeas(); break;
    case 'todo': app.innerHTML = renderTodo(); break;
    case 'templates': app.innerHTML = renderTemplates(); break;
    case 'settings': app.innerHTML = renderSettings(); break;
    case 'reports': app.innerHTML = renderReports(); break;
    default: app.innerHTML = '<p>Nieznany widok.</p>';
  }
}

function renderLogin() {
  return `
  <div class="grid">
    <div class="card">
      <h2>Zaloguj się</h2>
      <p>Domyślnie: admin@example.com / <code>admin</code> (zmień hasło po pierwszym logowaniu).</p>
      <form id="loginForm">
        <label>Email<br><input name="email" type="email" required placeholder="you@domain.com"/></label><br><br>
        <label>Hasło<br><input name="password" type="password" required/></label><br><br>
        <button class="primary">Zaloguj</button>
      </form>
    </div>
    <div class="card">
      <h2>O aplikacji</h2>
      <p>Planowanie publikacji (YouTube, IG Reels, TikTok), pipeline, to-do, pomysły, szablony, raporty.</p>
      <p>Wersja ${window.__APP_VERSION__}</p>
    </div>
  </div>`;
}

function renderDashboard() {
  const next = state.posts.filter(p=>p.publish_at).sort((a,b)=>a.publish_at.localeCompare(b.publish_at)).slice(0,5);
  const openTodos = state.todos.filter(t=>t.status==='open').slice(0,5);
  return `
  <div class="grid">
    <div class="card">
      <div class="section-title">Nadchodzące publikacje</div>
      <table class="table">
        <thead><tr><th>Data</th><th>Platforma</th><th>Tytuł</th><th>Status</th></tr></thead>
        <tbody>${next.map(p=>`<tr>
          <td>${(p.publish_at||'').replace('T',' ')}</td>
          <td>${platformLabel(p.platform)}</td>
          <td>${escapeHtml(p.title)}</td>
          <td>${statusLabel(p.status)}</td>
        </tr>`).join('')}</tbody>
      </table>
      <a href="#" onclick="navTo('calendar')">Zobacz kalendarz →</a>
    </div>
    <div class="card">
      <div class="section-title">Dzisiejsze To‑do</div>
      <ul>${openTodos.map(t=>`<li><label><input type="checkbox" data-todo="${t.id}" ${t.status==='done'?'checked':''}/> ${escapeHtml(t.title)}</label></li>`).join('')}</ul>
      <button onclick="navTo('todo')">Otwórz To‑do →</button>
    </div>
  </div>`;
}

function renderCalendar() {
  const start = startOfMonth(new Date());
  const days = buildMonthDays(start);
  const postsByDate = groupBy(state.posts.filter(p=>p.publish_at), p => (p.publish_at||'').slice(0,10));
  return `
  <div class="card">
    <div class="section-title">Kalendarz (miesiąc)</div>
    <div class="calendar">
      ${days.map(d=>{
        const key = d.toISOString().slice(0,10);
        const items = postsByDate[key] || [];
        return `<div class="day">
          <header>${key}</header>
          <div>${items.map(p=>`<div class="card-item">${platformLabel(p.platform)} • ${escapeHtml(p.title)}</div>`).join('')}</div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

function renderKanban() {
  const statuses = ['idea','in_production','ready','scheduled','published'];
  return `
  <div class="kanban">
    ${statuses.map(s=>`<section class="column" data-status="${s}">
      <h4>${statusLabel(s)}</h4>
      ${state.posts.filter(p=>p.status===s).slice(0,50).map(p=>`
        <div class="card-item">
          <div><b>${escapeHtml(p.title)}</b></div>
          <div class="muted">${platformLabel(p.platform)}</div>
          <div class="row">
            <button onclick="quickStatus(${p.id}, nextStatus('${s}'))">→ Następny</button>
            <button onclick="editPost(${p.id})">Edytuj</button>
          </div>
        </div>`).join('')}
    </section>`).join('')}
  </div>`;
}

function renderPosts() {
  const platforms = ['', 'youtube_long','youtube_short','instagram','tiktok'];
  const statuses = ['', 'idea','in_production','ready','scheduled','published'];
  const rows = state.posts;
  return `
  <div class="card">
    <div class="section-title">Lista postów</div>
    <div class="row" style="display:flex; gap:.5rem; flex-wrap:wrap;">
      <select id="filterPlatform">${platforms.map(p=>`<option value="${p}" ${state.filters.platform===p?'selected':''}>${p?platformLabel(p):'Platforma'}</option>`).join('')}</select>
      <select id="filterStatus">${statuses.map(s=>`<option value="${s}" ${state.filters.status===s?'selected':''}>${s?statusLabel(s):'Status'}</option>`).join('')}</select>
      <input id="filterQ" placeholder="Szukaj..." value="${state.filters.q||''}"/>
      <button onclick="applyFilters()">Filtruj</button>
      <button id="newPostBtn" class="primary" onclick="newPost()">+ Nowy post</button>
      <a href="export_csv.php" target="_blank">Eksport CSV</a>
      <a href="export_ics.php" target="_blank">Eksport .ics</a>
    </div>
    <table class="table">
      <thead><tr><th>ID</th><th>Tytuł</th><th>Platforma</th><th>Status</th><th>Publikacja</th><th>Tagi</th><th>Akcje</th></tr></thead>
      <tbody>${rows.map(p=>`<tr>
        <td>${p.id}</td>
        <td>${escapeHtml(p.title)}</td>
        <td>${platformLabel(p.platform)}</td>
        <td>${statusLabel(p.status)}</td>
        <td>${(p.publish_at||'').replace('T',' ')}</td>
        <td>${escapeHtml(p.tags||'')}</td>
        <td>
          <button onclick="editPost(${p.id})">Edytuj</button>
          <button onclick="duplicatePost(${p.id})">Duplikuj</button>
        </td>
      </tr>`).join('')}</tbody>
    </table>
  </div>`;
}

function renderIdeas() {
  return `
  <div class="grid">
    <div class="card">
      <div class="section-title">Nowy pomysł</div>
      <form id="ideaForm">
        <input name="title" placeholder="Tytuł" required/>
        <input name="category" placeholder="Kategoria"/>
        <textarea name="description" placeholder="Opis"></textarea>
        <button class="primary">Zapisz</button>
      </form>
    </div>
    <div class="card">
      <div class="section-title">Bank pomysłów</div>
      <ul>${state.ideas.map(i=>`<li><b>${escapeHtml(i.title)}</b> <span class="muted">(${i.category||'brak'})</span><br>${escapeHtml(i.description||'')}</li>`).join('')}</ul>
    </div>
  </div>`;
}

function renderTodo() {
  return `
  <div class="grid">
    <div class="card">
      <div class="section-title">Dodaj zadanie</div>
      <form id="todoForm">
        <input name="title" placeholder="Tytuł" required/>
        <input name="due_date" type="date"/>
        <textarea name="description" placeholder="Opis"></textarea>
        <button class="primary">Dodaj</button>
      </form>
    </div>
    <div class="card">
      <div class="section-title">Twoje zadania</div>
      <ul>${state.todos.map(t=>`<li>
        <label><input type="checkbox" data-todo="${t.id}" ${t.status==='done'?'checked':''}/> ${escapeHtml(t.title)} <span class="muted">${t.due_date||''}</span></label>
      </li>`).join('')}</ul>
    </div>
  </div>`;
}

function renderTemplates() {
  return `
  <div class="grid">
    <div class="card">
      <div class="section-title">Nowy szablon tygodnia</div>
      <form id="tplForm">
        <input name="name" placeholder="Nazwa" required/>
        <input name="days" placeholder="Dni tyg.: Mon,Wed,Fri" required/>
        <input name="platforms" placeholder="Platformy: youtube_long,instagram" required/>
        <button class="primary">Zapisz</button>
      </form>
    </div>
    <div class="card">
      <div class="section-title">Szablony</div>
      <ul>${state.templates.map(t=>`<li><b>${escapeHtml(t.name)}</b> — ${escapeHtml(t.days_of_week)} • ${escapeHtml(t.platforms)}
        <div>
          <label>Poniedziałek tygodnia: <input type="date" id="weekStart-${t.id}"/></label>
          <button onclick="instantiateTemplate(${t.id})">Wygeneruj tydzień</button>
        </div>
      </li>`).join('')}</ul>
    </div>
  </div>`;
}

function renderSettings() {
  return `
  <div class="grid">
    <div class="card">
      <div class="section-title">Wygląd</div>
      <button onclick="toggleTheme()">Przełącz motyw</button>
    </div>
    <div class="card">
      <div class="section-title">Kopie zapasowe</div>
      <a href="backup.php" target="_blank">Pobierz kopię bazy</a>
    </div>
    <div class="card">
      <div class="section-title">Skróty klawiszowe</div>
      <p><code>n</code> – nowy post, <code>f</code> – filtruj, <code>g d/k/p</code> – przejścia, <code>?</code> – pomoc</p>
    </div>
  </div>`;
}

function renderReports() {
  return `
  <div class="grid">
    <div class="card">
      <div class="section-title">Tygodniowy raport publikacji</div>
      <button onclick="loadWeeklyReport()">Odśwież</button>
      <pre id="weeklyOut"></pre>
    </div>
    <div class="card">
      <div class="section-title">Skuteczność serii</div>
      <button onclick="loadSeriesReport()">Odśwież</button>
      <pre id="seriesOut"></pre>
    </div>
  </div>`;
}

document.addEventListener('click', (e)=>{
  if (e.target.matches('nav a[data-view]')) {
    e.preventDefault();
    navTo(e.target.getAttribute('data-view'));
  }
  if (e.target.id === 'logoutLink') {
    e.preventDefault();
    api('logout', {}, 'POST').then(()=>{ state.me=null; render(); });
  }
  if (e.target.id === 'menuBtn') {
    $('#sidebar').classList.toggle('open');
  }
  if (e.target.id === 'themeToggle') toggleTheme();
});

document.addEventListener('change', (e)=>{
  if (e.target.matches('input[type="checkbox"][data-todo]')) {
    api('todos_toggle', { id: Number(e.target.getAttribute('data-todo')), csrf: state.csrf }).then(loadAll).then(render);
  }
});

document.addEventListener('submit', (e)=>{
  if (e.target.id === 'loginForm') {
    e.preventDefault();
    const fd = new FormData(e.target);
    api('login', { email: fd.get('email'), password: fd.get('password') }).then(async ()=>{
      await checkMe(); await loadAll(); render();
    }).catch(()=>toast('Błędny login lub hasło.'));
  }
  if (e.target.id === 'ideaForm') {
    e.preventDefault();
    const fd = new FormData(e.target);
    api('ideas_create', { title: fd.get('title'), description: fd.get('description'), category: fd.get('category'), csrf: state.csrf }).then(loadAll).then(render);
  }
  if (e.target.id === 'todoForm') {
    e.preventDefault();
    const fd = new FormData(e.target);
    api('todos_create', { title: fd.get('title'), description: fd.get('description'), due_date: fd.get('due_date'), csrf: state.csrf }).then(loadAll).then(render);
  }
  if (e.target.id === 'postForm') {
    e.preventDefault();
    const fd = new FormData(e.target);
    const post = Object.fromEntries([...fd.entries()]);
    post.series_id = post.series_id ? Number(post.series_id) : null;
    const payload = { post, csrf: state.csrf };
    const action = post.id ? 'posts_update' : 'posts_create';
    if (post.id) payload.id = Number(post.id);
    api(action, payload).then(loadAll).then(()=>{ navTo('posts'); });
  }
  if (e.target.id === 'tplForm') {
    e.preventDefault();
    const fd = new FormData(e.target);
    api('templates_create', { name: fd.get('name'), days_of_week: fd.get('days'), platforms: fd.get('platforms'), csrf: state.csrf }).then(loadAll).then(render);
  }
});

function newPost() { $('#app').insertAdjacentHTML('beforeend', postEditor()); }
function editPost(id) { const p = state.posts.find(x=>x.id==id); $('#app').insertAdjacentHTML('beforeend', postEditor(p)); }
function postEditor(p={}) {
  return `
  <div class="card" id="postEditor">
    <h3>${p.id?'Edytuj':'Nowy'} post</h3>
    <form id="postForm">
      ${p.id?`<input type="hidden" name="id" value="${p.id}"/>`:''}
      <label>Platforma<br>
        <select name="platform">${['youtube_long','youtube_short','instagram','tiktok'].map(k=>`<option value="${k}" ${p.platform===k?'selected':''}>${platformLabel(k)}</option>`).join('')}</select>
      </label><br>
      <label>Tytuł<br><input name="title" value="${escapeHtmlAttr(p.title||'')}" required/></label><br>
      <label>Opis<br><textarea name="description">${escapeHtml(p.description||'')}</textarea></label><br>
      <label>Data publikacji<br><input type="datetime-local" name="publish_at" value="${(p.publish_at||'').replace(' ','T')}"/></label><br>
      <label>Status<br>
        <select name="status">${['idea','in_production','ready','scheduled','published'].map(s=>`<option value="${s}" ${p.status===s?'selected':''}>${statusLabel(s)}</option>`).join('')}</select>
      </label><br>
      <label>Tagi (comma)<br><input name="tags" value="${escapeHtmlAttr(p.tags||'')}"/></label><br>
      <label>Seria<br>
        <select name="series_id">
          <option value="">—</option>
          ${state.series.map(s=>`<option value="${s.id}" ${p.series_id==s.id?'selected':''}>${escapeHtml(s.name)}</option>`).join('')}
        </select>
      </label><br><br>
      <button class="primary">${p.id?'Zapisz zmiany':'Utwórz'}</button>
    </form>
  </div>`;
}

function duplicatePost(id) {
  const platforms = prompt('Na jakie platformy skopiować? Np.: instagram,tiktok');
  if (!platforms) return;
  api('posts_duplicate_to_platforms', { id, platforms: platforms.split(',').map(s=>s.trim()), csrf: state.csrf }).then(loadAll).then(render);
}

function quickStatus(id, next) {
  api('posts_update', { id, post: { status: next }, csrf: state.csrf }).then(loadAll).then(render);
}
function nextStatus(s) {
  const order = ['idea','in_production','ready','scheduled','published'];
  const i = order.indexOf(s);
  return order[Math.min(order.length-1, i+1)];
}

function applyFilters() {
  state.filters.platform = $('#filterPlatform').value;
  state.filters.status = $('#filterStatus').value;
  state.filters.q = $('#filterQ').value;
  loadAll().then(render);
}

function instantiateTemplate(id) {
  const v = document.getElementById(`weekStart-${id}`).value;
  if (!v) return toast('Wybierz poniedziałek tygodnia.');
  api('templates_instatiate_week', { template_id: id, start_date: v, csrf: state.csrf }).then(loadAll).then(()=>navTo('calendar'));
}

function loadWeeklyReport() {
  const thisMonday = new Date(); thisMonday.setDate(thisMonday.getDate() - ((thisMonday.getDay()+6)%7));
  const start = thisMonday.toISOString().slice(0,10);
  api('report_weekly', {}, 'GET', { start }).then(data=>{
    document.getElementById('weeklyOut').textContent = JSON.stringify(data, null, 2);
  });
}
function loadSeriesReport() {
  api('report_series_effectiveness', {}, 'GET').then(data=>{
    document.getElementById('seriesOut').textContent = JSON.stringify(data, null, 2);
  });
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  setTheme(cur === 'light' ? 'dark' : 'light');
}

function escapeHtml(s='') { const div = document.createElement('div'); div.textContent = s; return div.innerHTML; }
function escapeHtmlAttr(s='') { return (s+'').replace(/"/g,'&quot;'); }
function groupBy(arr, keyFn){ return arr.reduce((m,x)=>{const k=keyFn(x); (m[k]=m[k]||[]).push(x); return m},{}); }
function startOfMonth(d){ return new Date(d.getFullYear(), d.getMonth(), 1); }
function buildMonthDays(start){ const days=[]; const cur = new Date(start.getFullYear(), start.getMonth(), 1); const month = cur.getMonth(); while (cur.getMonth()===month){ days.push(new Date(cur)); cur.setDate(cur.getDate()+1); } return days; }

(async function() {
  document.getElementById('sidebar').addEventListener('click', (e)=>{
    if (e.target.matches('a')) document.getElementById('sidebar').classList.remove('open');
  });
  await checkMe();
  if (state.me) { await loadAll(); }
  shortcutSetup();
  render();
})();
"""))

# README
open(f"{base}/README.md","w").write(textwrap.dedent("""
# Solo Creator Planner (PHP + SQLite)
Minimalna aplikacja webowa do planowania i produkcji treści (YouTube, Instagram Reels, TikTok).

## Szybki start (lokalnie z PHP)
1. Uruchom w katalogu projektu:  
   `php -S localhost:8000`
2. Otwórz: http://localhost:8000
3. Zaloguj się: **admin@example.com** / **admin** (zmień hasło po pierwszym logowaniu).

## Struktura
- `index.php` – UI (SPA, AJAX)
- `api.php` – REST‑owe endpoints (JSON)
- `db.php` – połączenie z SQLite + inicjalizacja schematu
- `auth.php` – sesje, CSRF
- `export_csv.php`, `export_ics.php`, `backup.php` – eksport/kopie
- `assets/style.css`, `assets/app.js` – frontend
- `schema.sql` – definicja bazy

## Bezpieczeństwo
- Logowanie z hasłem (bcrypt), sesja PHP
- CSRF token w żądaniach modyfikujących
- PDO + prepared statements (SQLi)
- Sanityzacja danych na wyjściu (escape HTML po stronie klienta)

## Walidacje per platforma
- YouTube Long: opis do 5000 znaków
- YouTube Short: do 150 znaków
- Instagram & TikTok: do 2200 znaków

## Automatyzacje
- Duplikacja posta na różne platformy (`posts_duplicate_to_platforms`)
- Generowanie tygodnia z szablonu (`templates_instatiate_week`)

## Raporty
- `report_weekly` – agregacja wg platformy/statusu w zakresie tygodnia
- `report_series_effectiveness` – podsumowanie wg serii

## Eksport
- CSV: `/export_csv.php`
- iCalendar (.ics): `/export_ics.php` (wydarzenia z `scheduled` i `published`)

## Uwaga
To szkielet MVP. Warto dodać: zmianę hasła, role zespołowe, drag&drop w Kanban, integracje API, paginację, testy.
"""))

# Zip the project
zip_path = "/mnt/data/solo-creator-app.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base)
            z.write(full, arcname=f"solo-creator-app/{rel}")

zip_path