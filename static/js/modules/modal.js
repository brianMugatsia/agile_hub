export function initModals() {
  document.addEventListener("click", (event) => {
    const openButton = event.target.closest("[data-modal-open]");
    if (openButton) {
      const dialog = document.getElementById(openButton.dataset.modalOpen);
      if (dialog instanceof HTMLDialogElement && !dialog.open) dialog.showModal();
      return;
    }

    const closeButton = event.target.closest("[data-modal-close]");
    if (closeButton) {
      const dialog = closeButton.closest("dialog");
      if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close();
    }
  });

  document.querySelectorAll("dialog[data-modal]").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
}