const DEFAULT_SERVER = "http://localhost:8000";

const $ = (id) => document.getElementById(id);
const statusEl = $("status");

function setStatus(msg, cls) {
  statusEl.innerHTML = msg;
  statusEl.className = cls || "";
}

async function loadSettings() {
  const { server, token } = await chrome.storage.local.get(["server", "token"]);
  $("server").value = server || DEFAULT_SERVER;
  $("token").value = token || "";
  if (!token) $("settings").open = true; // prompt first-time setup
}

$("save").addEventListener("click", async () => {
  await chrome.storage.local.set({
    server: ($("server").value || DEFAULT_SERVER).trim(),
    token: $("token").value.trim(),
  });
  setStatus("Settings saved.", "ok");
});

// This function is serialized and run INSIDE the page (no outer references).
function extractPage() {
  const url = location.href;
  const host = location.hostname;
  const isX = /(^|\.)x\.com$|(^|\.)twitter\.com$/.test(host);
  const httpOnly = (s) => s && /^https?:\/\//.test(s);
  const imgsIn = (root) =>
    [...root.querySelectorAll("img")].map((i) => i.currentSrc || i.src).filter(httpOnly);

  let title = document.title || "";
  let text = "";
  let images = [];

  if (isX) {
    const tweets = [...document.querySelectorAll('[data-testid="tweetText"]')]
      .map((n) => n.innerText.trim())
      .filter(Boolean);
    if (tweets.length) text = tweets.join("\n\n");
    if (!text) {
      const art = document.querySelector("article");
      if (art) text = (art.innerText || "").trim();
    }
    images = [...document.querySelectorAll('[data-testid="tweetPhoto"] img')]
      .map((i) => i.currentSrc || i.src)
      .filter(httpOnly);
    const author = document.querySelector('[data-testid="User-Name"]');
    if (author) {
      const name = (author.innerText || "").split("\n")[0];
      title = name + (tweets[0] ? " — " + tweets[0].slice(0, 60) : "");
    }
  } else {
    const og = document.querySelector('meta[property="og:title"]');
    if (og && og.content) title = og.content;
    const main = document.querySelector("article") || document.querySelector("main") || document.body;
    text = (main.innerText || "").trim();
    const ogimg = document.querySelector('meta[property="og:image"]');
    if (ogimg && ogimg.content) images.push(ogimg.content);
    images = images.concat(imgsIn(main));
  }

  if (text.length > 100000) text = text.slice(0, 100000);
  return {
    url,
    title: title.slice(0, 500),
    text,
    images: [...new Set(images)].slice(0, 12),
  };
}

$("clip").addEventListener("click", async () => {
  const { server, token } = await chrome.storage.local.get(["server", "token"]);
  const base = (server || DEFAULT_SERVER).replace(/\/$/, "");
  if (!token) {
    setStatus("Set your clip token in Settings first.", "err");
    $("settings").open = true;
    return;
  }

  $("clip").disabled = true;
  setStatus("Reading page…");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result: data }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPage,
    });

    if (!data || (!data.text && !data.url)) {
      setStatus("Nothing to clip on this page.", "err");
      return;
    }

    setStatus("Sending…");
    const res = await fetch(base + "/api/clip/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify(data),
    });

    if (res.status === 201) {
      const j = await res.json();
      setStatus(`Clipped → <a href="${j.url}" target="_blank">note #${j.id}</a>`, "ok");
    } else {
      const t = await res.text();
      setStatus(`Error ${res.status}: ${t.slice(0, 120)}`, "err");
    }
  } catch (e) {
    setStatus("Failed: " + (e && e.message ? e.message : e), "err");
  } finally {
    $("clip").disabled = false;
  }
});

loadSettings();
