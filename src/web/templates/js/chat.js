const query = (obj) =>
  Object.keys(obj)
    .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(obj[k]))
    .join("&");
const colorThemes = document.querySelectorAll('[name="theme"]');
const markdown = window.markdownit();
const message_box = document.getElementById(`messages`);
const message_input = document.getElementById(`message-input`);
const box_conversations = document.querySelector(`.top`);
const spinner = box_conversations.querySelector(".spinner");
const stop_generating = document.querySelector(`.stop_generating`);
const send_button = document.querySelector(`#send-button`);
let prompt_lock = false;


function resizeTextarea(textarea) {
  textarea.style.height = '80px';
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

const format = (text) => {
  return text.replace(/(?:\r\n|\r|\n)/g, "<br>");
};

const escapeHtml = (text) => {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

const renderProgressPopup = (progressLogs, openByDefault = false, processingTimeMs = null) => {
  const hasProgress = Array.isArray(progressLogs) && progressLogs.length > 0;
  const hasTiming = Number.isFinite(processingTimeMs) && processingTimeMs >= 0;
  if (!hasProgress && !hasTiming) {
    return "";
  }
  const items = (progressLogs || [])
    .map((line) => `<li>${escapeHtml(line)}</li>`)
    .join("");
  const totalTime = hasTiming
    ? `<div class="progress-total-time">Total processing time: ${(processingTimeMs / 1000).toFixed(1)}s</div>`
    : "";

  return `
    <details class="progress-popup" ${openByDefault ? "open" : ""}>
      <summary>Progress${hasProgress ? ` (${progressLogs.length})` : ""}</summary>
      <ul>${items}</ul>
      ${totalTime}
    </details>
  `;
};

const renderMessageHtml = (
  role,
  content,
  progressLogs = [],
  token = null,
  processingTimeMs = null
) => {
  const isAssistant = role === "assistant";
  const body = isAssistant ? processRawResponse(content) : format(content);
  const popup = isAssistant ? renderProgressPopup(progressLogs, false, processingTimeMs) : "";
  const userId = token ? `id="${isAssistant ? "gpt" : "user"}_${token}"` : "";

  return `
    <div class="message">
      <div class="user">
        ${isAssistant ? gpt_image : user_image}
      </div>
      <div class="content" ${userId}>
        ${popup}
        ${body}
      </div>
    </div>
  `;
};

const renderAssistantLiveContent = (progressLogs = []) => {
  const popup = renderProgressPopup(progressLogs, true);
  return `${popup}<div id="cursor"></div>`;
};

const updateAssistantProgress = (token, progressLogs = []) => {
  const target = document.getElementById(`gpt_${token}`);
  if (!target) return;
  target.innerHTML = renderAssistantLiveContent(progressLogs);
};

const startProgressPolling = (token) => {
  let active = true;
  let latestLogs = ["Starting..."];

  const poll = async () => {
    while (active) {
      try {
        const res = await fetch(`/backend-api/v2/progress/${token}`);
        if (res.ok) {
          const payload = await res.json();
          if (
            Array.isArray(payload.progress_logs) &&
            (payload.progress_logs.length > 0 || payload.done)
          ) {
            latestLogs = payload.progress_logs;
            updateAssistantProgress(token, latestLogs);
          }
          if (payload.done) {
            break;
          }
        }
      } catch (_e) {
        // Keep polling until final response arrives.
      }
      await new Promise((r) => setTimeout(r, 9000));
    }
  };

  poll();

  return () => {
    active = false;
    return latestLogs;
  };
};

message_input.addEventListener("blur", () => {
  window.scrollTo(0, 0);
});

message_input.addEventListener("focus", () => {
  document.documentElement.scrollTop = document.documentElement.scrollHeight;
});

const delete_conversations = async () => {
  localStorage.clear();
  await new_conversation();
};

const handle_ask = async () => {
  message_input.style.height = `80px`;
  message_input.focus();

  window.scrollTo(0, 0);
  let message = message_input.value;

  if (message.length > 0) {
    message_input.value = ``;
    await ask_gpt(message);
  }
};

const remove_cancel_button = async () => {
  stop_generating.classList.add(`stop_generating-hiding`);

  setTimeout(() => {
    stop_generating.classList.remove(`stop_generating-hiding`);
    stop_generating.classList.add(`stop_generating-hidden`);
  }, 300);
};


function processRawResponse(text) {
  let htmlcontent = markdown.render(text);
  htmlcontent = htmlcontent
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"');

  // remove empty paragraph <p></p>
  htmlcontent = htmlcontent.replace(/<p><\/p>/g, "");

  return htmlcontent;
}


const ask_gpt = async (message) => {
  let assistant_text = ``;
  let assistant_progress_logs = [];
  let assistant_processing_time_ms = null;
  let stopPolling = null;
  try {
    message_input.value = ``;
    message_input.innerHTML = ``;
    message_input.innerText = ``;

    add_conversation(window.conversation_id, message.substr(0, 20));
    window.scrollTo(0, 0);
    window.controller = new AbortController();

    // jailbreak = document.getElementById("jailbreak");
    // model = document.getElementById("model");
    prompt_lock = true;
    window.text = ``;
    window.token = message_id();

    stop_generating.classList.remove(`stop_generating-hidden`);

    message_box.innerHTML += renderMessageHtml("user", message, [], window.token);

    /* .replace(/(?:\r\n|\r|\n)/g, '<br>') */

    message_box.scrollTop = message_box.scrollHeight;
    window.scrollTo(0, 0);

    message_box.innerHTML += `
            <div class="message">
                <div class="user">
                    ${gpt_image}
                </div>
                <div class="content" id="gpt_${window.token}">
                    ${renderAssistantLiveContent(["Starting..."])}
                </div>
            </div>
        `;

    message_box.scrollTop = message_box.scrollHeight;
    window.scrollTo(0, 0);
    const responsePromise = fetch(`/backend-api/v2/conversation`, {
      method: `POST`,
      signal: window.controller.signal,
      headers: {
        "content-type": `application/json`,
        accept: `application/json`,
      },
      body: JSON.stringify({
        conversation_id: window.conversation_id,
        action: `_ask`,
        meta: {
          id: window.token,
          content: {
            conversation: await get_conversation(window.conversation_id),
            content_type: "text",
            parts: [
              {
                content: message,
                role: "user",
              },
            ],
          },
        },
      }),
    });
    stopPolling = startProgressPolling(window.token);
    const response = await responsePromise;

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const responseText = await response.text();
    assistant_text = responseText;
    try {
      const payload = JSON.parse(responseText);
      if (payload && typeof payload.content === "string") {
        assistant_text = payload.content;
      }
      if (payload && Array.isArray(payload.progress_logs)) {
        assistant_progress_logs = payload.progress_logs;
      }
      if (payload && Number.isFinite(payload.processing_time_ms)) {
        assistant_processing_time_ms = payload.processing_time_ms;
      }
    } catch (_e) {
      assistant_progress_logs = [];
    }

    if (stopPolling) {
      const polledLogs = stopPolling();
      if (assistant_progress_logs.length === 0 && Array.isArray(polledLogs)) {
        assistant_progress_logs = polledLogs;
      }
    }

    document.getElementById(`gpt_${window.token}`).innerHTML =
      renderProgressPopup(assistant_progress_logs, false, assistant_processing_time_ms)
      + processRawResponse(assistant_text);

    window.scrollTo(0, 0);
    message_box.scrollTo({ top: message_box.scrollHeight, behavior: "auto" });

    add_message(window.conversation_id, "user", message);
    add_message(
      window.conversation_id,
      "assistant",
      assistant_text,
      assistant_progress_logs,
      assistant_processing_time_ms
    );

    message_box.scrollTop = message_box.scrollHeight;
    await remove_cancel_button();
    prompt_lock = false;

    await load_conversations(20, 0);
    window.scrollTo(0, 0);
  } catch (e) {
    if (stopPolling) {
      stopPolling();
    }
    add_message(window.conversation_id, "user", message);

    message_box.scrollTop = message_box.scrollHeight;
    await remove_cancel_button();
    prompt_lock = false;

    await load_conversations(20, 0);

    console.log(e);

    let cursorDiv = document.getElementById(`cursor`);
    if (cursorDiv) cursorDiv.parentNode.removeChild(cursorDiv);

    if (e.name != `AbortError`) {
      let error_message = `oops ! something went wrong, please try again / reload. [stacktrace in console]`;

      document.getElementById(`gpt_${window.token}`).innerHTML = error_message;
      add_message(window.conversation_id, "assistant", error_message);
    } else {
      document.getElementById(`gpt_${window.token}`).innerHTML += ` [aborted]`;
      add_message(window.conversation_id, "assistant", assistant_text + ` [aborted]`);
    }

    window.scrollTo(0, 0);
  }
};

const clear_conversations = async () => {
  const elements = box_conversations.childNodes;
  let index = elements.length;

  if (index > 0) {
    while (index--) {
      const element = elements[index];
      if (
        element.nodeType === Node.ELEMENT_NODE &&
        element.tagName.toLowerCase() !== `button`
      ) {
        box_conversations.removeChild(element);
      }
    }
  }
};

const clear_conversation = async () => {
  let messages = message_box.getElementsByTagName(`div`);

  while (messages.length > 0) {
    message_box.removeChild(messages[0]);
  }
};

const show_option = async (conversation_id) => {
  const conv = document.getElementById(`conv-${conversation_id}`);
  const yes = document.getElementById(`yes-${conversation_id}`);
  const not = document.getElementById(`not-${conversation_id}`);

  conv.style.display = "none";
  yes.style.display = "block";
  not.style.display = "block"; 
}

const hide_option = async (conversation_id) => {
  const conv = document.getElementById(`conv-${conversation_id}`);
  const yes = document.getElementById(`yes-${conversation_id}`);
  const not = document.getElementById(`not-${conversation_id}`);

  conv.style.display = "block";
  yes.style.display = "none";
  not.style.display = "none"; 
}

const delete_conversation = async (conversation_id) => {
  localStorage.removeItem(`conversation:${conversation_id}`);

  const conversation = document.getElementById(`convo-${conversation_id}`);
    conversation.remove();

  if (window.conversation_id == conversation_id) {
    await new_conversation();
  }

  await load_conversations(20, 0, true);
};

const set_conversation = async (conversation_id) => {
  history.pushState({}, null, `/chat/${conversation_id}`);
  window.conversation_id = conversation_id;

  await clear_conversation();
  await load_conversation(conversation_id);
  await load_conversations(20, 0, true);
};

const new_conversation = async () => {
  history.pushState({}, null, `/chat/`);
  window.conversation_id = uuid();

  await clear_conversation();
  await load_conversations(20, 0, true);
};

const load_conversation = async (conversation_id) => {
  let conversation = await JSON.parse(
    localStorage.getItem(`conversation:${conversation_id}`)
  );
  console.log(conversation, conversation_id);

  for (item of conversation.items) {
    message_box.innerHTML += renderMessageHtml(
      item.role,
      item.content,
      item.progress_logs || [],
      null,
      item.processing_time_ms ?? null
    );
  }

  document.querySelectorAll(`code`).forEach((el) => {
    hljs.highlightElement(el);
  });

  message_box.scrollTo({ top: message_box.scrollHeight, behavior: "smooth" });

  setTimeout(() => {
    message_box.scrollTop = message_box.scrollHeight;
  }, 500);
};

const get_conversation = async (conversation_id) => {
  let conversation = await JSON.parse(
    localStorage.getItem(`conversation:${conversation_id}`)
  );
  return conversation.items;
};

const add_conversation = async (conversation_id, title) => {
  if (localStorage.getItem(`conversation:${conversation_id}`) == null) {
    localStorage.setItem(
      `conversation:${conversation_id}`,
      JSON.stringify({
        id: conversation_id,
        title: title,
        items: [],
      })
    );
  }
};

const add_message = async (
  conversation_id,
  role,
  content,
  progress_logs = [],
  processing_time_ms = null
) => {
  before_adding = JSON.parse(
    localStorage.getItem(`conversation:${conversation_id}`)
  );

  before_adding.items.push({
    role: role,
    content: content,
    progress_logs: progress_logs,
    processing_time_ms: processing_time_ms,
  });

  localStorage.setItem(
    `conversation:${conversation_id}`,
    JSON.stringify(before_adding)
  ); // update conversation
};

const load_conversations = async (limit, offset, loader) => {
  //console.log(loader);
  //if (loader === undefined) box_conversations.appendChild(spinner);

  let conversations = [];
  for (let i = 0; i < localStorage.length; i++) {
    if (localStorage.key(i).startsWith("conversation:")) {
      let conversation = localStorage.getItem(localStorage.key(i));
      conversations.push(JSON.parse(conversation));
    }
  }

  //if (loader === undefined) spinner.parentNode.removeChild(spinner)
  await clear_conversations();

  for (conversation of conversations) {
    box_conversations.innerHTML += `
    <div class="convo" id="convo-${conversation.id}">
      <div class="left" onclick="set_conversation('${conversation.id}')">
          <span class="convo-title">${conversation.title}</span>
      </div>
      <div onclick="show_option('${conversation.id}')" id="conv-${conversation.id}">
        <div style="width: 10px;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path fill="#00000055" d="M135.2 17.7L128 32 32 32C14.3 32 0 46.3 0 64S14.3 96 32 96l384 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-96 0-7.2-14.3C307.4 6.8 296.3 0 284.2 0L163.8 0c-12.1 0-23.2 6.8-28.6 17.7zM416 128L32 128 53.2 467c1.6 25.3 22.6 45 47.9 45l245.8 0c25.3 0 46.3-19.7 47.9-45L416 128z"/></svg>
        </div>
      </div>
      <div onclick="delete_conversation('${conversation.id}')" id="yes-${conversation.id}" style="display:none;">&#10003</div>
      <div onclick="hide_option('${conversation.id}')" id="not-${conversation.id}" style="display:none;">X</div>
    </div>
    `;
  }

  document.querySelectorAll(`code`).forEach((el) => {
    hljs.highlightElement(el);
  });
};

document.getElementById(`cancelButton`).addEventListener(`click`, async () => {
  window.controller.abort();
  console.log(`aborted ${window.conversation_id}`);
});

function h2a(str1) {
  var hex = str1.toString();
  var str = "";

  for (var n = 0; n < hex.length; n += 2) {
    str += String.fromCharCode(parseInt(hex.substr(n, 2), 16));
  }

  return str;
}

const uuid = () => {
  return `xxxxxxxx-xxxx-4xxx-yxxx-${Date.now().toString(16)}`.replace(
    /[xy]/g,
    function (c) {
      var r = (Math.random() * 16) | 0,
        v = c == "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    }
  );
};

const message_id = () => {
  random_bytes = (Math.floor(Math.random() * 1338377565) + 2956589730).toString(
    2
  );
  unix = Math.floor(Date.now() / 1000).toString(2);

  return BigInt(`0b${unix}${random_bytes}`).toString();
};

window.onload = async () => {

  conversations = 0;
  for (let i = 0; i < localStorage.length; i++) {
    if (localStorage.key(i).startsWith("conversation:")) {
      conversations += 1;
    }
  }

  if (conversations == 0) localStorage.clear();

  await setTimeout(() => {
    load_conversations(20, 0);
  }, 1);

  if (!window.location.href.endsWith(`#`)) {
    if (/\/chat\/.+/.test(window.location.href)) {
      await load_conversation(window.conversation_id);
    }
  }

message_input.addEventListener(`keydown`, async (evt) => {
    if (prompt_lock) return;
    if (evt.keyCode === 13 && !evt.shiftKey) {
        evt.preventDefault();
        console.log('pressed enter');
        await handle_ask();
    } else {
      message_input.style.removeProperty("height");
      message_input.style.height = message_input.scrollHeight + 4 + "px";
    }
  });

  send_button.addEventListener(`click`, async () => {
    console.log("clicked send");
    if (prompt_lock) return;
    await handle_ask();
  });

};

document.querySelector(".mobile-sidebar").addEventListener("click", (event) => {
  const sidebar = document.querySelector(".conversations");

  if (sidebar.classList.contains("shown")) {
    sidebar.classList.remove("shown");
    event.target.classList.remove("rotated");
  } else {
    sidebar.classList.add("shown");
    event.target.classList.add("rotated");
  }

  window.scrollTo(0, 0);
});
