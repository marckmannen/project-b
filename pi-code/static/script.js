// state
let lang = 'nl';
let pinValue = '';
let dateBuffer = '';   // flat string ddmyyyy

// user orders
let userOrders = [];
let currentPickupOrderId = null; // track which order was picked up for printing
let qrPollInterval = null;
let receiptPrinted = false; // track if receipt was printed (order already completed)

// dispensing timer
const DISPENSING_DURATION_DEFAULT = 10; // fallback seconds
let dispensingTimeLeft = DISPENSING_DURATION_DEFAULT;
let dispensingInterval = null;
const TIMER_CIRCUMFERENCE = 2 * Math.PI * 54; // ~339.292
let dispensingTotal = DISPENSING_DURATION_DEFAULT; // current total for progress ring

// inactivity timeout
const INACTIVITY_LIMIT = 60 * 1000; // 60 seconds
const TIMEOUT_COUNTDOWN = 30; // seconds
let inactivityTimer = null;
let timeoutModalTimer = null;
let timeoutCountdownValue = TIMEOUT_COUNTDOWN;
let endPageTimeout = null; // one-shot timeout for end page

function startEndPageTimeout() {
  console.log('[timeout] startEndPageTimeout called');
  if (endPageTimeout) clearTimeout(endPageTimeout);
  endPageTimeout = setTimeout(() => {
    console.log('[timeout] end page timeout fired after', INACTIVITY_LIMIT, 'ms');
    endPageTimeout = null;
    showTimeoutModal();
  }, INACTIVITY_LIMIT);
}

// translations
const T = {
  nl: {
    wTitle: 'Welkom',
    wSub: 'bij de medicijnkluis',
    wProceed: 'klik om door te gaan',
    flagLabel: 'click here for\nenglish',
    loginHeader: 'Aanmelden',
    btnManual: 'inloggen\nhandmatig',
    btnQr: 'inloggen\nQr-code',
    manualHeader: 'Handmatig inloggen',
    btnPin: 'inloggen met\npincode',
    btnDate: 'inloggen met\ngeboortedatum',
    pinHeader: 'Pincode invoeren',
    pinLabel: 'Vul uw pincode in',
    dateHeader: 'Geboortedatum invoeren',
    dateLabel: 'Vul uw geboortedatum in',
    qrHeader: 'QR-code scannen',
    qrMsg: 'Plaats uw QR-code voor de scanner',
    dispHeader: 'Medicijnen komen',
    dispMsg: 'Wacht tot de deur opengaat',
    dispTimerLabel: 'seconden',
    endHeader: 'Bedankt voor uw komst',
    endMsg: 'Heeft u alle medicijnen uit het vak gehaald?',
    finishBtn: 'Klik hier om af te ronden',
    btnPrint: 'Bijsluiter printen',
    timeoutMessage: 'Systeem wordt reset door inactiviteit.',
    timeoutSubtitle: 'Klik ergens om te heractiveren',
    ordersHeader: 'Uw openstaande orders',
    ordersError: 'Geen openstaande orders gevonden.',
    compartmentNotAssigned: 'Vak nog niet toegewezen. Contacteer de apotheek.'
  },
  en: {
    wTitle: 'Welcome',
    wSub: 'to the medicine vault',
    wProceed: 'click to proceed',
    flagLabel: 'klik hier voor\nnederlands',
    loginHeader: 'Log in',
    btnManual: 'login\nmanually',
    btnQr: 'login\nQR code',
    manualHeader: 'Manual login',
    btnPin: 'login with\npincode',
    btnDate: 'login with\ndate of birth',
    pinHeader: 'Enter pincode',
    pinLabel: 'Enter your pincode',
    dateHeader: 'Enter date of birth',
    dateLabel: 'Enter your date of birth',
    qrHeader: 'QR code scan',
    qrMsg: 'Place your QR code in front of the scanner',
    dispHeader: 'Incoming medicine',
    dispMsg: 'Wait until the door opens',
    dispTimerLabel: 'seconds',
    endHeader: 'Thank you for visiting',
    endMsg: 'Did you take all your medicine from the compartment?',
    finishBtn: 'Click here to finish',
    btnPrint: 'Print leaflet',
    timeoutMessage: 'Process will be stopped due to inactivity.',
    timeoutSubtitle: 'Click anywhere to cancel',
    ordersHeader: 'Your open orders',
    ordersError: 'No open orders found.',
    compartmentNotAssigned: 'Compartment not assigned yet. Please contact the pharmacy.'
  }
};

function applyLang() {
  const t = T[lang];
  document.getElementById('w-title').textContent = t.wTitle;
  document.getElementById('w-sub').textContent = t.wSub;
  document.getElementById('w-proceed').textContent = t.wProceed;
  document.getElementById('lang-label').innerHTML = t.flagLabel.replace('\n','<br>');
  document.getElementById('login-header').textContent = t.loginHeader;
  document.getElementById('btn-manual').innerHTML = t.btnManual.replace(/\n/g,'<br>');
  document.getElementById('btn-qr').innerHTML = t.btnQr.replace(/\n/g,'<br>');
  document.getElementById('manual-header').textContent = t.manualHeader;
  document.getElementById('btn-pin').innerHTML = t.btnPin.replace(/\n/g,'<br>');
  document.getElementById('btn-date').innerHTML = t.btnDate.replace(/\n/g,'<br>');
  document.getElementById('pin-header').textContent = t.pinHeader;
  document.getElementById('pin-label').textContent = t.pinLabel;
  document.getElementById('date-header').textContent = t.dateHeader;
  document.getElementById('date-label').textContent = t.dateLabel;
  document.getElementById('qr-header').textContent = t.qrHeader;
  document.getElementById('qr-msg').textContent = t.qrMsg;
  document.getElementById('disp-header').textContent = t.dispHeader;
  document.getElementById('disp-msg').textContent = t.dispMsg;

  // timer label
  const timerLabel = document.getElementById('disp-timer-label');
  if (timerLabel) timerLabel.textContent = t.dispTimerLabel;

  // update flag
  const fd = document.getElementById('flag-display');
  if (lang === 'nl') {
    fd.src = 'https://img.icons8.com/emoji/48/netherlands-emoji.png';
  } else {
    fd.src = 'https://img.icons8.com/emoji/48/united-kingdom-emoji.png';
  }

  // end page texts (language dependent)
  const endHeader = document.getElementById('end-header');
  const endMsg = document.getElementById('end-msg');
  const btnFinish = document.getElementById('btn-finish');
  const btnPrint = document.getElementById('btn-print');
  if (endHeader) {
    endHeader.textContent = t.endHeader;
  }
  if (endMsg) {
    endMsg.textContent = t.endMsg;
  }
  if (btnFinish) {
    btnFinish.textContent = t.finishBtn;
  }
  if (btnPrint) {
    btnPrint.textContent = t.btnPrint;
  }

  // timeout modal texts
  const timeoutMsgEl = document.getElementById('timeout-message');
  const timeoutSubEl = document.getElementById('timeout-subtitle');
  if (timeoutMsgEl) timeoutMsgEl.textContent = t.timeoutMessage;
  if (timeoutSubEl) timeoutSubEl.textContent = t.timeoutSubtitle;

  // orders page texts
  const ordersHeaderEl = document.getElementById('orders-header');
  if (ordersHeaderEl) ordersHeaderEl.textContent = t.ordersHeader;
}

function toggleLang() {
  lang = lang === 'nl' ? 'en' : 'nl';
  applyLang();
}

// navigation
let autoAdvanceTimer = null;
let navHistory = ['page-welcome']; // track navigation history for back button

function goTo(id) {
  if (autoAdvanceTimer) { clearTimeout(autoAdvanceTimer); autoAdvanceTimer = null; }
  if (dispensingInterval) { clearInterval(dispensingInterval); dispensingInterval = null; }

  hideTimeoutModal();
  stopQrPolling();

  // push to history (avoid duplicates for same page)
  if (navHistory[navHistory.length - 1] !== id) {
    navHistory.push(id);
  }

  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');

  if (id === 'page-end') {
    // hide back/stop buttons on end page (no bottom-btns on that page)
  }

  // hide back button on welcome page
  if (id !== 'page-end') {
    const backBtns = document.querySelectorAll('.back-btn');
    backBtns.forEach(btn => {
      btn.style.visibility = id === 'page-welcome' ? 'hidden' : 'visible';
    });
  }

  if (id === 'page-dispensing') {
    startDispensingTimer();
  }

  if (id === 'page-qr') {
    startQrPolling();
  }

  // start end page timeout
  if (id === 'page-end') {
    console.log('[timeout] navigating to page-end, starting end page timeout');
    startEndPageTimeout();
  }

  resetInactivityTimer();
}

function goBack() {
  // go back one step in navigation history
  if (navHistory.length > 1) {
    navHistory.pop(); // remove current page
    const prev = navHistory[navHistory.length - 1];
    // close door / stop carousel before going back
    closeDoorThenGoBack(prev);
  } else {
    // already at welcome
    goTo('page-welcome');
  }
}

async function closeDoorThenGoBack(targetPage) {
  // close door and stop carousel (if rotating)
  try {
    await fetch('/api/door/close', { method: 'POST' });
  } catch (e) {
    console.error('[back] error closing door:', e);
  }

  // navigate without re-pushing to history
  navigateTo(targetPage, false);
}

function navigateTo(id, pushHistory) {
  if (typeof pushHistory === 'undefined') pushHistory = true;
  if (autoAdvanceTimer) { clearTimeout(autoAdvanceTimer); autoAdvanceTimer = null; }
  if (dispensingInterval) { clearInterval(dispensingInterval); dispensingInterval = null; }

  hideTimeoutModal();
  stopQrPolling();

  if (pushHistory && navHistory[navHistory.length - 1] !== id) {
    navHistory.push(id);
  }

  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');

  if (id === 'page-dispensing') {
    startDispensingTimer();
  }

  if (id === 'page-qr') {
    startQrPolling();
  }

  resetInactivityTimer();
}

function startQrPolling() {
  if (qrPollInterval) {
    return;
  }
  const statusEl = document.getElementById('scan-code');
  if (statusEl) {
    statusEl.textContent = '';
  }
  checkQrScan();
  qrPollInterval = setInterval(checkQrScan, 1000);
}

function stopQrPolling() {
  if (qrPollInterval) {
    clearInterval(qrPollInterval);
    qrPollInterval = null;
  }
}

async function checkQrScan() {
  try {
    const res = await fetch('/api/qr/scan');
    const data = await res.json();
    if (res.ok && data.qr_code) {
      const code = data.qr_code;
      const statusEl = document.getElementById('scan-code');
      if (statusEl) {
        statusEl.textContent = 'Scan: ' + code;
      }
      loginUserByPin(code);
      stopQrPolling();
    }
  } catch (e) {
    // ignore polling errors; the page will keep checking
  }
}

// pin logic
function pinRender() {
  const d = document.getElementById('pin-display');
  d.innerHTML = '';
  for (let i = 0; i < 6; i++) {
    const dot = document.createElement('div');
    dot.className = 'pin-dot' + (i < pinValue.length ? ' filled' : '');
    d.appendChild(dot);
  }
}

function pinKey(k) {
  if (pinValue.length < 6) {
    pinValue += k;
    pinRender();
  }
}

function pinDel() {
  pinValue = pinValue.slice(0, -1);
  pinRender();
}

function pinConfirm() {
  if (pinValue.length > 0) {
    loginUserByPin(pinValue);
    pinReset();
  }
}

function pinReset() {
  pinValue = '';
  pinRender();
}

pinRender();

// date logic
function dateFields() {
  const dd = dateBuffer.slice(0, 2).padEnd(2, '_');
  const mm = dateBuffer.slice(2, 4).padEnd(2, '_');
  const yyyy = dateBuffer.slice(4, 8).padEnd(4, '_');
  document.getElementById('date-dd').value = dd === '__' ? '' : dd.replace(/_/g, '');
  document.getElementById('date-mm').value = mm === '__' ? '' : mm.replace(/_/g, '');
  document.getElementById('date-yyyy').value = yyyy === '____' ? '' : yyyy.replace(/_/g, '');
  document.getElementById('date-dd').placeholder = 'DD';
  document.getElementById('date-mm').placeholder = 'MM';
  document.getElementById('date-yyyy').placeholder = 'YYYY';
}

function dateKey(k) {
  if (dateBuffer.length < 8) {
    dateBuffer += k;
    dateFields();
  }
}

function dateDel() {
  dateBuffer = dateBuffer.slice(0, -1);
  dateFields();
}

function dateConfirm() {
  if (dateBuffer.length === 8) {
    const dd = dateBuffer.slice(0, 2);
    const mm = dateBuffer.slice(2, 4);
    const yyyy = dateBuffer.slice(4, 8);
    const birthdateStr = yyyy + '-' + mm + '-' + dd;
    loginUserByBirthdate(birthdateStr);
    dateReset();
  }
}

function dateReset() {
  dateBuffer = '';
  dateFields();
}

// dispensing timer
function startDispensingTimer(totalSeconds) {
  // clear any existing interval before creating a new one
  if (dispensingInterval) { clearInterval(dispensingInterval); dispensingInterval = null; }

  dispensingTotal = totalSeconds || DISPENSING_DURATION_DEFAULT;
  dispensingTimeLeft = dispensingTotal;
  updateTimerDisplay();

  dispensingInterval = setInterval(() => {
    dispensingTimeLeft--;
    updateTimerDisplay();

    if (dispensingTimeLeft <= 0) {
      clearInterval(dispensingInterval);
      dispensingInterval = null;
      goTo('page-end');
    }
  }, 1000);
}

function updateTimerDisplay() {
  const timerText = document.getElementById('disp-timer');
  const timerProgress = document.querySelector('.timer-progress');

  if (timerText) {
    timerText.textContent = dispensingTimeLeft;
  }

  if (timerProgress) {
    const progress = 1 - (dispensingTimeLeft / dispensingTotal);
    const offset = TIMER_CIRCUMFERENCE * (1 - progress);
    timerProgress.style.strokeDasharray = TIMER_CIRCUMFERENCE;
    timerProgress.style.strokeDashoffset = offset;
  }
}

// stop process — close door, let carousel finish, reload to welcome
async function stopProcess() {
  // clear all timers
  if (autoAdvanceTimer) { clearTimeout(autoAdvanceTimer); autoAdvanceTimer = null; }
  if (dispensingInterval) { clearInterval(dispensingInterval); dispensingInterval = null; }
  hideTimeoutModal();
  stopQrPolling();

  // reset state
  pinReset();
  dateReset();

  // close the servo door (carousel keeps running in background)
  try {
    await fetch('/api/door/close', { method: 'POST' });
  } catch (e) {
    console.error('[stop] error closing door:', e);
  }

  // reload page to return to welcome
  window.location.reload();
}

// stop process due to inactivity timeout — marks order as failed and hard-reloads
async function stopProcessByTimeout() {
  // clear all timers
  if (autoAdvanceTimer) { clearTimeout(autoAdvanceTimer); autoAdvanceTimer = null; }
  if (dispensingInterval) { clearInterval(dispensingInterval); dispensingInterval = null; }
  hideTimeoutModal();

  // only mark as failed if the order hasn't already been printed (which completes it)
  if (currentPickupOrderId && !receiptPrinted) {
    try {
      await fetch('/api/user/failed_pickup/' + currentPickupOrderId, { method: 'POST' });
    } catch (e) {
      console.error('[timeout] error marking order failed:', e);
    }
  }

  // hard reload the page (resets everything including receipt button)
  window.location.reload();
}

// finish session (from end page)
async function finishSession() {
  resetInactivityTimer();
  console.log('[finish] completing order:', currentPickupOrderId);

  // Try to complete the order first
  if (currentPickupOrderId) {
    try {
      const res = await fetch('/api/user/complete/' + currentPickupOrderId, { method: 'POST' });
      const data = await res.json();
      console.log('[finish] status:', res.status, JSON.stringify(data));
    } catch (e) {
      console.error('[finish] error completing order:', e);
    }
  }

  // Reload page to reset everything
  window.location.reload();
}

// print leaflet
async function printLeaflet() {
  resetInactivityTimer();

  // disable after first click
  const btn = document.getElementById('btn-print');
  if (btn.disabled) return;
  btn.disabled = true;
  btn.textContent = btn.textContent + '...';

  try {
    const res = await fetch('/api/print/receipt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order_id: currentPickupOrderId })
    });

    const text = await res.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { error: text || 'Afdrukken mislukt' };
    }

    if (!res.ok) {
      showError(data.details || data.error || 'Afdrukken mislukt');
      btn.textContent = 'Opnieuw proberen';
      btn.disabled = false;
    } else {
      // receipt printed — backend already marked order as completed
      receiptPrinted = true;
      btn.textContent = '✓ Afgedrukt';
    }
  } catch (e) {
    showError('Verbindingsfout, probeer opnieuw.');
    btn.textContent = 'Opnieuw proberen';
    btn.disabled = false;
  }
}

// inactivity timeout
function resetInactivityTimer() {
  if (inactivityTimer) {
    clearTimeout(inactivityTimer);
  }

  // hide timeout modal if visible
  hideTimeoutModal();

  // check if we're on a page that shouldn't timeout
  const activePage = document.querySelector('.page.active');
  if (activePage && (activePage.id === 'page-admin' || activePage.id === 'page-welcome')) {
    return;
  }

  // end page uses its own one-shot timer, but activity should restart it
  // just like the normal inactivity timer restarts on activity elsewhere
  if (activePage && activePage.id === 'page-end') {
    startEndPageTimeout();
    return;
  }

  // start inactivity timer
  inactivityTimer = setTimeout(showTimeoutModal, INACTIVITY_LIMIT);
}

function showTimeoutModal() {
  const modal = document.getElementById('timeout-modal');
  if (!modal) return;

  modal.classList.add('show');
  timeoutCountdownValue = TIMEOUT_COUNTDOWN;
  updateTimeoutDisplay();

  // start countdown
  timeoutModalTimer = setInterval(() => {
    timeoutCountdownValue--;
    updateTimeoutDisplay();

    if (timeoutCountdownValue <= 0) {
      hideTimeoutModal();
      stopProcessByTimeout();
    }
  }, 1000);
}

function hideTimeoutModal() {
  const modal = document.getElementById('timeout-modal');
  if (modal) {
    modal.classList.remove('show');
  }
  if (timeoutModalTimer) {
    clearInterval(timeoutModalTimer);
    timeoutModalTimer = null;
  }
}

function dismissTimeout() {
  if (timeoutCountdownValue > 0) {
    hideTimeoutModal();
    resetInactivityTimer();
  }
}

function updateTimeoutDisplay() {
  const countdownEl = document.getElementById('timeout-countdown');
  if (countdownEl) {
    countdownEl.textContent = timeoutCountdownValue;
  }
}

// global activity listener
document.addEventListener('click', resetInactivityTimer);
document.addEventListener('touchstart', resetInactivityTimer);

// init
applyLang();
resetInactivityTimer();

// ── User Login ──
async function loginUserByPin(pin) {
  try {
    const res = await fetch('/api/user/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pincode: pin })
    });
    const data = await res.json();
    if (res.ok) {
      userOrders = data;
      renderUserOrders(userOrders);
      goTo('page-orders');
    } else {
      showError(data.error || 'Inloggen mislukt');
    }
  } catch (e) {
    showError('Verbindingsfout, probeer opnieuw.');
  }
}

async function loginUserByBirthdate(date) {
  try {
    const res = await fetch('/api/user/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ birthdate: date })
    });
    const data = await res.json();
    if (res.ok) {
      userOrders = data;
      renderUserOrders(userOrders);
      goTo('page-orders');
    } else {
      showError(data.error || 'Inloggen mislukt');
    }
  } catch (e) {
    showError('Verbindingsfout, probeer opnieuw.');
  }
}

function showError(msg) {
  const banner = document.getElementById('frontend-error');
  if (banner) {
    banner.textContent = msg;
    banner.classList.add('show');
    clearTimeout(banner._hideTimer);
    banner._hideTimer = setTimeout(() => banner.classList.remove('show'), 4000);
  }
}

function showOrderNotReady() {
  showError(T[lang].compartmentNotAssigned);
}

// ── Render User Orders ──
function renderUserOrders(orders) {
  const container = document.getElementById('orders-list');
  const errorEl = document.getElementById('orders-error');
  errorEl.style.display = 'none';

  if (!orders || !orders.length) {
    container.innerHTML = '';
    errorEl.textContent = T[lang].ordersError;
    errorEl.style.display = 'block';
    return;
  }

  let html = '';
  orders.forEach(function(order) {
    const compartment = order.compartment_number != null ? 'Vak ' + order.compartment_number : '—';
    const status = order.status ? order.status.charAt(0).toUpperCase() + order.status.slice(1) : '—';
    const statusClass = order.status ? 'status-badge ' + order.status.toLowerCase() : '';
    const isReady = order.status === 'ready';
    const hasCompartment = order.compartment_number != null;
    const canPickUp = isReady && hasCompartment;
    const clickAction = canPickUp ? 'pickUpOrder(' + order.id + ')' : 'showOrderNotReady()';

    html += '<div class="user-order-card' + (canPickUp ? '' : ' locked') + '" onclick="' + clickAction + '">';
    html += '<div class="order-info">';
    html += '<div class="order-product">' + escapeXml(order.product_name || '—') + '</div>';
    html += '<div class="order-meta">';
    html += '<span class="' + statusClass + '">' + status + '</span>';
    html += '<span>' + compartment + '</span>';
    html += '</div></div>';
    html += '<div class="order-amount">' + order.amount + 'x</div>';
    html += '<div class="order-arrow">' + (isReady && hasCompartment ? '›' : '🔒') + '</div>';
    html += '</div>';
  });
  container.innerHTML = html;
}

// pick up order
async function pickUpOrder(orderId) {
  // Go to dispensing page IMMEDIATELY with default timer, then update when backend responds
  goTo('page-dispensing');

  try {
    const res = await fetch('/api/user/pickup/' + orderId, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      currentPickupOrderId = orderId;
      // restart timer with actual wait time from backend
      if (data.wait_seconds) {
        startDispensingTimer(data.wait_seconds);
      }
      console.log('[pickup] order', orderId, 'accepted — carousel spinning, door will open');
    } else {
      // Backend rejected (e.g. compartment not assigned) — go back to orders
      showError(data.error || 'Kon order niet ophalen');
      goTo('page-orders');
    }
  } catch (e) {
    showError('Verbindingsfout, probeer opnieuw.');
    goTo('page-orders');
  }
}

function escapeXml(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}