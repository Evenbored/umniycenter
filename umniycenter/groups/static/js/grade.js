const gradesState = {
  debounceTimer: null,
  teachersLoaded: false,
};

document.addEventListener('DOMContentLoaded', () => {
  bindGradeFilters();
  loadGrades();
});

function bindGradeFilters() {
  ['fSort', 'fTeacher', 'fStatus'].forEach(id => {
    const element = document.getElementById(id);
    if (element) element.addEventListener('change', loadGrades);
  });

  const search = document.getElementById('fSearch');
  if (search) {
    search.addEventListener('input', () => {
      window.clearTimeout(gradesState.debounceTimer);
      gradesState.debounceTimer = window.setTimeout(loadGrades, 300);
    });
  }
}

function applyFilters() {
  loadGrades();
}

function resetFilters() {
  const sort = document.getElementById('fSort');
  const teacher = document.getElementById('fTeacher');
  const status = document.getElementById('fStatus');
  const search = document.getElementById('fSearch');

  if (sort) sort.value = '';
  if (teacher) teacher.value = '';
  if (status) status.value = 'active';
  if (search) search.value = '';

  loadGrades();
}

async function loadGrades() {
  const list = document.getElementById('grdList');
  if (!list) return;

  list.innerHTML = '<div class="grd__empty">Загрузка классов...</div>';

  try {
    const response = await fetch(`/api/v1/groups/my/?${buildGradeQuery()}`, {
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });

    if (!response.ok) throw new Error(`API returned ${response.status}`);

    const grades = await response.json();
    updateTeacherFilter(grades);
    renderGrades(Array.isArray(grades) ? grades : grades.results || []);
  } catch (error) {
    list.innerHTML = '<div class="grd__empty">Не удалось загрузить классы</div>';
    console.error(error);
  }
}

function buildGradeQuery() {
  const params = new URLSearchParams();
  const sort = document.getElementById('fSort')?.value;
  const teacher = document.getElementById('fTeacher')?.value;
  const status = document.getElementById('fStatus')?.value;
  const search = document.getElementById('fSearch')?.value.trim();

  if (sort) params.set('ordering', sort);
  if (teacher) params.set('teacher', teacher);
  if (status) params.set('status', status);
  if (search) params.set('search', search);

  return params.toString();
}

function updateTeacherFilter(grades) {
  const select = document.getElementById('fTeacher');
  if (!select || gradesState.teachersLoaded) return;

  const teachers = new Map();
  grades.forEach(grade => {
    if (grade.teacher && grade.teacher_name) {
      teachers.set(String(grade.teacher), grade.teacher_name);
    }
  });

  Array.from(teachers.entries())
    .sort((a, b) => a[1].localeCompare(b[1], 'ru'))
    .forEach(([id, name]) => {
      const option = document.createElement('option');
      option.value = id;
      option.textContent = name;
      select.appendChild(option);
    });

  gradesState.teachersLoaded = true;
}

function renderGrades(grades) {
  const list = document.getElementById('grdList');
  const footer = document.getElementById('grdFooter');

  if (!grades.length) {
    list.innerHTML = '<div class="grd__empty">Классы не найдены</div>';
    if (footer) footer.textContent = 'Найдено: 0';
    return;
  }

  list.innerHTML = grades.map(renderGradeCard).join('');
  if (footer) footer.textContent = `Найдено: ${grades.length}`;
}

function renderGradeCard(grade) {
  const statusText = grade.is_active ? 'Активный' : 'Архивный';
  const statusClass = grade.is_active ? 'grd__meta-green' : 'grd__meta-dark';
  const dropdownId = `grd-drop-${grade.id}`;

  return `
    <div class="grd__card">
      <div class="grd__card-left">
        <a class="grd__card-name" href="#">
          <svg class="grd__card-name-icon" width="18" height="18" fill="none" viewBox="0 0 24 24">
            <rect x="3" y="3" width="18" height="18" rx="2" stroke="#22c55e" stroke-width="1.8" />
            <path d="M7 8h10M7 12h10M7 16h6" stroke="#22c55e" stroke-width="1.8" stroke-linecap="round" />
          </svg>${escapeHtml(grade.course_name)} - Группа ${escapeHtml(grade.number)}
        </a>
        <div class="grd__card-meta">
          <div class="grd__meta-row">
            <svg width="14" height="14" fill="none" viewBox="0 0 20 20">
              <circle cx="10" cy="10" r="9" fill="#22c55e" />
              <path d="M7 10.5l2 2 4-4" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="grd__meta-dark">${grade.students_count || 0} учеников</span>
          </div>
          <div class="grd__meta-row">
            <svg width="13" height="13" fill="none" viewBox="0 0 16 16">
              <path d="M3 8l3.5 3.5L13 5" stroke="#22c55e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="${statusClass}">${statusText}</span>
          </div>
          <div class="grd__meta-row">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24">
              <rect x="3" y="3" width="18" height="18" rx="2" stroke="#3b82f6" stroke-width="1.7" />
              <path d="M7 8h10M7 12h10M7 16h6" stroke="#3b82f6" stroke-width="1.7" stroke-linecap="round" />
            </svg>
            <span class="grd__meta-link">${escapeHtml(grade.course_name)}</span>
          </div>
        </div>
      </div>

      <div class="grd__card-center">
        <div class="grd__meta-row">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
            <path d="M3 21h18M3 10.5L12 3l9 7.5" stroke="#3b82f6" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
            <rect x="7" y="13" width="4" height="8" rx="1" stroke="#3b82f6" stroke-width="1.7" />
            <rect x="13" y="13" width="4" height="8" rx="1" stroke="#3b82f6" stroke-width="1.7" />
          </svg>
          <a class="grd__meta-link" href="#">Центр развития интеллекта «Умный», Ломоносов</a>
        </div>
        <div class="grd__meta-row">
          <svg width="13" height="13" fill="none" viewBox="0 0 24 24">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" stroke="#6b7280" stroke-width="1.7" />
            <circle cx="12" cy="9" r="2.5" stroke="#6b7280" stroke-width="1.7" />
          </svg>
          <span>Санкт-Петербург, Ломоносов, ул. Костылева, д. 18</span>
        </div>
      </div>

      <div class="grd__card-teacher">
        <div class="grd__teacher-ava" style="background:#dbeafe;">
          <svg width="46" height="46" viewBox="0 0 46 46">
            <text x="23" y="29" text-anchor="middle" font-size="14" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" fill="#1e40af" font-weight="600">${getInitials(grade.teacher_name)}</text>
          </svg>
        </div>
        <div>
          <div class="grd__teacher-lbl">Учитель</div>
          <a class="grd__teacher-name" href="#">${escapeHtml(grade.teacher_name)}</a>
        </div>
      </div>

      <div class="grd__card-dots">
        <button class="grd__btn-dots" onclick="toggleDrop(event,'${dropdownId}')">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="5" r="1.6" />
            <circle cx="12" cy="12" r="1.6" />
            <circle cx="12" cy="19" r="1.6" />
          </svg>
          <div class="grd__dropdown" id="${dropdownId}">
            <a href="#">Открыть</a>
            <a href="#" class="grd__dropdown-danger">${grade.is_active ? 'Архивировать' : 'Вернуть в активные'}</a>
          </div>
        </button>
      </div>
    </div>
  `;
}

function toggleDrop(e, id) {
  e.stopPropagation();
  const el = document.getElementById(id);
  if (!el) return;

  const wasOpen = el.classList.contains('grd__dropdown--open');
  document.querySelectorAll('.grd__dropdown--open').forEach(m => m.classList.remove('grd__dropdown--open'));
  if (!wasOpen) el.classList.add('grd__dropdown--open');
}

document.addEventListener('click', () => {
  document.querySelectorAll('.grd__dropdown--open').forEach(m => m.classList.remove('grd__dropdown--open'));
});

function getInitials(name) {
  return String(name || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('') || 'У';
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}
