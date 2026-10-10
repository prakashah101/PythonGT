(() => {
  const dialog = document.getElementById("safety-report-dialog");
  const reportForm = document.getElementById("safety-report-form");
  const reportStatus = document.getElementById("safety-report-status");
  const toast = document.getElementById("safety-toast");
  let toastTimer;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { toast.hidden = true; }, 4500);
  }

  function csrfForm() {
    const form = new FormData();
    form.append("csrf_token", document.body.dataset.safetyCsrf || "");
    return form;
  }

  async function postSafety(url, form) {
    const response = await fetch(url, { method: "POST", body: form, headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "Could not complete that safety action.");
    return result;
  }

  document.addEventListener("click", async event => {
    const closeButton = event.target.closest("[data-safety-close]");
    if (closeButton) {
      dialog?.close();
      return;
    }

    const reportButton = event.target.closest("[data-safety-report-user], [data-safety-report-message]");
    if (reportButton && dialog) {
      document.getElementById("safety-report-user-id").value = reportButton.dataset.safetyReportUser || "";
      document.getElementById("safety-report-message-id").value = reportButton.dataset.safetyReportMessage || "";
      reportStatus.textContent = "";
      reportForm.reset();
      document.getElementById("safety-report-user-id").value = reportButton.dataset.safetyReportUser || "";
      document.getElementById("safety-report-message-id").value = reportButton.dataset.safetyReportMessage || "";
      dialog.showModal();
      return;
    }

    const blockButton = event.target.closest("[data-safety-block-user]");
    const unblockButton = event.target.closest("[data-safety-unblock-user]");
    const accountButton = blockButton || unblockButton;
    if (!accountButton) return;
    const isUnblock = Boolean(unblockButton);
    const userId = accountButton.dataset.safetyUnblockUser || accountButton.dataset.safetyBlockUser;
    if (!isUnblock && !window.confirm("Block this user? They will no longer be able to message or follow you, and you will no longer see each other’s community content.")) return;
    accountButton.disabled = true;
    try {
      const result = await postSafety(`/api/safety/users/${userId}/${isUnblock ? "unblock" : "block"}`, csrfForm());
      if (isUnblock) {
        accountButton.closest(".blocked-user")?.remove();
        showToast("User unblocked. You can follow each other again.");
      } else if (accountButton.dataset.afterBlock === "redirect") {
        location.assign("/safety?blocked=1");
      } else {
        accountButton.closest(".community-post, .people-result")?.remove();
        showToast(result.message || "User blocked. Manage blocked accounts in the Safety Center.");
      }
    } catch (error) {
      showToast(error.message || "Could not update the block list.");
      accountButton.disabled = false;
    }
  });

  reportForm?.addEventListener("submit", async event => {
    event.preventDefault();
    const submit = reportForm.querySelector("button[type=submit]");
    submit.disabled = true;
    reportStatus.textContent = "Sending report…";
    const form = new FormData(reportForm);
    const reportedUserId = document.getElementById("safety-report-user-id").value;
    const messageId = document.getElementById("safety-report-message-id").value;
    form.delete("reported_user_id");
    form.delete("message_id");
    if (reportedUserId) form.append("reported_user_id", reportedUserId);
    if (messageId) form.append("message_id", messageId);
    form.append("csrf_token", document.body.dataset.safetyCsrf || "");
    try {
      const result = await postSafety("/api/safety/report", form);
      dialog.close();
      reportForm.reset();
      showToast(result.message || "Report sent. Thank you for helping keep Grapsy safe.");
    } catch (error) {
      reportStatus.textContent = error.message || "Could not send the report.";
    } finally {
      submit.disabled = false;
    }
  });
})();
