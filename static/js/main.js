document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".alert").forEach(el => {
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(-5px)"; }, 4500);
    setTimeout(() => el.remove(), 5000);
  });
});




/* NRP STORE opening animation with automatic sound attempt */
document.addEventListener("DOMContentLoaded", function () {
    const splash = document.getElementById("nrp-splash");
    if (!splash) return;

    const soundButton = document.getElementById("nrp-sound-toggle");
    let soundStarted = false;

    function playSplashSound() {
        if (soundStarted) return;

        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;

        const ctx = new AudioCtx();

        ctx.resume().then(() => {
            const master = ctx.createGain();
            master.gain.setValueAtTime(0.0001, ctx.currentTime);
            master.gain.linearRampToValueAtTime(0.045, ctx.currentTime + 0.3);
            master.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + 2);
            master.connect(ctx.destination);

            [261.63, 329.63, 392, 523.25].forEach((frequency, i) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.value = frequency;
                gain.gain.value = 0.2;
                osc.connect(gain);
                gain.connect(master);
                osc.start(ctx.currentTime + i * 0.12);
                osc.stop(ctx.currentTime + 2);
            });

            soundStarted = true;
            if (soundButton) soundButton.style.display = "none";
            setTimeout(() => ctx.close(), 2300);
        }).catch(() => {});
    }

    if (soundButton) {
        soundButton.addEventListener("click", playSplashSound);
    }

    playSplashSound();

    setTimeout(function () {
        splash.classList.add("is-leaving");
        setTimeout(function () {
            splash.remove();
        }, 700);
    }, 5000);
});
