<?php
require_once __DIR__ . '/../db.php';
require_login();
header('Content-Type: application/json');
$db = get_db();
$method = $_SERVER['REQUEST_METHOD'];

switch ($method) {
    case 'GET':
        $stmt = $db->query('SELECT * FROM ideas ORDER BY created_at DESC');
        echo json_encode($stmt->fetchAll(PDO::FETCH_ASSOC));
        break;
    case 'POST':
        $data = json_decode(file_get_contents('php://input'), true);
        $stmt = $db->prepare('INSERT INTO ideas (title, description, category) VALUES (?,?,?)');
        $stmt->execute([
            $data['title'] ?? '',
            $data['description'] ?? '',
            $data['category'] ?? ''
        ]);
        echo json_encode(['id' => $db->lastInsertId()]);
        break;
    case 'DELETE':
        $id = $_GET['id'] ?? 0;
        $stmt = $db->prepare('DELETE FROM ideas WHERE id=?');
        $stmt->execute([$id]);
        echo json_encode(['success' => true]);
        break;
    default:
        http_response_code(405);
        echo json_encode(['error' => 'Method not allowed']);
}
?>
