<?php
require_once __DIR__ . '/config.php';
require_login();
$dest = __DIR__ . '/backup/' . 'backup_' . date('Ymd_His') . '.sqlite';
if (copy(DB_FILE, $dest)) {
    echo 'Backup saved to ' . basename($dest);
} else {
    http_response_code(500);
    echo 'Backup failed';
}
?>