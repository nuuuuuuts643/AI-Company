// ===== テーマ管理 (ダーク / ライト / システム) =====
// 依存なし。<script src="js/theme.js"> を <head> の直後に置くと FOUC を防げる。

const THEME_KEY = 'flotopic_theme';
const THEMES = ['system', 'light', 'dark'];
const ICONS  = { system: '🌓', light: '☀️', dark: '🌙' };

function applyTheme(theme) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark);
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
}

function getTheme() {
  return localStorage.getItem(THEME_KEY) || 'system';
}

function cycleTheme() {
  const cur = getTheme();
  const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) btn.textContent = ICONS[next];
}

function initTheme() {
  const theme = getTheme();
  applyTheme(theme);
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    btn.textContent = ICONS[theme];
    btn.addEventListener('click', cycleTheme);
  }
  // システムテーマが変わったら追随
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getTheme() === 'system') applyTheme('system');
  });
}

// 即時適用（FOUC防止）
applyTheme(getTheme());
document.addEventListener('DOMContentLoaded', initTheme);
