from __future__ import annotations


CDP_NODE_SCRIPT = r"""
const fs = require("node:fs");

function emit(payload) {
  process.stdout.write(JSON.stringify(payload));
}

function endpointFromInput(value) {
  return String(value || "http://127.0.0.1:9225").replace(/\/+$/, "");
}

function compactTarget(target) {
  return {
    id: target.id,
    type: target.type,
    title: target.title,
    url: target.url,
  };
}

function selectChatTarget(targets) {
  const pages = targets.filter((target) => target.webSocketDebuggerUrl && target.type === "page");
  return (
    pages.find((target) => String(target.url || "").includes("doubao://doubao-chat/chat/")) ||
    pages.find((target) => String(target.url || "").includes("doubao-chat")) ||
    null
  );
}

async function fetchJson(endpoint, path) {
  const response = await fetch(endpoint + path);
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return await response.json();
}

async function connect(webSocketDebuggerUrl) {
  return await new Promise((resolve, reject) => {
    const ws = new WebSocket(webSocketDebuggerUrl);
    const timer = setTimeout(() => reject(new Error("Timed out while opening CDP WebSocket")), 10000);
    ws.addEventListener("open", () => {
      clearTimeout(timer);
      resolve(ws);
    });
    ws.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new Error("Failed to open CDP WebSocket"));
    });
  });
}

function createClient(ws) {
  let nextId = 1;
  const pending = new Map();

  ws.addEventListener("message", (event) => {
    let text;
    if (typeof event.data === "string") {
      text = event.data;
    } else if (event.data instanceof ArrayBuffer) {
      text = Buffer.from(event.data).toString("utf8");
    } else {
      text = Buffer.from(event.data).toString("utf8");
    }
    const message = JSON.parse(text);
    if (!message.id || !pending.has(message.id)) {
      return;
    }
    const { resolve, reject, timer } = pending.get(message.id);
    clearTimeout(timer);
    pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message || JSON.stringify(message.error)));
    } else {
      resolve(message.result || {});
    }
  });

  function send(method, params = {}, timeoutMs = 15000) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`${method} timed out`));
      }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  return { send };
}

async function evaluate(client, source, args = [], timeoutMs = 15000) {
  const expression = `(${source})(...${JSON.stringify(args)})`;
  const result = await client.send(
    "Runtime.evaluate",
    {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    },
    timeoutMs,
  );
  if (result.exceptionDetails) {
    const details = result.exceptionDetails;
    const description = details.exception && details.exception.description;
    throw new Error(description || details.text || "Runtime.evaluate failed");
  }
  return result.result ? result.result.value : undefined;
}

const statusSource = function () {
  const input = document.querySelector(
    'textarea[data-testid="chat_input_input"], textarea, [contenteditable="true"]',
  );
  const bodyText = document.body ? document.body.innerText || "" : "";
  return {
    ok: Boolean(input),
    inputFound: Boolean(input),
    title: document.title,
    url: location.href,
    bodyTextLength: bodyText.length,
    bodyTextTail: bodyText.slice(-1000),
  };
};

const readSource = function () {
  const normalizeText = (value) => String(value || "").replace(/\u00a0/g, " ").replace(/\r/g, "");
  const bodyText = normalizeText(document.body ? document.body.innerText || "" : "");
  const blocks = Array.from(document.querySelectorAll('[data-testid="message-block-container"]'))
    .map((element) => normalizeText(element.innerText || "").trim())
    .filter(Boolean);
  const latestMessage = blocks.length ? blocks[blocks.length - 1] : "";
  return {
    ok: Boolean(bodyText.trim()),
    response: (latestMessage || bodyText.slice(-8000)).trim(),
    title: document.title,
    url: location.href,
    bodyTextLength: bodyText.length,
  };
};

const askSource = async function (prompt, options) {
  const timeoutMs = Math.max(1000, Number(options.timeoutMs) || 180000);
  const settleMs = Math.max(800, Number(options.settleMs) || 3000);
  const startedAt = Date.now();
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const normalizeText = (value) => String(value || "").replace(/\u00a0/g, " ").replace(/\r/g, "");
  const bodyText = () => normalizeText(document.body ? document.body.innerText || "" : "");
  const visible = (element) => {
    if (!element || !element.isConnected) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const labelFor = (element) =>
    normalizeText(
      [
        element.innerText,
        element.getAttribute && element.getAttribute("aria-label"),
        element.getAttribute && element.getAttribute("title"),
        element.getAttribute && element.getAttribute("data-testid"),
      ]
        .filter(Boolean)
        .join(" "),
    );

  function findInput() {
    const selectors = [
      'textarea[data-testid="chat_input_input"]',
      'textarea[placeholder*="发"]',
      "textarea",
      '[contenteditable="true"]',
    ];
    for (const selector of selectors) {
      const candidate = Array.from(document.querySelectorAll(selector)).find(
        (element) => visible(element) && !element.disabled && !element.readOnly,
      );
      if (candidate) return candidate;
    }
    return null;
  }

  function setInputValue(element, value) {
    if ("value" in element) {
      const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
      if (descriptor && descriptor.set) {
        descriptor.set.call(element, value);
      } else {
        element.value = value;
      }
    } else {
      element.textContent = value;
      element.innerText = value;
    }
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: " " }));
  }

  function findSendButton() {
    const preferred = [
      'button[data-testid="chat_input_send_button"]',
      'button[aria-label*="发送"]',
      'button[title*="发送"]',
      '[role="button"][aria-label*="发送"]',
    ];
    for (const selector of preferred) {
      const candidate = Array.from(document.querySelectorAll(selector)).find(
        (element) => visible(element) && !element.disabled && element.getAttribute("aria-disabled") !== "true",
      );
      if (candidate) return candidate;
    }
    return Array.from(document.querySelectorAll("button,[role='button']")).find((element) => {
      if (!visible(element) || element.disabled || element.getAttribute("aria-disabled") === "true") return false;
      return /发送|send/i.test(labelFor(element));
    });
  }

  function findNewChatButton() {
    return Array.from(document.querySelectorAll("button,a,[role='button']")).find((element) => {
      if (!visible(element) || element.disabled || element.getAttribute("aria-disabled") === "true") return false;
      return /新对话|新建对话|新聊天|new chat/i.test(labelFor(element));
    });
  }

  function extractAfterPrompt(text, before, userPrompt) {
    const promptIndex = text.lastIndexOf(userPrompt);
    if (promptIndex >= 0) {
      return text.slice(promptIndex + userPrompt.length);
    }
    if (text.startsWith(before)) {
      return text.slice(before.length);
    }
    let index = 0;
    const max = Math.min(text.length, before.length);
    while (index < max && text[index] === before[index]) {
      index += 1;
    }
    return text.slice(index);
  }

  function extractMessageAfterPrompt(userPrompt) {
    const blocks = Array.from(document.querySelectorAll('[data-testid="message-block-container"]'))
      .filter(visible)
      .map((element) => normalizeText(element.innerText || "").trim())
      .filter(Boolean);
    let promptBlockIndex = -1;
    for (let index = 0; index < blocks.length; index += 1) {
      if (blocks[index].includes(userPrompt)) {
        promptBlockIndex = index;
      }
    }
    if (promptBlockIndex >= 0) {
      for (let index = promptBlockIndex + 1; index < blocks.length; index += 1) {
        if (blocks[index] && !blocks[index].includes(userPrompt)) {
          return blocks[index];
        }
      }
    }
    return "";
  }

  function cleanTail(tail) {
    const normalized = normalizeText(tail).trim();
    if (!normalized) return "";
    const noisePatterns = [
      /^办公任务$/,
      /^搜索$/,
      /^AI\s/,
      /^AI$/,
      /^图像生成$/,
      /^翻译$/,
      /^查看更多$/,
      /^帮我写作$/,
      /^学术搜索$/,
      /^PPT 生成$/,
      /^视频生成$/,
      /^更多$/,
      /^用户\d+$/,
    ];
    const rawLines = normalized
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const lines = rawLines.filter((line) => !noisePatterns.some((pattern) => pattern.test(line)));
    if (!lines.length && rawLines.some((line) => noisePatterns.some((pattern) => pattern.test(line)))) {
      return "";
    }
    return (lines.join("\n").trim() || normalized).slice(-8000);
  }

  if (options.startNew) {
    const newChat = findNewChatButton();
    if (newChat) {
      newChat.click();
      await sleep(1000);
    }
  }

  const beforeText = bodyText();
  const input = findInput();
  if (!input) {
    return {
      ok: false,
      error: "Could not find Doubao chat input",
      title: document.title,
      url: location.href,
      bodyTextTail: beforeText.slice(-1000),
    };
  }

  input.scrollIntoView({ block: "center" });
  input.focus();
  setInputValue(input, prompt);
  await sleep(300);

  const valueAfterSet = "value" in input ? input.value : input.innerText || input.textContent || "";
  const sendButton = findSendButton();
  if (!sendButton) {
    return {
      ok: false,
      error: "Could not find Doubao send button",
      title: document.title,
      url: location.href,
      inputValueAfterSet: valueAfterSet,
      bodyTextTail: bodyText().slice(-1000),
    };
  }

  sendButton.click();

  let sawPrompt = false;
  let sawResponseTail = false;
  let lastText = bodyText();
  let stableSince = Date.now();
  let iterations = 0;
  const deadline = startedAt + timeoutMs;

  while (Date.now() < deadline) {
    iterations += 1;
    await sleep(500);
    const currentText = bodyText();
    if (currentText.includes(prompt)) sawPrompt = true;
    const messageTail = extractMessageAfterPrompt(prompt);
    if (messageTail.trim()) sawResponseTail = true;
    if (currentText !== lastText) {
      lastText = currentText;
      stableSince = Date.now();
    }
    const currentInput = findInput();
    const currentValue = currentInput
      ? "value" in currentInput
        ? currentInput.value
        : currentInput.innerText || currentInput.textContent || ""
      : "";
    const stopVisible = Array.from(document.querySelectorAll("button,[role='button']")).some(
      (element) => visible(element) && /停止|stop/i.test(labelFor(element)),
    );
    if (
      sawPrompt &&
      sawResponseTail &&
      Date.now() - stableSince >= settleMs &&
      !stopVisible &&
      String(currentValue || "").trim() !== prompt
    ) {
      break;
    }
  }

  const afterText = bodyText();
  const response = cleanTail(extractMessageAfterPrompt(prompt) || extractAfterPrompt(afterText, beforeText, prompt));
  if (!response) {
    return {
      ok: false,
      error: "No Doubao response text detected before timeout",
      title: document.title,
      url: location.href,
      beforeTextLength: beforeText.length,
      afterTextLength: afterText.length,
      sawPrompt,
      sawResponseTail,
      iterations,
    };
  }
  return {
    ok: true,
    response,
    title: document.title,
    url: location.href,
    beforeTextLength: beforeText.length,
    afterTextLength: afterText.length,
    sawPrompt,
    sawResponseTail,
    iterations,
  };
};

async function main() {
  const inputText = fs.readFileSync(0, "utf8");
  const input = inputText ? JSON.parse(inputText) : {};
  const endpoint = endpointFromInput(input.endpoint);
  const operation = input.operation || "status";

  if (typeof fetch !== "function" || typeof WebSocket !== "function") {
    emit({
      ok: false,
      error: "cdp-app requires Node.js with built-in fetch and WebSocket support",
      diagnostics: { cdp_endpoint: endpoint },
    });
    process.exit(1);
  }

  const version = await fetchJson(endpoint, "/json/version");
  const targets = await fetchJson(endpoint, "/json/list");
  const target = selectChatTarget(targets);
  const diagnostics = {
    cdp_endpoint: endpoint,
    browser: version.Browser,
    protocol_version: version["Protocol-Version"],
    target_count: targets.length,
    targets: targets.map(compactTarget).slice(0, 20),
  };

  if (!target) {
    emit({
      ok: false,
      error: "Could not find a Doubao chat CDP target",
      diagnostics,
    });
    process.exit(1);
  }

  diagnostics.target = compactTarget(target);
  const ws = await connect(target.webSocketDebuggerUrl);
  const client = createClient(ws);

  try {
    await client.send("Runtime.enable");
    try {
      await client.send("Page.bringToFront", {}, 5000);
    } catch (_) {
      // Doubao can reject bringToFront for non-standard app pages; DOM automation still works.
    }

    let result;
    if (operation === "ask") {
      result = await evaluate(
        client,
        askSource.toString(),
        [
          String(input.prompt || ""),
          {
            timeoutMs: Math.max(1000, Number(input.timeout_seconds || 180) * 1000),
            settleMs: 3000,
            startNew: Boolean(input.start_new),
          },
        ],
        Math.max(5000, Number(input.timeout_seconds || 180) * 1000 + 10000),
      );
    } else if (operation === "read") {
      result = await evaluate(client, readSource.toString(), [], 15000);
    } else if (operation === "status") {
      result = await evaluate(client, statusSource.toString(), [], 15000);
    } else {
      throw new Error(`Unsupported CDP operation: ${operation}`);
    }

    diagnostics.page = {
      title: result && result.title,
      url: result && result.url,
      input_found: result && result.inputFound,
      body_text_length: result && result.bodyTextLength,
      before_text_length: result && result.beforeTextLength,
      after_text_length: result && result.afterTextLength,
      iterations: result && result.iterations,
      saw_prompt: result && result.sawPrompt,
      saw_response_tail: result && result.sawResponseTail,
    };

    if (!result || result.ok === false) {
      emit({
        ok: false,
        error: (result && result.error) || "CDP operation failed",
        stdout: (result && result.bodyTextTail) || "",
        diagnostics,
      });
      process.exit(1);
    }

    const response = result.response || "";
    emit({
      ok: true,
      response,
      stdout: operation === "status" ? `Connected to ${result.url || target.url}` : response,
      diagnostics,
    });
  } finally {
    ws.close();
  }
}

main().catch((error) => {
  emit({
    ok: false,
    error: error && error.stack ? error.stack : String(error),
  });
  process.exit(1);
});
"""
