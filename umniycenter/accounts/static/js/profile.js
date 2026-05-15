function tzpAddTask() {
  const input = document.getElementById('tzp-input');
  const isImportant = document.getElementById('tzp-important-check').checked;
  const text = input.value.trim();
  if (!text) return;

  const list = document.getElementById('tzp-task-list');
  const empty = document.getElementById('tzp-empty-msg');
  if (empty) empty.remove();

  const item = document.createElement('div');
  item.className = 'tzp-task-item' + (isImportant ? ' tzp-important' : '');

  item.innerHTML = `
      <input type="checkbox" class="tzp-task-check" onchange="this.parentElement.style.opacity=this.checked?'0.45':'1'">
      <span>${text}</span>
      <button class="tzp-task-del" onclick="this.parentElement.remove(); tzpCheckEmpty()">×</button>
    `;
  const tg = 'tzp-task-del'; // Класс, который ищем

  // Ищем только внутри родителя
  let count = list.querySelectorAll(`.${tg}`).length;
  if (count < 10) {
    list.appendChild(item);
  }
  console.log(count)
  input.value = '';
  document.getElementById('tzp-important-check').checked = false;
}

document.getElementById('tzp-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') tzpAddTask();
});

function tzpCheckEmpty() {
  const list = document.getElementById('tzp-task-list');
  if (list.children.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'tzp-empty';
    msg.id = 'tzp-empty-msg';
    msg.textContent = 'Список задач пуст';
    list.appendChild(msg);
  }
}