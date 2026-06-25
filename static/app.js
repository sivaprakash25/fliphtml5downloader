const urlInput = document.getElementById("book-url");
const startBtn = document.getElementById("start-btn");
const btnLabel = startBtn.querySelector(".btn-label");
const btnSpinner = startBtn.querySelector(".btn-spinner");
const progressPanel = document.getElementById("progress-panel");
const phaseLabel = document.getElementById("phase-label");
const bookTitle = document.getElementById("book-title");
const statusText = document.getElementById("status-text");
const percentText = document.getElementById("percent-text");
const barFill = document.getElementById("bar-fill");
const ringProgress = document.getElementById("ring-progress");
const steps = document.getElementById("steps");
const downloadLink = document.getElementById("download-link");
const resetBtn = document.getElementById("reset-btn");
const errorBox = document.getElementById("error-box");

const RING_CIRCUMFERENCE = 327;
const PHASE_ORDER = ["fetching", "decoding", "downloading", "building", "done"];
const PHASE_LABELS = {
  queued: "Queued",
  fetching: "Fetching",
  decoding: "Decoding",
  downloading: "Downloading",
  building: "Building PDF",
  done: "Complete",
  error: "Failed",
};

let activeSource = null;
let autoDownloadedJobId = null;

function triggerPdfDownload(jobId) {
  const link = document.createElement("a");
  link.href = `/api/jobs/${jobId}/file`;
  link.download = "";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function setBusy(busy) {
  startBtn.disabled = busy;
  btnSpinner.hidden = !busy;
  btnLabel.textContent = busy ? "Working..." : "Download PDF";
  urlInput.disabled = busy;
}

function updateRing(percent) {
  const offset = RING_CIRCUMFERENCE - (RING_CIRCUMFERENCE * percent) / 100;
  ringProgress.style.strokeDashoffset = String(offset);
  percentText.textContent = `${percent}%`;
  barFill.style.width = `${percent}%`;
  const progressBar = document.getElementById("progress-bar");
  if (progressBar) {
    progressBar.setAttribute("aria-valuenow", String(percent));
  }
}

function updateSteps(phase) {
  const currentIndex = PHASE_ORDER.indexOf(phase);
  steps.querySelectorAll("li").forEach((item) => {
    const itemPhase = item.dataset.phase;
    const itemIndex = PHASE_ORDER.indexOf(itemPhase);
    item.classList.remove("active", "done");
    if (phase === "error") {
      return;
    }
    if (itemIndex < currentIndex) {
      item.classList.add("done");
    } else if (itemIndex === currentIndex) {
      item.classList.add("active");
    }
  });
}

function applyState(data) {
  const phase = data.phase || "queued";
  phaseLabel.textContent = PHASE_LABELS[phase] || phase;
  bookTitle.textContent = data.title || "FlipHTML5 Book";
  statusText.textContent = data.message || "";
  updateRing(data.percent || 0);
  updateSteps(phase);

  if (phase === "error") {
    errorBox.hidden = false;
    errorBox.textContent = data.error || data.message || "Something went wrong.";
    downloadLink.hidden = true;
    resetBtn.hidden = false;
    setBusy(false);
    return;
  }

  errorBox.hidden = true;

  if (data.done && data.has_pdf) {
    downloadLink.href = `/api/jobs/${data.job_id}/file`;
    downloadLink.hidden = false;
    resetBtn.hidden = false;
    setBusy(false);
    updateRing(100);
    updateSteps("done");

    if (autoDownloadedJobId !== data.job_id) {
      autoDownloadedJobId = data.job_id;
      triggerPdfDownload(data.job_id);
      statusText.textContent = "Downloading PDF — file will be removed from the server after.";
    }
    return;
  }

  if (data.done && data.downloaded) {
    downloadLink.hidden = true;
    resetBtn.hidden = false;
    setBusy(false);
    updateRing(100);
    updateSteps("done");
    statusText.textContent = "PDF saved. Server copy removed.";
  }
}

async function startDownload() {
  const url = urlInput.value.trim();
  if (!url) {
    urlInput.focus();
    return;
  }

  if (activeSource) {
    activeSource.close();
    activeSource = null;
  }

  autoDownloadedJobId = null;
  progressPanel.hidden = false;
  downloadLink.hidden = true;
  resetBtn.hidden = true;
  errorBox.hidden = true;
  updateRing(0);
  updateSteps("fetching");
  bookTitle.textContent = "—";
  statusText.textContent = "Creating job...";
  setBusy(true);

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not start download");
    }

    const { job_id: jobId } = await response.json();
    activeSource = new EventSource(`/api/jobs/${jobId}/events`);

    activeSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      applyState(data);
      if (data.done) {
        activeSource.close();
        activeSource = null;
      }
    };

    activeSource.onerror = () => {
      if (activeSource) {
        activeSource.close();
        activeSource = null;
      }
      errorBox.hidden = false;
      errorBox.textContent = "Lost connection to the server.";
      resetBtn.hidden = false;
      setBusy(false);
    };
  } catch (error) {
    errorBox.hidden = false;
    errorBox.textContent = error.message || "Failed to start download.";
    resetBtn.hidden = false;
    setBusy(false);
  }
}

function resetUi() {
  if (activeSource) {
    activeSource.close();
    activeSource = null;
  }
  autoDownloadedJobId = null;
  progressPanel.hidden = true;
  downloadLink.hidden = true;
  resetBtn.hidden = true;
  errorBox.hidden = true;
  setBusy(false);
  urlInput.focus();
}

startBtn.addEventListener("click", startDownload);
resetBtn.addEventListener("click", resetUi);

urlInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    startDownload();
  }
});
