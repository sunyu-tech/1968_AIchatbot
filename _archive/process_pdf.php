<?php
// 如果請求方法為 OPTIONS，則回應預檢請求的處理邏輯
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    // 設置允許的來源，* 表示允許所有來源
    header("Access-Control-Allow-Origin: https://59.126.242.4:8106");
    // 設置允許的 HTTP 方法
    header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
    // 設置允許的 HTTP 標頭
    header("Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With");
    // 返回 204 狀態碼，表示成功但無內容
    http_response_code(204);
    // 結束腳本執行
    exit();
}

// 處理 OPTIONS 請求
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    // 返回 204 狀態碼，表示成功但無內容
    http_response_code(204);
    // 結束腳本執行，避免後續程式碼繼續執行
    exit();
}

// 確保所有情況下返回有效的 JSON
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // 獲取 POST 請求中的 JSON 資料並解碼
    $input = json_decode(file_get_contents('php://input'), true);
    $question = $input['question'] ?? ''; // 從請求中提取 'question' 字段

    if ($question) {
        // 指定 Python 解譯器的路徑
        $pythonPath = 'C:\\Users\\A\\AppData\\Local\\Programs\\Python\\Python313\\python.exe';
        // 指定 Python 腳本的路徑
        $scriptPath = 'D:\\Project\\1968_SMART_CHAT_BACK\\process_pdf.py';
        // 指定 JSON 資料的路徑
        $jsonPath = 'D:\\Project\\1968_SMART_CHAT_BACK\\PDF\\1968_QA.json';

        // 構建執行命令，包含 Python 路徑、腳本、參數
        $command = sprintf(
            '"%s" "%s" --action query --json %s --question %s',
            $pythonPath,
            $scriptPath,
            escapeshellarg($jsonPath), // 對路徑進行轉義以避免特殊字符問題
            escapeshellarg($question) // 對問題進行轉義
        );

        // 執行命令並獲取輸出
        $output = shell_exec($command);

        // 移除輸出的多餘空格
        $output = trim($output);

        if ($output) {
            // 將輸出寫入 debug.log 用於排錯
            file_put_contents('debug.log', $output . PHP_EOL, FILE_APPEND);
            // 將輸出解析為 JSON
            $response = json_decode($output, true);

            if ($response) {
                // 回傳解析後的答案
                echo json_encode(['answer' => $response['answer']]);
            } else {
                // 無法解析 Python 腳本回應時回傳錯誤
                echo json_encode([
                    'error' => 'Python 腳本回應解析失敗',
                    'raw_output' => $output // 回傳原始輸出方便調試
                ]);
            }
        } else {
            // 若 Python 腳本執行失敗，寫入 debug.log
            file_put_contents('debug.log', "Python 腳本執行失敗\n", FILE_APPEND);
            file_put_contents('debug.log', "執行的命令: $command\n", FILE_APPEND);
            // 回傳錯誤訊息
            echo json_encode(['error' => 'Python 腳本未返回任何輸出']);
        }
    } else {
        // 若未提供有效問題，回傳錯誤訊息
        echo json_encode(['error' => '未提供有效的問題']);
    }
}
