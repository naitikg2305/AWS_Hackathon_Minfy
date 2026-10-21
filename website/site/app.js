const toggle = document.querySelector('.menu-toggle');
const nav = document.getElementById('navigation');
toggle.addEventListener('click', () => {
  const open = toggle.getAttribute('aria-expanded') !== 'true';
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  nav.classList.toggle('is-open', open);
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('is-open'); toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-label', 'Open navigation');
}));
document.addEventListener('keydown', e => {if(e.key === 'Escape' && nav.classList.contains('is-open')){toggle.click();toggle.focus();}});

const video = document.getElementById('demo-video');
const cover = document.getElementById('play-demo');
cover.addEventListener('click', async () => {
  cover.hidden = true;
  try { await video.play(); video.focus(); } catch { cover.hidden = false; }
});
video.addEventListener('play', () => { cover.hidden = true; });
video.addEventListener('loadedmetadata', () => {
  if (Number.isFinite(video.duration)) {
    const seconds = Math.round(video.duration);
    document.querySelectorAll('.duration').forEach(el => el.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`);
  }
});
video.addEventListener('error', () => {
  cover.hidden = true;
  const message = document.createElement('p'); message.className = 'video-error';
  message.textContent = 'The video could not load. Please reload the page and try again.';
  message.style.cssText = 'padding:20px;color:white;background:#19283c;position:absolute;inset:auto 0 0';
  document.querySelector('.video-stage').append(message);
});

const tabs = [...document.querySelectorAll('[role="tab"]')];
function activateTab(tab, focus = false) {
  tabs.forEach(t => {const active = t === tab; t.setAttribute('aria-selected', String(active));t.tabIndex = active ? 0 : -1;document.getElementById(t.getAttribute('aria-controls')).hidden = !active;});
  if (focus) tab.focus();
}
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => activateTab(tab));
  tab.addEventListener('keydown', e => {
    if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){
      e.preventDefault(); const n = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length-1 : (i+(e.key === 'ArrowRight'?1:-1)+tabs.length)%tabs.length;
      activateTab(tabs[n], true);
    }
  });
});

