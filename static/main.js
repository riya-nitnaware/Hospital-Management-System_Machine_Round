
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menuToggle");
  const nav = document.getElementById("navLinks");

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  // Client-side date validation is a convenience only.
  document.querySelectorAll('input[type="datetime-local"]').forEach(input => {
    const now = new Date();
    input.min = new Date(
      now.getTime() - now.getTimezoneOffset() * 60000
    ).toISOString().slice(0, 16);
  });

  // Prevent accidental duplicate normal form submissions.
  document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", event => {
      if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
        return;
      }

      const button = event.submitter;
      if (button && !button.disabled) {
        button.disabled = true;
        button.textContent = "Please wait...";
      }
    });
  });
});
