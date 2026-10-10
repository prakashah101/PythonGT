/* Runs learner-authored Python in a dedicated Web Worker using Pyodide. */
let runtimePromise;

async function getRuntime() {
  if (!runtimePromise) {
    const runtimeUrl = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
    importScripts(`${runtimeUrl}pyodide.js`);
    runtimePromise = loadPyodide({ indexURL: runtimeUrl }).then(pyodide => {
      pyodide.setStdout({ batched: text => self.postMessage({ type: "stdout", text: `${text}\n` }) });
      pyodide.setStderr({ batched: text => self.postMessage({ type: "stderr", text: `${text}\n` }) });
      return pyodide;
    }).catch(error => {
      runtimePromise = null;
      throw error;
    });
  }
  return runtimePromise;
}

self.addEventListener("message", async event => {
  const message = event.data || {};
  if (message.type === "init") {
    self.postMessage({ type: "loading" });
    try {
      await getRuntime();
      self.postMessage({ type: "ready" });
    } catch (error) {
      self.postMessage({ type: "error", text: `Python runtime failed to load. Check your internet connection and try again.\n${error.message || error}` });
      self.postMessage({ type: "done" });
    }
    return;
  }

  if (message.type !== "run") return;
  try {
    const pyodide = await getRuntime();
    self.postMessage({ type: "running" });
    const input = `${message.stdin || ""}\n`;
    const inputChars = Array.from(input);
    pyodide.setStdin({ stdin: () => inputChars.length ? inputChars.shift().codePointAt(0) : null });
    await pyodide.runPythonAsync(message.code || "");
  } catch (error) {
    self.postMessage({ type: "error", text: `${error.message || error}\n` });
  } finally {
    self.postMessage({ type: "done" });
  }
});
