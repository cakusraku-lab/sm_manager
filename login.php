<?php
require_once __DIR__ . '/config.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents('php://input'), true);
    $user = $data['username'] ?? '';
    $pass = $data['password'] ?? '';
    if ($user === APP_USER && password_verify($pass, APP_PASS_HASH)) {
        $_SESSION['user'] = $user;
        echo json_encode(['success' => true]);
    } else {
        http_response_code(401);
        echo json_encode(['error' => 'Invalid credentials']);
    }
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    session_destroy();
    echo json_encode(['success' => true]);
    exit;
}

echo json_encode(['error' => 'Unsupported method']);
?>