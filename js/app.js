let postsCache = [];

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('nav a').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      loadView(a.getAttribute('data-view'));
    });
  });
  document.getElementById('themeToggle').addEventListener('click', () => {
    document.body.dataset.theme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
  });
  loadView('dashboard');
});

function loadView(view) {
  fetch('views/' + view + '.html')
    .then(r => r.text())
    .then(html => {
      document.getElementById('content').innerHTML = html;
      document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.getAttribute('data-view') === view));
      if (window[view + 'Init']) {
        window[view + 'Init']();
      }
    });
}

function dashboardInit() {
  fetch('api/posts.php')
    .then(r => r.json())
    .then(data => {
      const upcoming = data.filter(p => p.status === 'scheduled').slice(0,5);
      const list = upcoming.map(p => `<li>${p.title} (${p.platform}) - ${p.publish_date}</li>`).join('');
      document.getElementById('upcoming').innerHTML = `<ul>${list}</ul>`;
    });
  fetch('api/todos.php')
    .then(r=>r.json())
    .then(data=>{
      const today = new Date().toISOString().slice(0,10);
      const list = data.filter(t=>t.due_date===today && t.status!=='done')
        .map(t=>`<li>${t.title}</li>`).join('');
      document.getElementById('todayTodos').innerHTML = list || '<li>Brak zadań</li>';
    });
}

function postsInit() {
  fetch('api/posts.php')
    .then(r => r.json())
    .then(data => {
      postsCache = data;
      renderPosts(data);
      const search = document.getElementById('postSearch');
      if (search) {
        search.addEventListener('input', () => {
          const term = search.value.toLowerCase();
          renderPosts(postsCache.filter(p => p.title.toLowerCase().includes(term)));
        });
      }
    });
}

function ideasInit() {
  fetch('api/ideas.php')
    .then(r => r.json())
    .then(data => {
      const list = data.map(i => `<li>${i.title}</li>`).join('');
      document.getElementById('ideasList').innerHTML = list;
    });
}

function todosInit() {
  fetch('api/todos.php')
    .then(r => r.json())
    .then(data => {
      const list = data.map(t => `<li><input type='checkbox' ${t.status==='done'?'checked':''} data-id='${t.id}'/> ${t.title}</li>`).join('');
      const ul = document.getElementById('todoList');
      ul.innerHTML = list;
      ul.querySelectorAll('input').forEach(ch => ch.addEventListener('change', () => {
        fetch('api/todos.php?id=' + ch.dataset.id, {
          method:'PUT',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({status: ch.checked ? 'done':'open'})
        });
      }));
    });
}

function calendarInit() {
  fetch('api/posts.php')
    .then(r => r.json())
    .then(data => {
      const today = new Date();
      const year = today.getFullYear();
      const month = today.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      let html = '<table class="calendar"><tr>' + ['Pn','Wt','Śr','Cz','Pt','So','Nd'].map(d=>`<th>${d}</th>`).join('') + '</tr><tr>';
      for (let i = 0; i < (firstDay.getDay() + 6) % 7; i++) html += '<td></td>';
      for (let d = 1; d <= lastDay.getDate(); d++) {
        const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const posts = data.filter(p => p.publish_date === dateStr);
        html += `<td><div class='date'>${d}</div>${posts.map(p=>`<div class='cal-post'>${p.title}</div>`).join('')}</td>`;
        if ((d + (firstDay.getDay()+6)%7) % 7 === 0) html += '</tr><tr>';
      }
      html += '</tr></table>';
      document.getElementById('calendar').innerHTML = html;
    });
}

function kanbanInit() {
  const statuses = ['idea','production','ready','scheduled','published'];
  fetch('api/posts.php')
    .then(r=>r.json())
    .then(data => {
      postsCache = data;
      const board = document.getElementById('kanban');
      board.innerHTML = statuses.map(s=>`<div class='column' data-status='${s}'><h3>${s}</h3><div class='col-content'></div></div>`).join('');
      statuses.forEach(s => {
        const col = board.querySelector(`[data-status='${s}'] .col-content`);
        data.filter(p=>p.status===s).forEach(p=>{
          const card = document.createElement('div');
          card.className = 'card';
          card.textContent = p.title;
          card.draggable = true;
          card.dataset.id = p.id;
          card.addEventListener('dragstart', e => e.dataTransfer.setData('id', p.id));
          col.appendChild(card);
        });
      });
      board.querySelectorAll('.column').forEach(col => {
        col.addEventListener('dragover', e => e.preventDefault());
        col.addEventListener('drop', e => {
          const id = e.dataTransfer.getData('id');
          const status = col.dataset.status;
          const post = postsCache.find(p=>p.id==id);
          fetch('api/posts.php?id=' + id, {
            method:'PUT',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({...post, status})
          }).then(()=>kanbanInit());
        });
      });
    });
}

function renderPosts(data){
  const rows = data.map(p => `<tr><td>${p.title}</td><td>${p.platform}</td><td>${p.status}</td></tr>`).join('');
  document.getElementById('postsTable').innerHTML = rows;
}

document.addEventListener('keydown', e => {
  if (e.altKey) {
    const map = {'1':'dashboard','2':'calendar','3':'kanban','4':'posts','5':'ideas','6':'todos','7':'settings','8':'reports'};
    if (map[e.key]) {
      loadView(map[e.key]);
    }
  }
});
