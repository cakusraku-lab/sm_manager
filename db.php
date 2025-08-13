<?php
require_once __DIR__ . '/config.php';

function get_db(): PDO {
    static $db = null;
    if ($db === null) {
        $needInit = !file_exists(DB_FILE);
        $db = new PDO('sqlite:' . DB_FILE);
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        if ($needInit) {
            init_db($db);
        }
    }
    return $db;
}

function init_db(PDO $db): void {
    $db->exec("CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT,
        title TEXT,
        description TEXT,
        publish_date TEXT,
        status TEXT,
        tags TEXT,
        series_id INTEGER
    )");

    $db->exec("CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        category TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )");

    $db->exec("CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        due_date TEXT,
        status TEXT
    )");

    $db->exec("CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        weekdays TEXT,
        platforms TEXT
    )");
}
?>