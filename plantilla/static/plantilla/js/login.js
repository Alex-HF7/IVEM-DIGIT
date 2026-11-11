document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    const password = document.getElementById('id_password');
    const toggle = document.getElementById('password-toggle');
    const caps = document.getElementById('caps-lock-help');
    const submit = document.getElementById('login-submit');
    if (!form || !password || !toggle || !submit) return;
    toggle.addEventListener('click', () => {
        const visible = password.type === 'password';
        password.type = visible ? 'text' : 'password';
        toggle.setAttribute('aria-pressed', String(visible));
        toggle.setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña');
        toggle.querySelector('i').className = visible ? 'bi bi-eye-slash' : 'bi bi-eye';
    });
    password.addEventListener('keyup', event => {
        caps.classList.toggle('d-none', !event.getModifierState('CapsLock'));
    });
    password.addEventListener('blur', () => caps.classList.add('d-none'));
    const original = submit.innerHTML;
    form.addEventListener('submit', event => {
        if (form.dataset.submitting === 'true') { event.preventDefault(); return; }
        if (!form.checkValidity()) return;
        form.dataset.submitting = 'true';
        submit.disabled = true;
        submit.textContent = 'Ingresando…';
    });
    window.addEventListener('pageshow', (event = {}) => {
        password.type = 'password';
        toggle.setAttribute('aria-pressed', 'false');
        toggle.setAttribute('aria-label', 'Mostrar contraseña');
        toggle.querySelector('i').className = 'bi bi-eye';
        if (event.persisted) password.value = '';
        delete form.dataset.submitting;
        submit.disabled = false;
        submit.innerHTML = original;
    });
});
