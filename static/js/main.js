document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".alert").forEach(el => {
        setTimeout(() => {
            el.style.opacity = "0";
            el.style.transform = "translateY(-5px)";
        }, 4500);
        setTimeout(() => el.remove(), 5000);
    });

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    let audioCtx = null;
    let welcomePlayed = false;

    function getAudio() {
        if (!AudioCtx) return null;
        if (!audioCtx) audioCtx = new AudioCtx();
        return audioCtx;
    }

    function playWelcomeSound() {
        const ctx = getAudio();
        if (!ctx || welcomePlayed) return;

        ctx.resume().then(() => {
            if (welcomePlayed || ctx.state !== "running") return;
            welcomePlayed = true;

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
        }).catch(() => {});
    }


    const splash = document.getElementById("nrp-splash");
    const soundButton = document.getElementById("nrp-sound-toggle");
    if (soundButton) soundButton.remove();

    if (splash) {
        try {
            if (sessionStorage.getItem("nrpSplashShown") === "1") {
                splash.remove();
            } else {
                sessionStorage.setItem("nrpSplashShown", "1");

                setTimeout(() => {
                    splash.classList.add("is-leaving");
                    setTimeout(() => splash.remove(), 700);
                }, 5000);

                // Automatic welcome music attempts during the opening animation.
                playWelcomeSound();
                window.addEventListener("load", playWelcomeSound, { once: true });
                setTimeout(playWelcomeSound, 700);
            }
        } catch (e) {
            playWelcomeSound();
        }
    }


});
