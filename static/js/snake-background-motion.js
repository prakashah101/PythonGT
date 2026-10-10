(() => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || document.documentElement.classList.contains("a11y-reduced-motion")) return;

  const image = document.querySelector(".python-snake-scene img");
  const selector = image ? ".python-snake-scene img" : "body::before";
  const eventTarget = image || document.body;
  const style = document.createElement("style");
  style.id = "snake-random-motion";
  document.head.appendChild(style);

  let cycle = 0;
  let activeAnimation = "";
  function randomizeMotion() {
    const points = 2 + Math.floor(Math.random() * 3);
    const name = `snake-drift-${++cycle}`;
    activeAnimation = name;
    const frames = ["0% { transform:scale(1.1) translate3d(0,0,0); }"];

    for (let i = 1; i <= points; i += 1) {
      const percent = Math.round((i / (points + 1)) * 100);
      const x = (Math.random() * 1.6 - .8).toFixed(2);
      const y = (Math.random() * .8 - .4).toFixed(2);
      frames.push(`${percent}% { transform:scale(1.1) translate3d(${x}%,${y}%,0); }`);
    }

    frames.push("100% { transform:scale(1.1) translate3d(0,0,0); }");
    const duration = 48 + Math.random() * 12;
    style.textContent = `@keyframes ${name} { ${frames.join(" ")} } ${selector} { animation:${name} ${duration.toFixed(1)}s cubic-bezier(.45,0,.55,1) infinite normal; }`;
  }

  randomizeMotion();
  eventTarget.addEventListener("animationiteration", event => {
    if (event.animationName === activeAnimation && (image || event.pseudoElement === "::before")) randomizeMotion();
  });
})();
