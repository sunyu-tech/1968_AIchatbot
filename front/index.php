<?php
// 可依實際情況設為你的根目錄網址，例如部署上線時換成正式網址
$WEB_ROOT = ".";  // 若放在網站根目錄就用 "."，子資料夾請改為 "./1968_Front"
?>
<!DOCTYPE html>
<html lang="zh-Hant">
<link rel="icon" href="<?php echo $WEB_ROOT; ?>/menu_logo.ico">

<head>
    <meta charset="UTF-8">
    <title>1968 智能客服</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- CSS -->
    <link rel="stylesheet" href="<?php echo $WEB_ROOT; ?>/css/chatbox.css">
</head>

<body style="margin: 0; padding: 0; background: #f5f5f5;">

    <!-- 對話框 -->
    <?php include("./includes/chatbox.php"); ?>

    <!-- JS -->
    <script>
        const WEB_ROOT = "<?php echo $WEB_ROOT ?>";
    </script>
    <script src="<?php echo $WEB_ROOT; ?>/js/robot.js"></script>
</body>

</html>