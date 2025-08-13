<?php
session_start();

// Database file path
const DB_FILE = __DIR__ . '/data.sqlite';

// Simple credentials - change in production
const APP_USER = 'admin';
const APP_PASS_HASH = '$2y$12$aO.pPc4/1yrZ0f/TK.9dtuA7iFx3OvCKg7jjSEsKYn7c0Kt3r151.';

function require_login() {
    if (!isset($_SESSION['user'])) {
        http_response_code(401);
        echo json_encode(['error' => 'Unauthorized']);
        exit;
    }
}
?>