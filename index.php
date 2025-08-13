<?php
require_once __DIR__ . '/db.php';
$db = get_db();
?>
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SM Manager</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="css/styles.css" />
</head>
<body data-theme="light">
<?php if (!isset($_SESSION['user'])): ?>
<div id="login">
  <h1>Logowanie</h1>
  <input id="user" placeholder="Użytkownik" />
  <input id="pass" type="password" placeholder="Hasło" />
  <button id="loginBtn">Zaloguj</button>
  <div id="loginMsg"></div>
</div>
<script>
document.getElementById('loginBtn').addEventListener('click', ()=>{
  fetch('login.php', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({username:document.getElementById('user').value, password:document.getElementById('pass').value})
  }).then(r=>{
    if(r.ok) location.reload();
    else r.json().then(d=>document.getElementById('loginMsg').innerText=d.error);
  });
});
</script>
<?php else: ?>
<nav>
  <a href="#" data-view="dashboard">Dashboard</a>
  <a href="#" data-view="calendar">Kalendarz</a>
  <a href="#" data-view="kanban">Kanban</a>
  <a href="#" data-view="posts">Posty</a>
  <a href="#" data-view="ideas">Pomysły</a>
  <a href="#" data-view="todos">To-do</a>
  <a href="#" data-view="settings">Ustawienia</a>
  <a href="#" data-view="reports">Raporty</a>
  <button id="themeToggle">🌓</button>
</nav>
<div id="content">Ładowanie...</div>
<script src="js/app.js"></script>
<?php endif; ?>
</body>
</html>