    const { invoke } = window.__TAURI__.core;
    const { listen } = window.__TAURI__.event;

    const canvas = document.getElementById("snipCanvas");
    const ctx = canvas.getContext("2d");
    const sizeBadge = document.getElementById("sizeBadge");
    const hintPill = document.getElementById("hintPill");

    let screenImg = new Image();
    let imgReady = false;
    let dragging = false;
    let startX = 0;
    let startY = 0;
    let curX = 0;
    let curY = 0;

    function resizeCanvas() {
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = window.innerHeight * window.devicePixelRatio;
      render();
    }

    window.addEventListener("resize", resizeCanvas);

    async function loadScreen() {
      imgReady = false;
      dragging = false;
      sizeBadge.style.display = "none";
      hintPill.style.display = "block";
      const b64 = await invoke("get_snip_screen");
      if (!b64) return;
      screenImg = new Image();
      screenImg.onload = () => {
        imgReady = true;
        resizeCanvas();
      };
      screenImg.src = `data:image/png;base64,${b64}`;
    }

    function render() {
      if (!imgReady) return;
      const cw = canvas.width;
      const ch = canvas.height;
      const dpr = window.devicePixelRatio || 1;

      ctx.clearRect(0, 0, cw, ch);
      ctx.drawImage(screenImg, 0, 0, cw, ch);

      // Làm tối màn hình nền
      ctx.fillStyle = "rgba(8, 10, 15, 0.52)";
      ctx.fillRect(0, 0, cw, ch);

      if (!dragging) return;

      const x = Math.min(startX, curX);
      const y = Math.min(startY, curY);
      const w = Math.abs(curX - startX);
      const h = Math.abs(curY - startY);

      if (w > 2 && h > 2) {
        const sx = (x / window.innerWidth) * screenImg.naturalWidth;
        const sy = (y / window.innerHeight) * screenImg.naturalHeight;
        const sw = (w / window.innerWidth) * screenImg.naturalWidth;
        const sh = (h / window.innerHeight) * screenImg.naturalHeight;

        const dx = x * dpr;
        const dy = y * dpr;
        const dw = w * dpr;
        const dh = h * dpr;

        // Vẽ vùng sáng được chọn
        ctx.drawImage(screenImg, sx, sy, sw, sh, dx, dy, dw, dh);

        // Viền khung chọn xanh dương
        ctx.strokeStyle = "#3b82f6";
        ctx.lineWidth = Math.max(2, 2 * dpr);
        ctx.strokeRect(dx, dy, dw, dh);

        // Hiển thị kích thước thật
        sizeBadge.style.display = "block";
        sizeBadge.textContent = `${Math.round(sw)} × ${Math.round(sh)}`;
        sizeBadge.style.left = `${Math.min(x, window.innerWidth - 90)}px`;
        sizeBadge.style.top = `${Math.max(8, y - 28)}px`;
      }
    }

    window.addEventListener("mousedown", (e) => {
      if (e.button === 2) {
        e.preventDefault();
        invoke("cancel_snip");
        return;
      }
      if (e.button !== 0 || !imgReady) return;
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      curX = e.clientX;
      curY = e.clientY;
      hintPill.style.display = "none";
      render();
    });

    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      curX = e.clientX;
      curY = e.clientY;
      render();
    });

    window.addEventListener("mouseup", async (e) => {
      if (e.button !== 0 || !dragging) return;
      dragging = false;
      sizeBadge.style.display = "none";

      const x = Math.min(startX, curX);
      const y = Math.min(startY, curY);
      const w = Math.abs(curX - startX);
      const h = Math.abs(curY - startY);

      if (w < 12 || h < 12) {
        hintPill.style.display = "block";
        render();
        return;
      }

      // Cắt vùng ảnh theo độ phân giải gốc của màn hình
      const sx = Math.round((x / window.innerWidth) * screenImg.naturalWidth);
      const sy = Math.round((y / window.innerHeight) * screenImg.naturalHeight);
      const sw = Math.max(1, Math.round((w / window.innerWidth) * screenImg.naturalWidth));
      const sh = Math.max(1, Math.round((h / window.innerHeight) * screenImg.naturalHeight));

      const cropCanvas = document.createElement("canvas");
      cropCanvas.width = sw;
      cropCanvas.height = sh;
      const cropCtx = cropCanvas.getContext("2d");
      cropCtx.drawImage(screenImg, sx, sy, sw, sh, 0, 0, sw, sh);

      const dataUrl = cropCanvas.toDataURL("image/png");
      const base64 = dataUrl.split(",")[1];
      await invoke("finish_snip", {
        imageBase64: base64,
        cropRect: { x: sx, y: sy, width: sw, height: sh },
      });
    });

    window.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      invoke("cancel_snip");
    });

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        invoke("cancel_snip");
      }
    });

    await listen("snip-ready", loadScreen);
    loadScreen();
