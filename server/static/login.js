(() => {
  'use strict';
  const button = document.getElementById('toggle-admin-password');
  const input = document.getElementById('admin-password');
  if (!button || !input) return;
  button.addEventListener('click', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(visible));
    button.textContent = visible ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور';
  });
})();
