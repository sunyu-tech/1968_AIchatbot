// ✅ 當 DOM 結構載入完成後才綁定事件，避免找不到元素錯誤
// document.addEventListener("DOMContentLoaded", function () {
//     const entryBtn = document.getElementById('smartchat-entry'); // 智能客服按鈕（右下角機器人）
//     if (entryBtn) {
//         entryBtn.addEventListener('click', function () {
//             const wrapper = document.getElementById('smartchat-wrapper'); // 對話框容器
//             if (wrapper) wrapper.style.display = 'block'; // 顯示對話框
//         });
//     } else {
//         console.warn("❌ 沒找到 smartchat-entry 按鈕，請確認它是否在畫面上");
//     }
// });

// ✅ 關閉對話框：點擊「×」時呼叫此函式
function closeSmartChat() {
    document.getElementById('smartchat-wrapper').style.display = 'none';
}

// ===== 滿意度框：一次只顯示一個 =====
let activeFeedbackBox = null;
function removeActiveFeedback() {
    if (activeFeedbackBox && activeFeedbackBox.parentNode) {
        activeFeedbackBox.parentNode.removeChild(activeFeedbackBox);
    }
    activeFeedbackBox = null;
}

function appendFeedbackUI(containerEl) {
    // 先移除舊的
    removeActiveFeedback();

    const box = document.createElement('div');
    box.className = 'feedback-card';
    box.innerHTML = `
        <div class="fb-row">
            <span class="fb-title">這則回覆是否有幫助？</span>
            <div class="fb-actions">
                <button class="fb-good">滿意</button>
                <button class="fb-bad">不滿意</button>
            </div>
        </div>
        <div class="fb-form" style="display:none;">
            <textarea class="fb-text" rows="3" placeholder="可簡述哪裡不滿意（選填）"></textarea>
            <div class="fb-form-actions">
                <button class="fb-submit">送出</button>
                <button class="fb-cancel">取消</button>
            </div>
        </div>
    `;
    containerEl.appendChild(box);
    activeFeedbackBox = box;

    const goodBtn = box.querySelector('.fb-good');
    const badBtn = box.querySelector('.fb-bad');
    const formEl = box.querySelector('.fb-form');
    const submitBtn = box.querySelector('.fb-submit');
    const cancelBtn = box.querySelector('.fb-cancel');
    const textEl = box.querySelector('.fb-text');

    goodBtn.addEventListener('click', () => {
        box.innerHTML = `<div class="fb-thanks">感謝您的回饋！</div>`;
        activeFeedbackBox = null;
    });

    badBtn.addEventListener('click', () => {
        formEl.style.display = 'block';
    });

    cancelBtn.addEventListener('click', () => {
        // 關閉表單但保留選項
        formEl.style.display = 'none';
        textEl.value = '';
    });

    submitBtn.addEventListener('click', () => {
        const content = textEl.value.trim();
        // 這裡可視需要送往後端紀錄（目前只做UI）
        // fetch('/feedback', {method:'POST', body: JSON.stringify({content}) ...})
        box.innerHTML = `<div class="fb-thanks">已收到您的意見，感謝提供！</div>`;
        activeFeedbackBox = null;
    });
}

/* =========================
   ✅ 四個選單：文雅提示 & 小工具
   ========================= */
const MENU_POLITE = {
    "交通路況": "您想查哪一路段的交通路況呢？",
    "行車安全": "您想了解哪一類行車安全資訊呢？例如道路交通規則、速限與酒駕規範、惡劣天候行車建議、事故處理與通報流程等。",
    "服務資訊": "請問您欲查詢哪一項服務資訊呢？如收費與計費方式、服務區設施與營業時段、停車與轉乘、客服通道等，我將為您詳盡說明。",
    "常見問題": "請告訴我您關心的主題，我可提供帳號設定、功能使用指引、故障排除、通知與權限等常見問題的解答。"
};

// 產生時間字串
function nowText() {
    return new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: true });
}

// 插入使用者與系統訊息（用於選單快捷）
function appendUserAndBot(userText, botText) {
    const chatBox = document.getElementById('chatMessages');

    // 使用者訊息
    const userMsg = document.createElement('div');
    userMsg.className = 'user-message';
    userMsg.innerHTML = `
        <div class="message-bubble">
            <div class="message-time">${nowText()}</div>
            <div class="message-content">${userText}</div>
        </div>`;
    chatBox.appendChild(userMsg);

    // 系統訊息（文雅提示）
    const botMsg = document.createElement('div');
    botMsg.className = 'system-message';
    botMsg.innerHTML = `
        <img class="mascot" src="${WEB_ROOT}/images/robot_.png" alt="mascot" />
        <div class="message-content">${botText}</div>
        <div class="system-time">${nowText()}</div>`;
    chatBox.appendChild(botMsg);

    // 在最新系統訊息後加「滿意度框」
    const contentEl = botMsg.querySelector('.message-content');
    if (contentEl) appendFeedbackUI(contentEl);

    chatBox.scrollTop = chatBox.scrollHeight;
}

/* =========================
   ✅ 選單：展開/關閉與點擊處理
   ========================= */
document.addEventListener("DOMContentLoaded", function () {
  const wrapper = document.getElementById('smartchat-wrapper');
  if (wrapper) wrapper.style.display = 'block';

  const btn   = document.getElementById('chatMenuBtn');
  const menu  = document.getElementById('chatMenu');
  const input = document.getElementById('chatInput');

  if (btn && menu) {
    // 開/關
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      menu.classList.toggle('open');
      menu.setAttribute('aria-hidden', menu.classList.contains('open') ? 'false' : 'true');
      // 開啟時把第一個項目設為可聚焦（鍵盤可用）
      if (menu.classList.contains('open')) {
        const first = menu.querySelector('.menu-item');
        if (first) first.focus();
      }
    });

    // 點外面關閉
    document.addEventListener('click', function (e) {
      if (!menu.classList.contains('open')) return;
      const withinMenu = menu.contains(e.target);
      const withinBtn  = btn.contains(e.target);
      if (!withinMenu && !withinBtn) {
        menu.classList.remove('open');
        menu.setAttribute('aria-hidden', 'true');
      }
    });

    // ✅ 點選單卡片：直接回覆，不動輸入框
    menu.addEventListener('click', function (e) {
      const li = e.target.closest('li[data-key]');
      if (!li) return;
      const key = li.getAttribute('data-key');

      // 文雅提示
      const MENU_POLITE = {
        "交通路況": "您想查哪一路段的交通路況呢？",
        "行車安全": "您想了解哪一類行車安全資訊呢？例如道路交通規則、速限與酒駕規範、惡劣天候行車建議、事故處理與通報流程等。",
        "服務資訊": "請問您欲查詢哪一項服務資訊呢？如收費與計費方式、服務區設施與營業時段、停車與轉乘、客服通道等，我將為您詳盡說明。",
        "常見問題": "請告訴我您關心的主題，我可提供帳號設定、功能使用指引、故障排除、通知與權限等常見問題的解答。"
      };
      const polite = MENU_POLITE[key] || "";

      // 關閉面板
      menu.classList.remove('open');
      menu.setAttribute('aria-hidden', 'true');

      // ⚠️ 不要把文字塞到輸入框
      // input.value = key;  <-- 移除

      // 直接在對話中顯示「使用者點了某選單」與文雅回覆
      appendUserAndBot(key, polite);

      // 若日後要「點選單 → 真正送到後端」，改成：
      // appendUserAndBot(key, "…正在為您查詢…");
      // fetch(...) // 呼叫你的 /chatback/query
    });

    // 鍵盤支援：Enter/Space 也可點選
    menu.addEventListener('keydown', function (e) {
      const li = e.target.closest('.menu-item');
      if (!li) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        li.click();
      }
      if (e.key === 'Escape') {
        menu.classList.remove('open');
        menu.setAttribute('aria-hidden', 'true');
        btn.focus();
      }
    });
  }

  // 輸入框：自動長高 + Enter送出（維持原有）
  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = this.scrollHeight + 'px';
    });
    chatInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
  }
});

// ✅ 傳送訊息函式（點擊送出按鈕時執行）
function sendMessage() {
    const input = document.getElementById('chatInput');        // 使用者輸入框
    const chatBox = document.getElementById('chatMessages');   // 對話顯示區
    const sendBtn = document.querySelector('.send-btn');       // 傳送按鈕
    const text = input.value.trim();                           // 輸入文字
    if (!text) return;

    // ✅ 若是四個選單關鍵字 → 不發後端、直接回覆文雅提示
    if (MENU_POLITE[text]) {
        appendUserAndBot(text, MENU_POLITE[text]);
        input.value = "";
        return;
    }

    // 使用者要送新訊息了 → 移除上一個未處理的滿意度框
    removeActiveFeedback();

    // 時間戳
    const time = new Date().toLocaleTimeString('zh-TW', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });

    // 顯示使用者訊息
    const userMsg = document.createElement('div');
    userMsg.className = 'user-message';
    userMsg.innerHTML = `
        <div class="message-bubble">
            <div class="message-time">${time}</div>
            <div class="message-content">${text}</div>
        </div>
    `;
    chatBox.appendChild(userMsg);
    chatBox.scrollTop = chatBox.scrollHeight;
    input.value = "";

    // 鎖定輸入與按鈕，避免重複發送
    input.disabled = true;
    sendBtn.disabled = true;

    console.time("⏱ fetch + GPT 回應時間");

    // 傳送 API 請求
    // fetch("https://59.126.242.4:8108/chatback/query", {
    fetch("http://127.0.0.1:8108/chatback/query/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            question: text,
            menu: "系統QA"
        })
    })
    .then(response => response.json())
    .then(data => {
        console.timeEnd("⏱ fetch + GPT 回應時間");
        console.time("⏱ 回應處理與 DOM 建構");

        const answer = data.answer || "很抱歉，找不到答案。";
        const pages = data.pages && data.pages.length ? `（第 ${data.pages.join(", ")} 頁）` : "";

        const botMsg = document.createElement('div');
        botMsg.className = 'system-message';
        botMsg.innerHTML = `
            <img class="mascot" src="${WEB_ROOT}/images/robot_.png" alt="mascot" />
            <div class="message-content">
                ${answer}
                <div class="message-source">${pages}</div>
            </div>
            <div class="system-time">${new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: true })}</div>
        `;
        chatBox.appendChild(botMsg);
        chatBox.scrollTop = chatBox.scrollHeight;

        // 在最新系統訊息後加「滿意度框」
        const contentEl = botMsg.querySelector('.message-content');
        if (contentEl) appendFeedbackUI(contentEl);

        // 解鎖輸入與按鈕
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();

        console.timeEnd("⏱ 回應處理與 DOM 建構");
    })
    .catch(error => {
        console.error("❌ 錯誤：", error);

        const botMsg = document.createElement('div');
        botMsg.className = 'system-message';
        botMsg.innerHTML = `
            <img class="mascot" src="${WEB_ROOT}/images/robot_.png" alt="mascot" />
            <div class="message-content">❌ 系統發生錯誤，請稍後再試。</div>
            <div class="system-time">${new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: true })}</div>
        `;
        chatBox.appendChild(botMsg);
        chatBox.scrollTop = chatBox.scrollHeight;

        // 解鎖輸入與按鈕
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    });
}
