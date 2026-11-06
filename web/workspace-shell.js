'use strict';
// Presentation only. Authentication and permissions remain on the shared backend.
window.WorkspaceUI = (() => {
  let setAuthenticated = () => {};
  function director(getLanguage) {
    const sidebar = document.getElementById('sidebar');
    const main = document.getElementById('director-main');
    const toggle = document.getElementById('menu-toggle');
    const close = document.getElementById('menu-close');
    const backdrop = document.getElementById('nav-backdrop');
    const mobile = window.matchMedia('(max-width: 900px)');
    let opened = false, authenticated = false;
    function update() {
      const modal = mobile.matches && opened && authenticated;
      document.body.classList.toggle('menu-open', modal);
      main.inert = modal;
      sidebar.inert = mobile.matches && !modal;
      backdrop.hidden = !modal;
      toggle.setAttribute('aria-expanded', String(modal));
      if (modal) {
        sidebar.setAttribute('role', 'dialog');
        sidebar.setAttribute('aria-modal', 'true');
      } else {
        sidebar.removeAttribute('role');
        sidebar.removeAttribute('aria-modal');
      }
    }
    function dismiss(restoreFocus = true) {
      opened = false;
      update();
      if (restoreFocus && mobile.matches && authenticated) toggle.focus();
    }
    toggle.onclick = () => {
      if (!authenticated || !mobile.matches) return;
      opened = true;
      update();
      close.focus();
    };
    close.onclick = () => dismiss();
    backdrop.onclick = () => dismiss();
    document.getElementById('nav').addEventListener('click', event => {
      if (opened && event.target.closest('[data-section]')) dismiss();
    });
    document.addEventListener('keydown', event => {
      if (!opened || !mobile.matches) return;
      if (event.key === 'Escape') { event.preventDefault(); dismiss(); }
      if (event.key !== 'Tab') return;
      const focusable = [...sidebar.querySelectorAll('a[href],button:not([disabled])')]
        .filter(el => !el.hidden && el.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    mobile.addEventListener('change', () => {
      const focusWasInside = sidebar.contains(document.activeElement);
      dismiss(false);
      if (mobile.matches && focusWasInside && authenticated) toggle.focus();
    });
    setAuthenticated = value => {
      authenticated = value;
      document.body.classList.toggle('signed-out', !value);
      document.documentElement.lang = getLanguage();
      const ru = getLanguage() === 'ru';
      toggle.setAttribute('aria-label', ru ? 'Открыть разделы' : 'Bo‘limlarni ochish');
      close.setAttribute('aria-label', ru ? 'Закрыть разделы' : 'Bo‘limlarni yopish');
      sidebar.setAttribute('aria-label', ru ? 'Разделы кабинета' : 'Kabinet bo‘limlari');
      if (!value) dismiss(false);
      update();
    };
    setAuthenticated(false);
  }
  return { director, authenticated: value => setAuthenticated(value) };
})();
