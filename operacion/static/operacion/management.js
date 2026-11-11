document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.field-hint').forEach(button => {
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape') button.classList.add('hint-dismissed');
    });
    ['mouseenter', 'focus'].forEach(name => button.addEventListener(name, () => {
      button.classList.remove('hint-dismissed');
    }));
  });
});
