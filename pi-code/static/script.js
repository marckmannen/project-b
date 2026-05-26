// ── STATE ──
let lang = 'nl';
let pinValue = '';
let dateBuffer = '';   // flat string DDMMYYYY

// ── TRANSLATIONS ──
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

  // Update flag
  const fd = document.getElementById('flag-display');
  if (lang === 'nl') {
    fd.src = 'https://img.icons8.com/emoji/48/netherlands-emoji.png';
  } else {
    fd.src = 'https://img.icons8.com/emoji/48/united-kingdom-emoji.png';
  }

  // End page texts (language dependent)
  const endHeader = document.getElementById('end-header');
  const endMsg = document.getElementById('end-msg');
  const endFarewell = document.getElementById('end-farewell');
  if (endHeader) {
    endHeader.textContent = (lang === 'nl') ? 'Bedankt voor uw komst' : 'Thank you for visiting';
  }
  if (endMsg) {
    endMsg.textContent = (lang === 'nl') ? 'Zorg dat u al uw medicijnen uit het vak heeft gehaald!' : 'Make sure to take all your medicine from the compartment!';
  }
  if (endFarewell) {
    endFarewell.textContent = (lang === 'nl') ? 'Tot ziens!' : 'Goodbye!';
  }
}

function toggleLang() {
  lang = lang === 'nl' ? 'en' : 'nl';
  applyLang();
}

// ── NAVIGATION ──
let autoAdvanceTimer = null;

function goTo(id) {
  if (autoAdvanceTimer) { clearTimeout(autoAdvanceTimer); autoAdvanceTimer = null; }
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if (id === 'page-dispensing') {
    autoAdvanceTimer = setTimeout(() => { goTo('page-end'); }, 10000);
  }
}

// ── PIN LOGIC ──
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
    goTo('page-dispensing');
    pinReset();
  }
}

function pinReset() {
  pinValue = '';
  pinRender();
}

pinRender();

// ── DATE LOGIC ──
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
    goTo('page-dispensing');
    dateReset();
  }
}

function dateReset() {
  dateBuffer = '';
  dateFields();
}

// Simulate QR scan after 3 seconds on QR page
document.getElementById('page-qr').addEventListener('click', function() {
  goTo('page-dispensing');
});

applyLang();
