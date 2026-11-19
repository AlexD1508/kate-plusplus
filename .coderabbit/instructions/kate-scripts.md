---
id: kpp-kate-scripts
name: Kate JavaScript tools
paths:
  - "kate-scripts/**"
---

These are KTextEditor command scripts (QJSEngine, no DOM/Node APIs such as `btoa` or `Buffer`).
- The `var katescript = {…};` header must stay pure JSON and stay the first statement.
- Each tool works on the selection, or on the whole document when nothing is selected, and is one undo step (`document.editBegin()` / `editEnd()`).
- Every new tool needs a case in `tests/kate-scripts.test.js` and an entry in `help()`.
