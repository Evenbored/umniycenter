const studentsState = {
  debounceTimer: null,
  period: '',
};

document.addEventListener('DOMContentLoaded', () => {
  bindStudentFilters();
  loadStudentGroups();
  loadStudents();
});

function bindStudentFilters() {
  ['sGroup', 'sStatus', 'sSort', 'sDateFrom', 'sDateTo'].forEach(id => {
    const element = document.getElementById(id);
    if (element) element.addEventListener('change', () => {
      if (id === 'sDateFrom' || id === 'sDateTo') studentsState.period = '';
      loadStudents();
    });
  });

  const search = document.getElementById('sSearch');
  if (search) {
    search.addEventListener('input', () => {
      window.clearTimeout(studentsState.debounceTimer);
      studentsState.debounceTimer = window.setTimeout(loadStudents, 300);
    });
  }

  document.querySelectorAll('[data-period]').forEach(button => {
    button.addEventListener('click', () => {
      studentsState.period = button.dataset.period;
      document.getElementById('sDateFrom').value = '';
      document.getElementById('sDateTo').value = '';
      setActivePeriodLink(button);
      loadStudents();
    });
  });
}

async function loadStudentGroups() {
  const select = document.getElementById('sGroup');
  if (!select) return;

  try {
    const response = await fetch('/api/v1/groups/my/?status=active', {
      headers: apiHeaders(),
    });

    if (!response.ok) throw new Error(`Groups API returned ${response.status}`);

    const groups = normalizeApiList(await response.json());
    groups.forEach(group => {
      const option = document.createElement('option');
      option.value = group.id;
      option.textContent = `${group.course_name} - Группа ${group.number}`;
      select.appendChild(option);
    });
  } catch (error) {
    console.error(error);
  }
}

async function loadStudents() {
  const list = document.getElementById('studentsList');
  if (!list) return;

  list.innerHTML = '<div class="grd__empty">Загрузка учеников...</div>';

  try {
    const response = await fetch(`/api/v1/students/my/?${buildStudentsQuery()}`, {
      headers: apiHeaders(),
    });

    if (!response.ok) throw new Error(`Students API returned ${response.status}`);

    const students = normalizeApiList(await response.json());
    renderStudents(students);
  } catch (error) {
    list.innerHTML = '<div class="grd__empty">Не удалось загрузить учеников</div>';
    console.error(error);
  }
}

function buildStudentsQuery() {
  const params = new URLSearchParams();
  const group = document.getElementById('sGroup')?.value;
  const status = document.getElementById('sStatus')?.value;
  const sort = document.getElementById('sSort')?.value;
  const dateFrom = document.getElementById('sDateFrom')?.value;
  const dateTo = document.getElementById('sDateTo')?.value;
  const search = document.getElementById('sSearch')?.value.trim();

  if (group) params.set('group', group);
  if (status) params.set('status', status);
  if (sort) params.set('ordering', sort);
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  if (studentsState.period) params.set('period', studentsState.period);
  if (search) params.set('search', search);

  return params.toString();
}

function renderStudents(students) {
  const list = document.getElementById('studentsList');
  const footer = document.getElementById('studentsFooter');

  if (!students.length) {
    list.innerHTML = '<div class="grd__empty">Ученики не найдены</div>';
    if (footer) footer.textContent = 'Найдено: 0';
    return;
  }

  list.innerHTML = students.map(renderStudentCard).join('');
  if (footer) footer.textContent = `Найдено: ${students.length}`;
}

function renderStudentCard(item) {
  const statusText = item.student_is_active ? 'Активный' : 'Архивный';
  const statusClass = item.student_is_active ? 'grd__meta-green' : 'grd__meta-dark';
  const dropdownId = `student-drop-${item.student}`;
  const city = item.student_city || 'Город не указан';
  const contact = item.student_phone || item.student_email || 'Контакты не указаны';
  const groups = item.groups || [];
  const primaryGroup = groups[0] || {};
  const groupsText = groups.length
    ? groups.map(group => `${group.course_name}, группа ${group.group_number}`).join('; ')
    : 'Класс не указан';
  const teachersText = Array.from(new Set(groups.map(group => group.teacher_name).filter(Boolean))).join(', ') || 'Учитель не указан';

  return `
    <div class="grd__card std__card">
      <div class="grd__card-left std__student-main">
        <div class="std__student-heading">
          <div class="std__avatar">${getInitials(item.student_full_name)}</div>
          <a class="grd__card-name std__student-name" href="#">${escapeHtml(item.student_full_name)}</a>
        </div>
        <div class="grd__card-meta std__meta">
          <div class="grd__meta-row">
            <svg width="14" height="14" fill="none" viewBox="0 0 16 16">
              <path d="M3 8l3.5 3.5L13 5" stroke="#22c55e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="${statusClass}">${statusText}</span>
          </div>
          <div class="grd__meta-row">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07A19.5 19.5 0 0 1 5.15 12.8 19.8 19.8 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.77.62 2.61a2 2 0 0 1-.45 2.11L8 9.67a16 16 0 0 0 6.33 6.33l1.23-1.23a2 2 0 0 1 2.11-.45c.84.29 1.71.5 2.61.62A2 2 0 0 1 22 16.92Z" stroke="#22c55e" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>${escapeHtml(contact)}</span>
          </div>
          <!--
          <div class="std__rating">
            <span>85%</span>
            <span>3617</span>
            <span>3380</span>
          </div>
          -->
        </div>
      </div>

      <div class="grd__card-center std__student-center">
        <div class="grd__meta-row">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
            <path d="M3 21h18M3 10.5L12 3l9 7.5" stroke="#3b82f6" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
            <rect x="7" y="13" width="4" height="8" rx="1" stroke="#3b82f6" stroke-width="1.7" />
            <rect x="13" y="13" width="4" height="8" rx="1" stroke="#3b82f6" stroke-width="1.7" />
          </svg>
          <a class="grd__meta-link" href="#">Центр развития интеллекта "Умный", Ломоносов</a>
        </div>
        <div class="grd__meta-row">
          <svg width="13" height="13" fill="none" viewBox="0 0 24 24">
            <rect x="3" y="3" width="18" height="18" rx="2" stroke="#22c55e" stroke-width="1.7" />
            <path d="M7 8h10M7 12h10M7 16h6" stroke="#22c55e" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          <span class="grd__meta-link">${escapeHtml(groupsText)}</span>
        </div>
        <div class="grd__meta-row">
          <svg width="13" height="13" fill="none" viewBox="0 0 24 24">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" stroke="#22c55e" stroke-width="1.7" />
            <circle cx="12" cy="9" r="2.5" stroke="#22c55e" stroke-width="1.7" />
          </svg>
          <span>${escapeHtml(city)}</span>
        </div>
      </div>

      <div class="grd__card-teacher std__teacher-col">
        <div class="grd__teacher-ava" style="background:#dbeafe;">
          <svg width="46" height="46" viewBox="0 0 46 46">
            <text x="23" y="29" text-anchor="middle" font-size="14" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" fill="#1e40af" font-weight="600">${getInitials(primaryGroup.teacher_name)}</text>
          </svg>
        </div>
        <div>
          <div class="grd__teacher-lbl">Учитель</div>
          <a class="grd__teacher-name" href="#">${escapeHtml(teachersText)}</a>
        </div>
      </div>

      <div class="grd__card-dots">
        <button class="grd__btn-dots" onclick="toggleStudentDrop(event,'${dropdownId}')">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="5" r="1.6" />
            <circle cx="12" cy="12" r="1.6" />
            <circle cx="12" cy="19" r="1.6" />
          </svg>
          <div class="grd__dropdown" id="${dropdownId}">
            <a href="#">Открыть</a>
            <a href="#">Написать</a>
          </div>
        </button>
      </div>
    </div>
  `;
}

function resetStudentFilters() {
  document.getElementById('sGroup').value = '';
  document.getElementById('sStatus').value = 'active';
  document.getElementById('sSort').value = '';
  document.getElementById('sDateFrom').value = '';
  document.getElementById('sDateTo').value = '';
  document.getElementById('sSearch').value = '';
  studentsState.period = '';
  setActivePeriodLink(null);
  loadStudents();
}

function toggleStudentDrop(e, id) {
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

function setActivePeriodLink(activeButton) {
  document.querySelectorAll('[data-period]').forEach(button => {
    button.classList.toggle('std__period-active', button === activeButton);
  });
}

function normalizeApiList(data) {
  return Array.isArray(data) ? data : data.results || [];
}

function apiHeaders() {
  return {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  };
}

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
