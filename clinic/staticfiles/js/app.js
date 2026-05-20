// ============ SIDEBAR TOGGLE ============
let sidebarOpen = false;

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const hamburger = document.getElementById('hamburgerBtn');

  if (sidebarOpen) {
    sidebarOpen = false;
    sidebar.classList.add('-translate-x-full', 'sidebar-hidden');
    sidebar.classList.remove('sidebar-open');
    overlay.classList.remove('visible');
    if (hamburger) hamburger.classList.remove('is-open');
    setTimeout(() => { if (!sidebarOpen) overlay.classList.add('hidden'); }, 450);
  } else {
    sidebarOpen = true;
    overlay.classList.remove('hidden');
    void overlay.offsetWidth;
    overlay.classList.add('visible');
    sidebar.classList.remove('-translate-x-full', 'sidebar-hidden');
    sidebar.classList.add('sidebar-open');
    if (hamburger) hamburger.classList.add('is-open');
  }
}

function closeSidebarMobile() {
  if (window.innerWidth < 1024 && sidebarOpen) {
    toggleSidebar();
  }
}

// ============ DESKTOP SIDEBAR TOGGLE ============
let desktopSidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';

function toggleDesktopSidebar(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }

  console.log('toggleDesktopSidebar called');
  const sidebar = document.getElementById('sidebar');
  const wrapper = document.getElementById('main-wrapper');

  if (!sidebar || !wrapper) {
    console.error('Sidebar or wrapper not found');
    return;
  }

  desktopSidebarCollapsed = !desktopSidebarCollapsed;
  localStorage.setItem('sidebarCollapsed', desktopSidebarCollapsed);

  updateSidebarState();
}

function updateSidebarState() {
  const sidebar = document.getElementById('sidebar');
  const wrapper = document.getElementById('main-wrapper');
  const icon = document.getElementById('toggleIcon');

  if (desktopSidebarCollapsed) {
    sidebar.classList.add('sidebar-collapsed');
    wrapper.classList.add('content-expanded');
    wrapper.classList.remove('lg:ml-72');
    if (icon) icon.style.transform = 'rotate(180deg)';
  } else {
    sidebar.classList.remove('sidebar-collapsed');
    wrapper.classList.remove('content-expanded');
    wrapper.classList.add('lg:ml-72');
    if (icon) icon.style.transform = 'rotate(0deg)';
  }
}

// ============ HTMX PAGE NAVIGATION ============
function setActivePage(el, title, breadcrumb) {
  // Update page title & breadcrumb
  document.getElementById('pageTitle').textContent = title;
  document.getElementById('breadcrumb').textContent = breadcrumb;
  document.title = clinicName + ' - ' + title;

  // Update active sidebar link
  document.querySelectorAll('.sidebar-link').forEach(link => link.classList.remove('active'));
  if (el) el.classList.add('active');

  // Close dropdowns
  closeAllDropdowns();

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============ MOBILE SEARCH ============
let mobileSearchOpen = false;

function toggleMobileSearch() {
  const overlay = document.getElementById('mobileSearchOverlay');
  const input = document.getElementById('mobileSearchInput');

  if (mobileSearchOpen) {
    mobileSearchOpen = false;
    overlay.classList.remove('search-active');
    input.blur();
  } else {
    mobileSearchOpen = true;
    overlay.classList.add('search-active');
    setTimeout(() => input.focus(), 350);
  }
}

function clearMobileSearch() {
  const input = document.getElementById('mobileSearchInput');
  const clearBtn = document.getElementById('mobileSearchClear');
  input.value = '';
  clearBtn.classList.add('hidden');
  input.focus();
}

// ============ DROPDOWNS ============
function toggleNotifications() {
  const dd = document.getElementById('notificationsDropdown');
  const pd = document.getElementById('profileDropdown');
  pd.classList.add('hidden');
  dd.classList.toggle('hidden');
}

function toggleProfileMenu() {
  const pd = document.getElementById('profileDropdown');
  const dd = document.getElementById('notificationsDropdown');
  dd.classList.add('hidden');
  pd.classList.toggle('hidden');
}

function closeAllDropdowns() {
  const nd = document.getElementById('notificationsDropdown');
  const pd = document.getElementById('profileDropdown');
  if (nd) nd.classList.add('hidden');
  if (pd) pd.classList.add('hidden');
}


// ============ MODALS (HTMX-friendly) ============
function syncBodyScrollLock() {
  const hasVisibleFullscreenModal = document.querySelector('.fixed.inset-0:not(.hidden)');
  document.body.style.overflow = hasVisibleFullscreenModal ? 'hidden' : '';
}

function openModal(id) {
    document.querySelectorAll('.action-menu')
        .forEach(m => m.classList.add('hidden'));

    const modal = document.getElementById(id);
    if (!modal) return;

    modal.classList.remove('hidden');
    syncBodyScrollLock();

    requestAnimationFrame(() => {
        const backdrop = modal.querySelector('.modal-backdrop');
        const content = modal.querySelector('.modal-content');
        if (backdrop) backdrop.classList.add('modal-visible');
        if (content) content.classList.add('modal-visible');
    });
}

function openModal1(id) {
  openModal(id);

  if (id === 'prescriptionFormModal') {
    if (typeof loadMedicationTemplates === 'function') {
      loadMedicationTemplates();
    }
    if (typeof updateTreatmentQuickButtons === 'function') {
      updateTreatmentQuickButtons();
    }
    if (typeof updateTemplateButtons === 'function') {
      setTimeout(() => updateTemplateButtons(), 300);
    }
  }

  if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
    lucide.createIcons();
  }
}

document.body.addEventListener("openModal", function (evt) {
    if (evt.detail) {
        openModal(evt.detail);
    }
});

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  const backdrop = modal.querySelector('.modal-backdrop');
  const content = modal.querySelector('.modal-content');
  if (backdrop) backdrop.classList.remove('modal-visible');
  if (content) content.classList.remove('modal-visible');
  setTimeout(() => {
    modal.classList.add('hidden');
    syncBodyScrollLock();
  }, 300);
}



// ============ CHART HELPERS ============
// Destroy existing chart before creating new one (prevents HTMX reload issues)
window.chartInstances = {};

function createChart(canvasId, config) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  // Destroy existing instance
  if (window.chartInstances[canvasId]) {
    window.chartInstances[canvasId].destroy();
  }
  window.chartInstances[canvasId] = new Chart(ctx, config);
  return window.chartInstances[canvasId];
}

// ============ INIT ============
document.addEventListener('DOMContentLoaded', function () {
  // Initialize desktop sidebar state
  updateSidebarState();

  // Mobile search input clear button
  const mInput = document.getElementById('mobileSearchInput');
  const clearBtn = document.getElementById('mobileSearchClear');
  if (mInput && clearBtn) {
    mInput.addEventListener('input', function () {
      clearBtn.classList.toggle('hidden', this.value.length === 0);
    });
  }

  // Close dropdowns on outside click
  document.addEventListener('click', function (e) {
    const notifBtn = e.target.closest('[onclick="toggleNotifications()"]');
    const profBtn = e.target.closest('[onclick="toggleProfileMenu()"]');
    const notifDD = document.getElementById('notificationsDropdown');
    const profDD = document.getElementById('profileDropdown');

    if (notifDD && !notifBtn && !notifDD.contains(e.target)) notifDD.classList.add('hidden');
    if (profDD && !profBtn && !profDD.contains(e.target)) profDD.classList.add('hidden');
  });

  // Escape key handlers
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (mobileSearchOpen) toggleMobileSearch();
      closeAllDropdowns();
    }
  });

  // Desktop sidebar toggle listener
  const desktopBtn = document.getElementById('desktopToggleBtn');
  if (desktopBtn && !desktopBtn.dataset.listenerAttached) {
    desktopBtn.addEventListener('click', toggleDesktopSidebar);
    desktopBtn.dataset.listenerAttached = 'true';
  }
});

// ============ HTMX EVENTS ============
// After HTMX swaps content, run any inline scripts in the partial
document.addEventListener('htmx:afterSettle', function (e) {
  // Execute scripts inside loaded partials
  const scripts = e.detail.target.querySelectorAll('script');
  scripts.forEach(script => {
    const newScript = document.createElement('script');
    if (script.src) {
      newScript.src = script.src;
    } else {
      newScript.textContent = script.textContent;
    }
    document.head.appendChild(newScript);
    setTimeout(() => newScript.remove(), 100);
  });
});






