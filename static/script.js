// ── MODAL CONTROLS ────────────────────────────────────────────────────────────

function openModal(id) {
  const el = document.getElementById('modal-' + id);
  if (el) el.classList.add('open');
}

function closeModal(id) {
  const el = document.getElementById('modal-' + id);
  if (el) el.classList.remove('open');
}

// Close modal when clicking the dark overlay (not the modal box itself)
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// Close modal on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(el => el.classList.remove('open'));
  }
});


// ── EDIT MODAL PRE-FILL ───────────────────────────────────────────────────────

function openEditModal(id, name, sku, category, totalQty, lowAlert, notes) {
  document.getElementById('editForm').action = '/item/edit/' + id;
  document.getElementById('editName').value     = name;
  document.getElementById('editSku').value      = sku;
  document.getElementById('editTotalQty').value = totalQty;
  document.getElementById('editLowAlert').value = lowAlert;
  document.getElementById('editNotes').value    = notes;

  // Set the correct category option
  const catSelect = document.getElementById('editCategory');
  for (let i = 0; i < catSelect.options.length; i++) {
    catSelect.options[i].selected = (catSelect.options[i].value === category);
  }

  openModal('editItem');
}


// ── TABLE FILTERING ───────────────────────────────────────────────────────────

let currentFilter = 'all';

function setFilter(type, chipEl) {
  currentFilter = type;

  // Update chip visual state
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active-chip'));
  chipEl.classList.add('active-chip');

  applyFilters();
}

function applyFilters() {
  const query = (document.getElementById('searchInput')?.value || '').toLowerCase().trim();

  const rows = document.querySelectorAll('#tableBody tr[data-status]');
  let visibleCount = 0;

  rows.forEach(row => {
    const name     = row.getAttribute('data-name') || '';
    const sku      = row.getAttribute('data-sku') || '';
    const status   = row.getAttribute('data-status') || '';
    const category = row.getAttribute('data-category') || '';

    // Search matches name or SKU
    const matchesSearch = !query || name.includes(query) || sku.includes(query);

    // Filter match
    let matchesFilter = false;
    if      (currentFilter === 'all')        matchesFilter = true;
    else if (currentFilter === 'available')  matchesFilter = status === 'available';
    else if (currentFilter === 'low')        matchesFilter = status === 'low stock';
    else if (currentFilter === 'critical')   matchesFilter = status === 'critical';
    else if (currentFilter === 'equipment')  matchesFilter = category === 'equipment';
    else if (currentFilter === 'consumable') matchesFilter = category === 'consumable';

    const show = matchesSearch && matchesFilter;
    row.style.display = show ? '' : 'none';
    if (show) visibleCount++;
  });

  // Show empty state if nothing matches
  const emptyRow = document.getElementById('emptyRow');
  if (emptyRow) {
    emptyRow.style.display = (visibleCount === 0 && rows.length > 0) ? '' : 'none';
  }

  // Update count
  const info = document.getElementById('paginationInfo');
  if (info) {
    info.textContent = `Showing ${visibleCount} of ${rows.length} items`;
  }
}


// ── FLASH AUTO-DISMISS ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  // Run initial filter count
  applyFilters();

  // Auto-dismiss flash messages after 4 seconds
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (flash) {
    setTimeout(function () {
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(20px)';
      flash.style.transition = 'opacity 0.4s, transform 0.4s';
      setTimeout(() => flash.remove(), 400);
    }, 4000);
  });
});