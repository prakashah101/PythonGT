(() => {
  const keywordPattern = /^(?:False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)$/;
  const builtinPattern = /^(?:abs|all|any|bool|dict|enumerate|float|input|int|len|list|map|max|min|open|print|range|reversed|round|set|sorted|str|sum|super|tuple|type|zip)$/;
  const tokenPattern = /(?<comment>\#[^\n]*)|(?<string>'''[\s\S]*?'''|"""[\s\S]*?"""|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")|(?<word>\b[A-Za-z_]\w*\b)|(?<number>\b\d+(?:\.\d+)?\b)/g;

  function escapeHtml(value) {
    return value.replace(/[&<>]/g, character => ({"&":"&amp;", "<":"&lt;", ">":"&gt;"})[character]);
  }

  function highlight(source) {
    let result = "";
    let cursor = 0;
    tokenPattern.lastIndex = 0;
    for (const match of source.matchAll(tokenPattern)) {
      const token = match[0];
      const groups = match.groups || {};
      let className = "";
      if (groups.comment) className = "tok-comment";
      else if (groups.string) className = "tok-string";
      else if (groups.number) className = "tok-number";
      else if (groups.word && keywordPattern.test(token)) className = "tok-keyword";
      else if (groups.word && builtinPattern.test(token)) className = "tok-builtin";
      result += escapeHtml(source.slice(cursor, match.index));
      result += className ? `<span class="${className}">${escapeHtml(token)}</span>` : escapeHtml(token);
      cursor = match.index + token.length;
    }
    result += escapeHtml(source.slice(cursor));
    return result || " ";
  }

  function dispatchInput(editor) {
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function initEditor(frame) {
    const editor = frame.querySelector(".python-editor-input");
    const gutter = frame.querySelector(".ide-gutter pre");
    const highlightLayer = frame.querySelector(".ide-highlight code");
    const position = frame.querySelector(".ide-position");
    if (!editor || !gutter || !highlightLayer) return;

    function update() {
      const source = editor.value;
      const lineCount = source.split("\n").length;
      gutter.textContent = Array.from({ length: lineCount }, (_, index) => index + 1).join("\n");
      highlightLayer.innerHTML = highlight(source) + (source.endsWith("\n") ? " " : "");
      highlightLayer.style.transform = `translate(${-editor.scrollLeft}px, ${-editor.scrollTop}px)`;
      gutter.style.transform = `translateY(${-editor.scrollTop}px)`;

      if (position) {
        const beforeCursor = source.slice(0, editor.selectionStart);
        const line = beforeCursor.split("\n");
        position.textContent = `Ln ${line.length}, Col ${line[line.length - 1].length + 1}`;
      }
    }

    editor.addEventListener("input", update);
    editor.addEventListener("scroll", update, { passive: true });
    editor.addEventListener("click", update);
    editor.addEventListener("keyup", update);
    editor.addEventListener("select", update);
    if (frame.dataset.smartKeys !== "false") editor.addEventListener("keydown", event => {
      if (event.key === "Tab") {
        event.preventDefault();
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        if (event.shiftKey) {
          const lineStart = editor.value.lastIndexOf("\n", start - 1) + 1;
          const indentation = editor.value.slice(lineStart, start).match(/^ {1,4}/)?.[0];
          if (indentation) {
            editor.setRangeText("", lineStart, lineStart + indentation.length, "start");
            dispatchInput(editor);
          }
          return;
        }
        editor.setRangeText("    ", start, end, "end");
        dispatchInput(editor);
        return;
      }

      if (event.key === "Enter") {
        event.preventDefault();
        const cursor = editor.selectionStart;
        const lineStart = editor.value.lastIndexOf("\n", cursor - 1) + 1;
        const currentLine = editor.value.slice(lineStart, cursor);
        let indent = currentLine.match(/^\s*/)?.[0] || "";
        const trimmedLine = currentLine.trimEnd();
        if (trimmedLine.endsWith(":") || ["(", "[", "{"].some(opening => trimmedLine.endsWith(opening))) indent += "    ";
        editor.setRangeText(`\n${indent}`, editor.selectionStart, editor.selectionEnd, "end");
        dispatchInput(editor);
        return;
      }

      const pairs = { "(": ")", "[": "]", "{": "}", "'": "'", "\"": "\"" };
      if (pairs[event.key] && editor.selectionStart === editor.selectionEnd) {
        event.preventDefault();
        const cursor = editor.selectionStart;
        if (event.key === editor.value[cursor] && [")", "]", "}", "'", "\""].includes(event.key)) {
          editor.setSelectionRange(cursor + 1, cursor + 1);
          update();
          return;
        }
        editor.setRangeText(event.key + pairs[event.key], cursor, cursor, "select");
        editor.setSelectionRange(cursor + 1, cursor + 1);
        dispatchInput(editor);
      }
    });

    update();
  }

  document.querySelectorAll("[data-python-editor]").forEach(initEditor);
  document.documentElement.classList.add("python-editors-ready");
})();
