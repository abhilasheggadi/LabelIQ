/**
 * Interactive OCR Verification & Field Correction Logic
 */

let inspectionData = null;
let canvas, ctx;
let canvasImage = null;
let currentBoxes = [];
let activeFieldKey = null;

document.addEventListener('DOMContentLoaded', async () => {
  canvas = document.getElementById('annotationCanvas');
  if (canvas) ctx = canvas.getContext('2d');

  const urlParams = new URLSearchParams(window.location.search);
  const inspectionUuid = urlParams.get('id');

  if (inspectionUuid) {
    await loadInspectionData(inspectionUuid);
  } else {
    // Check sessionStorage
    const stored = sessionStorage.getItem('currentInspection');
    if (stored) {
      inspectionData = JSON.parse(stored);
      initializeCorrectionScreen();
    } else {
      alert('No active inspection record found. Please scan a label first.');
      window.location.href = '/';
    }
  }

  setupEventListeners();
});

async function loadInspectionData(uuid) {
  try {
    const res = await fetch(`/api/inspections/${uuid}`);
    if (!res.ok) throw new Error('Inspection not found');
    inspectionData = await res.json();
    initializeCorrectionScreen();
  } catch (err) {
    alert('Error loading inspection: ' + err.message);
    window.location.href = '/';
  }
}

let activeImageIndex = 0;

function initializeCorrectionScreen() {
  if (!inspectionData) return;

  // Set Metadata info
  const memoIdEl = document.getElementById('memoIdDisplay');
  if (memoIdEl) memoIdEl.textContent = inspectionData.inspection_uuid;

  const catSelect = document.getElementById('categorySelect');
  if (catSelect) catSelect.value = inspectionData.category || 'general';

  // Render Panel Tabs if multiple images
  renderPanelTabs();

  // Load Active Image onto Canvas
  loadActiveCanvasImage();

  // Render Field Form Inputs
  renderFieldInputs();
  renderVerdictSummary();
}

function renderPanelTabs() {
  const canvasCard = document.querySelector('.correction-layout .card');
  if (!canvasCard) return;

  const existing = document.getElementById('correctionPanelTabs');
  if (existing) existing.remove();

  const urls = inspectionData.original_image_urls || [inspectionData.original_image_url];
  if (urls.length > 1) {
    const tabContainer = document.createElement('div');
    tabContainer.id = 'correctionPanelTabs';
    tabContainer.style.cssText = 'display:flex; gap:6px; margin-bottom:10px; padding:0 4px;';

    urls.forEach((url, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip-btn' + (i === activeImageIndex ? ' active' : '');
      btn.textContent = `📷 Panel ${i + 1}`;
      btn.onclick = () => {
        activeImageIndex = i;
        tabContainer.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        loadActiveCanvasImage();
      };
      tabContainer.appendChild(btn);
    });

    const header = canvasCard.querySelector('.card-header');
    if (header) header.insertAdjacentElement('afterend', tabContainer);
  }
}

function loadActiveCanvasImage() {
  const urls = inspectionData.original_image_urls || [inspectionData.original_image_url];
  const activeUrl = urls[activeImageIndex] || urls[0];

  canvasImage = new Image();
  canvasImage.src = activeUrl;
  canvasImage.onload = () => {
    canvas.width = canvasImage.naturalWidth;
    canvas.height = canvasImage.naturalHeight;
    currentBoxes = (inspectionData.ocr_boxes || []).filter(b => (b.image_index || 0) === activeImageIndex);
    redrawCanvas();
  };
}

function redrawCanvas() {
  if (!ctx || !canvasImage) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(canvasImage, 0, 0);

  // Draw OCR boxes for active panel
  currentBoxes.forEach(box => {
    const bbox = box.bbox;
    if (!bbox || bbox.length < 4) return;

    const isMatch = box.field_match === activeFieldKey;
    
    ctx.beginPath();
    ctx.moveTo(bbox[0][0], bbox[0][1]);
    for (let i = 1; i < bbox.length; i++) {
      ctx.lineTo(bbox[i][0], bbox[i][1]);
    }
    ctx.closePath();

    if (isMatch) {
      ctx.lineWidth = 4;
      ctx.strokeStyle = '#38bdf8';
      ctx.fillStyle = 'rgba(56, 189, 248, 0.3)';
      ctx.fill();
    } else if (box.field_match) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#10b981';
    } else {
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    }
    ctx.stroke();

    // Box Label text
    if (box.field_match || isMatch) {
      ctx.font = '14px sans-serif';
      ctx.fillStyle = isMatch ? '#38bdf8' : '#10b981';
      ctx.fillText(box.field_match || box.text, bbox[0][0], Math.max(15, bbox[0][1] - 4));
    }
  });
}

function renderFieldInputs() {
  const container = document.getElementById('fieldsContainer');
  if (!container || !inspectionData.fields) return;

  container.innerHTML = '';

  Object.entries(inspectionData.fields).forEach(([key, field]) => {
    const row = document.createElement('div');
    row.className = `field-row ${key === activeFieldKey ? 'active' : ''}`;
    row.id = `field_row_${key}`;

    const isOk = field.is_present && field.is_valid;
    const statusClass = isOk ? 'ok' : 'missing';
    const panelLabel = (field.image_index !== null && field.image_index !== undefined) ? `[Panel ${field.image_index + 1}]` : '[Missing in all photos]';
    const statusText = isOk ? `✓ COMPLIANT ${panelLabel}` : (field.is_present ? `⚠ NON-STD ${panelLabel}` : '✗ MISSING ACROSS PHOTOS');

    row.innerHTML = `
      <div class="field-header">
        <span class="field-label">${field.label} (${field.rule_number})</span>
        <span class="field-status-tag ${statusClass}">${statusText}</span>
      </div>
      <input type="text" class="form-control field-input" data-key="${key}" value="${field.raw_value || ''}" placeholder="Enter or correct ${field.label}..." />
      ${field.error_message ? `<div style="font-size:0.75rem; color:#f87171; margin-top:4px;">⚠ ${field.error_message}</div>` : ''}
      ${field.font_height_mm ? `<div style="font-size:0.75rem; color:#94a3b8; margin-top:2px;">Measured Font Height: <strong>${field.font_height_mm} mm</strong> (Min required: ${field.min_required_font_mm || '2.0'} mm)</div>` : ''}
    `;

    // Input focus interaction -> switch active image if requirement came from different panel
    const input = row.querySelector('.field-input');
    input.addEventListener('focus', () => {
      activeFieldKey = key;
      document.querySelectorAll('.field-row').forEach(r => r.classList.remove('active'));
      row.classList.add('active');

      if (field.image_index !== null && field.image_index !== undefined && field.image_index !== activeImageIndex) {
        activeImageIndex = field.image_index;
        renderPanelTabs();
        loadActiveCanvasImage();
      } else {
        redrawCanvas();
      }
    });

    container.appendChild(row);
  });
}

function renderVerdictSummary() {
  const verdictBadge = document.getElementById('correctionVerdict');
  const pdfBtn = document.getElementById('correctionPdfBtn');
  
  if (verdictBadge) {
    verdictBadge.className = `verdict-badge ${inspectionData.verdict}`;
    verdictBadge.textContent = inspectionData.verdict === 'PASS' ? '✓ PASS' : (inspectionData.verdict === 'FAIL' ? '✗ FAIL' : '⚠ WARNING');
  }

  if (pdfBtn && inspectionData.pdf_url) {
    pdfBtn.href = inspectionData.pdf_url;
    pdfBtn.style.display = 'inline-flex';
  }
}

function setupEventListeners() {
  // Canvas click interaction to find box
  if (canvas) {
    canvas.addEventListener('click', (e) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;

      // Find box containing click
      let found = null;
      for (const b of currentBoxes) {
        if (b.bbox && b.bbox.length >= 4) {
          const minX = Math.min(...b.bbox.map(p => p[0]));
          const maxX = Math.max(...b.bbox.map(p => p[0]));
          const minY = Math.min(...b.bbox.map(p => p[1]));
          const maxY = Math.max(...b.bbox.map(p => p[1]));

          if (x >= minX && x <= maxX && y >= minY && y <= maxY) {
            found = b;
            break;
          }
        }
      }

      if (found && found.field_match) {
        activeFieldKey = found.field_match;
        redrawCanvas();
        const row = document.getElementById(`field_row_${found.field_match}`);
        if (row) {
          row.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const inp = row.querySelector('.field-input');
          if (inp) inp.focus();
        }
      }
    });
  }

  // Re-evaluate Button
  const reEvalBtn = document.getElementById('reEvaluateBtn');
  if (reEvalBtn) {
    reEvalBtn.addEventListener('click', handleReEvaluation);
  }
}

async function handleReEvaluation() {
  const reEvalBtn = document.getElementById('reEvaluateBtn');
  const spinner = document.getElementById('correctionSpinner');
  
  if (reEvalBtn) reEvalBtn.disabled = true;
  if (spinner) spinner.style.display = 'block';

  // Gather field inputs
  const inputs = document.querySelectorAll('.field-input');
  const correctedFields = {};
  inputs.forEach(inp => {
    const key = inp.getAttribute('data-key');
    correctedFields[key] = inp.value.trim();
  });

  const category = document.getElementById('categorySelect').value;

  const payload = {
    inspection_uuid: inspectionData.inspection_uuid,
    category: category,
    corrected_fields: correctedFields
  };

  try {
    const res = await fetch('/api/corrections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Re-evaluation failed');
    }

    inspectionData = await res.json();
    sessionStorage.setItem('currentInspection', JSON.stringify(inspectionData));
    
    renderFieldInputs();
    renderVerdictSummary();
    alert(`✓ Re-evaluated! New Verdict: ${inspectionData.verdict} (${inspectionData.compliance_score}% Compliant). Evidence PDF regenerated.`);
  } catch (err) {
    alert('Re-evaluation error: ' + err.message);
  } finally {
    if (reEvalBtn) reEvalBtn.disabled = false;
    if (spinner) spinner.style.display = 'none';
  }
}
