<!-- chatbox 對話框 -->
<div id="smartchat-wrapper" class="chat-fixed-wrapper" style="display: block;">
    <div class="chat-box">
        <div class="chat-header">
            <img class="mascot" src="<?php echo $WEB_ROOT ?>/images/robot_.png" alt="mascot" />
            <p class="header-name">AI 路況小幫手</p>
            <button class="close-btn" onclick="closeSmartChat()">×</button>
        </div>

        <div class="chat-messages" id="chatMessages">
            <div class="system-message">
                <img class="mascot" src="<?php echo $WEB_ROOT ?>/images/robot_.png" alt="mascot" />
                <div class="message-content">
                    歡迎使用1968智能客服！<br>
                    可詢問：交通狀況、事故通報、國道即時路況等。
                </div>
                <div class="system-time">
                    <?php $ampm = date("A") === "AM" ? "上午" : "下午";
                    echo $ampm . " " . date("h:i"); ?>
                </div>
            </div>
        </div>

        <div class="chat-footer">
            <!-- ✅ 漢堡按鈕 -->
            <button class="menu-btn" id="chatMenuBtn" aria-label="開啟選單">
                <span class="menu-icon"></span>
            </button>

            <!-- ✅ 2×2 選單卡片 -->
            <div class="menu-panel" id="chatMenu" aria-hidden="true" role="menu">
                <ul class="menu-grid">
                    <li class="menu-item" role="menuitem" data-key="交通路況">
                        <!-- <div class="mi-icon" aria-hidden="true">🚗</div> -->
                        <div class="mi-text">
                            <div class="mi-title">交通路況</div>
                            <!-- <div class="mi-desc">即時壅塞、事故與路段</div> -->
                        </div>
                    </li>
                    <li class="menu-item" role="menuitem" data-key="行車安全">
                        <!-- <div class="mi-icon" aria-hidden="true">🛡️</div> -->
                        <div class="mi-text">
                            <div class="mi-title">行車安全</div>
                            <!-- <div class="mi-desc">規則速限、天候與事故處理</div> -->
                        </div>
                    </li>
                    <li class="menu-item" role="menuitem" data-key="服務資訊">
                        <!-- <div class="mi-icon" aria-hidden="true">🛠️</div> -->
                        <div class="mi-text">
                            <div class="mi-title">服務資訊</div>
                            <!-- <div class="mi-desc">收費制度、服務區、轉乘</div> -->
                        </div>
                    </li>
                    <li class="menu-item" role="menuitem" data-key="常見問題">
                        <!-- <div class="mi-icon" aria-hidden="true">❓</div> -->
                        <div class="mi-text">
                            <div class="mi-title">常見問題</div>
                            <!-- <div class="mi-desc">帳號、功能、故障排除</div> -->
                        </div>
                    </li>
                </ul>
            </div>

            <textarea id="chatInput" class="chat-input" placeholder="輸入訊息..." rows="1" style="overflow:hidden; resize: none;"></textarea>
            <button class="send-btn" onclick="sendMessage()">
                <img src="<?php echo $WEB_ROOT ?>/images/send.png" alt="傳送" class="send-icon" />
            </button>
        </div>
    </div>
</div>