(() => {
  const tools = document.querySelector(".barcode-tools");
  const serialInput = document.getElementById("id_serial_ref");
  if (!tools || !serialInput) return;

  const resultArea = document.getElementById("barcode-lookup-results");
  const status = document.getElementById("barcode-scan-status");
  const video = document.getElementById("barcode-video");
  const startButton = document.getElementById("start-barcode-scan");
  const stopButton = document.getElementById("stop-barcode-scan");
  let stream;
  let scanTimer;
  let lookupTimer;

  function stopCamera() {
    window.clearTimeout(scanTimer);
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = undefined;
    }
    video.srcObject = null;
    video.hidden = true;
    stopButton.hidden = true;
    startButton.hidden = false;
  }

  function showMatches(matches) {
    resultArea.replaceChildren();
    if (matches.length === 0) {
      resultArea.textContent = "No matching asset found. Review the value before registering.";
      return;
    }
    const heading = document.createElement("p");
    heading.className = "error-message";
    heading.textContent = `Barcode matches ${matches.length} existing asset(s):`;
    const list = document.createElement("ul");
    for (const match of matches) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = match.url;
      link.textContent = `${match.asset_id} · ${match.site} · ${match.status}`;
      item.append(link);
      list.append(item);
    }
    resultArea.append(heading, list);
  }

  async function lookupBarcode(code) {
    if (!code) {
      resultArea.replaceChildren();
      return;
    }
    try {
      const url = new URL(tools.dataset.lookupUrl, window.location.href);
      url.searchParams.set("code", code);
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Lookup failed (${response.status}).`);
      const payload = await response.json();
      showMatches(payload.matches);
    } catch (error) {
      resultArea.textContent = error.message;
    }
  }

  serialInput.addEventListener("input", () => {
    window.clearTimeout(lookupTimer);
    lookupTimer = window.setTimeout(() => lookupBarcode(serialInput.value.trim()), 250);
  });

  stopButton.addEventListener("click", stopCamera);
  startButton.addEventListener("click", async () => {
    if (!("BarcodeDetector" in window)) {
      status.textContent = "Camera scanning is not supported in this browser. Use a USB scanner or type the barcode.";
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      status.textContent = "Camera access is unavailable. Use a USB scanner or type the barcode.";
      return;
    }
    try {
      const detector = new window.BarcodeDetector({
        formats: ["qr_code", "code_128", "code_39", "ean_13", "ean_8", "upc_a", "upc_e"],
      });
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
      });
      video.srcObject = stream;
      video.hidden = false;
      await video.play();
      startButton.hidden = true;
      stopButton.hidden = false;
      status.textContent = "Point the camera at an asset barcode.";

      const scan = async () => {
        if (!stream) return;
        try {
          const [result] = await detector.detect(video);
          if (result?.rawValue) {
            serialInput.value = result.rawValue;
            serialInput.dispatchEvent(new Event("input", { bubbles: true }));
            status.textContent = "Barcode captured. Check for existing matches before saving.";
            stopCamera();
            return;
          }
        } catch (error) {
          status.textContent = `Barcode scan failed: ${error.message}`;
          stopCamera();
          return;
        }
        scanTimer = window.setTimeout(scan, 300);
      };
      scan();
    } catch (error) {
      status.textContent = `Could not start camera: ${error.message}`;
      stopCamera();
    }
  });
})();
