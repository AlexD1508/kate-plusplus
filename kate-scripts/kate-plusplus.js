var katescript = {
    "author": "kate-plusplus contributors",
    "license": "MIT",
    "revision": 1,
    "kate-version": "5.1",
    "functions": ["kppFormatJson", "kppMinifyJson", "kppBase64Encode", "kppBase64Decode",
                  "kppUrlEncode", "kppUrlDecode", "kppInsertDate", "kppInsertDateTime",
                  "kppRemoveBlankLines", "kppRemoveDuplicateLines", "kppTrimTrailing"],
    "actions": [
        { "function": "kppFormatJson",          "name": "Format JSON",                   "category": "Notepad++ Tools", "shortcut": "Ctrl+Alt+Shift+M" },
        { "function": "kppMinifyJson",          "name": "Minify JSON",                   "category": "Notepad++ Tools" },
        { "function": "kppBase64Encode",        "name": "Base64 Encode",                 "category": "Notepad++ Tools" },
        { "function": "kppBase64Decode",        "name": "Base64 Decode",                 "category": "Notepad++ Tools" },
        { "function": "kppUrlEncode",           "name": "URL Encode",                    "category": "Notepad++ Tools" },
        { "function": "kppUrlDecode",           "name": "URL Decode",                    "category": "Notepad++ Tools" },
        { "function": "kppInsertDate",          "name": "Insert Date",                   "category": "Notepad++ Tools" },
        { "function": "kppInsertDateTime",      "name": "Insert Date && Time",           "category": "Notepad++ Tools", "shortcut": "Ctrl+F5" },
        { "function": "kppRemoveBlankLines",    "name": "Remove Empty Lines",            "category": "Notepad++ Tools" },
        { "function": "kppRemoveDuplicateLines","name": "Remove Duplicate Lines",        "category": "Notepad++ Tools" },
        { "function": "kppTrimTrailing",        "name": "Trim Trailing Spaces",          "category": "Notepad++ Tools" }
    ]
}; // kate-script-header, must be at the start of the file without comments, pure json

/*
 * kate-plusplus — Notepad++-style text tools for Kate.
 * https://github.com/AlexD1508/kate-plusplus  ·  MIT License
 *
 * Every tool works on the selection, or on the whole document when nothing
 * is selected, and is a single undo step.
 */

require("range.js");

// ---------------------------------------------------------------- helpers

function _wholeDocument() {
    var last = document.lines() - 1;
    return new Range(0, 0, last, document.lineLength(last));
}

// Selection (or whole document) as a text range.
function _targetRange() {
    return view.hasSelection() ? view.selection() : _wholeDocument();
}

// Selection expanded to full lines (or whole document), for line tools.
function _targetLines() {
    if (!view.hasSelection())
        return _wholeDocument();
    var sel = view.selection();
    var endLine = sel.end.line;
    if (sel.end.column === 0 && endLine > sel.start.line)
        endLine--;
    return new Range(sel.start.line, 0, endLine, document.lineLength(endLine));
}

function _replace(range, text) {
    document.editBegin();
    document.removeText(range);
    document.insertText(range.start, text);
    document.editEnd();
}

function _transform(fn) {
    var range = _targetRange();
    _replace(range, fn(document.text(range)));
}

function _transformLines(fn) {
    var range = _targetLines();
    var lines = document.text(range).split("\n");
    _replace(range, fn(lines).join("\n"));
}

function _pad(n) {
    return (n < 10 ? "0" : "") + n;
}

function _insert(text) {
    if (view.hasSelection())
        view.removeSelectedText();
    document.insertText(view.cursorPosition(), text);
}

// UTF-8 safe Base64 (the script engine has no btoa/atob).
var _B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function _utf8Bytes(str) {
    var bin = unescape(encodeURIComponent(str));
    var out = [];
    for (var i = 0; i < bin.length; i++)
        out.push(bin.charCodeAt(i));
    return out;
}

function _base64Encode(str) {
    var b = _utf8Bytes(str), out = "";
    for (var i = 0; i < b.length; i += 3) {
        var n = (b[i] << 16) | ((b[i + 1] || 0) << 8) | (b[i + 2] || 0);
        out += _B64[(n >> 18) & 63] + _B64[(n >> 12) & 63]
             + (i + 1 < b.length ? _B64[(n >> 6) & 63] : "=")
             + (i + 2 < b.length ? _B64[n & 63] : "=");
    }
    return out;
}

function _base64Decode(str) {
    var clean = str.replace(/[\s=]/g, "").replace(/-/g, "+").replace(/_/g, "/");
    if (/[^A-Za-z0-9+\/]/.test(clean))
        throw new Error("Not valid Base64");
    var bin = "";
    for (var i = 0; i < clean.length; i += 4) {
        var n = 0, chunk = clean.substr(i, 4);
        for (var j = 0; j < 4; j++)
            n = (n << 6) | (j < chunk.length ? _B64.indexOf(chunk[j]) : 0);
        bin += String.fromCharCode((n >> 16) & 255);
        if (chunk.length > 2) bin += String.fromCharCode((n >> 8) & 255);
        if (chunk.length > 3) bin += String.fromCharCode(n & 255);
    }
    try {
        return decodeURIComponent(escape(bin));
    } catch (e) {
        throw new Error("Decoded data is not UTF-8 text");
    }
}

// ---------------------------------------------------------------- tools

function kppFormatJson() {
    _transform(function (t) { return JSON.stringify(JSON.parse(t), null, 4); });
}

function kppMinifyJson() {
    _transform(function (t) { return JSON.stringify(JSON.parse(t)); });
}

function kppBase64Encode() { _transform(_base64Encode); }
function kppBase64Decode() { _transform(_base64Decode); }
function kppUrlEncode()    { _transform(encodeURIComponent); }
function kppUrlDecode()    { _transform(decodeURIComponent); }

function kppInsertDate() {
    var d = new Date();
    _insert(d.getFullYear() + "-" + _pad(d.getMonth() + 1) + "-" + _pad(d.getDate()));
}

function kppInsertDateTime() {
    var d = new Date();
    _insert(d.getFullYear() + "-" + _pad(d.getMonth() + 1) + "-" + _pad(d.getDate())
            + " " + _pad(d.getHours()) + ":" + _pad(d.getMinutes()));
}

function kppRemoveBlankLines() {
    _transformLines(function (lines) {
        return lines.filter(function (l) { return l.trim() !== ""; });
    });
}

function kppRemoveDuplicateLines() {
    _transformLines(function (lines) {
        var seen = {};
        return lines.filter(function (l) {
            if (Object.prototype.hasOwnProperty.call(seen, l)) return false;
            seen[l] = true;
            return true;
        });
    });
}

function kppTrimTrailing() {
    _transformLines(function (lines) {
        return lines.map(function (l) { return l.replace(/[ \t]+$/, ""); });
    });
}

// ---------------------------------------------------------------- help

function help(cmd) {
    var h = {
        kppFormatJson: "Pretty-print the selected JSON (or the whole document).",
        kppMinifyJson: "Compact the selected JSON onto one line.",
        kppBase64Encode: "Base64-encode the selection (UTF-8).",
        kppBase64Decode: "Decode Base64 back to text.",
        kppUrlEncode: "Percent-encode the selection for use in a URL.",
        kppUrlDecode: "Decode percent-encoded text.",
        kppInsertDate: "Insert today's date (YYYY-MM-DD).",
        kppInsertDateTime: "Insert the current date and time.",
        kppRemoveBlankLines: "Delete empty and whitespace-only lines.",
        kppRemoveDuplicateLines: "Delete repeated lines, keeping the first occurrence.",
        kppTrimTrailing: "Strip spaces and tabs at the end of each line."
    };
    return h[cmd] || "";
}
