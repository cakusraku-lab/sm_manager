<?php
require_once __DIR__ . '/../db.php';
require_login();
header('Content-Type: application/json');
$db = get_db();

$method = $_SERVER['REQUEST_METHOD'];

switch ($method) {
    case 'GET':
        $stmt = $db->query('SELECT * FROM posts ORDER BY publish_date');
        echo json_encode($stmt->fetchAll(PDO::FETCH_ASSOC));
        break;
    case 'POST':
        $data = json_decode(file_get_contents('php://input'), true);
        $stmt = $db->prepare('INSERT INTO posts (platform, title, description, publish_date, status, tags, series_id) VALUES (?,?,?,?,?,?,?)');
        $stmt->execute([
            $data['platform'] ?? '',
            $data['title'] ?? '',
            $data['description'] ?? '',
            $data['publish_date'] ?? '',
            $data['status'] ?? 'idea',
            $data['tags'] ?? '',
            $data['series_id'] ?? null
        ]);
        echo json_encode(['id' => $db->lastInsertId()]);
        break;
    case 'PUT':
        $id = $_GET['id'] ?? 0;
        $data = json_decode(file_get_contents('php://input'), true);
        $stmt = $db->prepare('SELECT * FROM posts WHERE id=?');
        $stmt->execute([$id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC) ?: [];
        $data = array_merge($row, $data);
        $stmt = $db->prepare('UPDATE posts SET platform=?, title=?, description=?, publish_date=?, status=?, tags=?, series_id=? WHERE id=?');
        $stmt->execute([
            $data['platform'] ?? '',
            $data['title'] ?? '',
            $data['description'] ?? '',
            $data['publish_date'] ?? '',
            $data['status'] ?? '',
            $data['tags'] ?? '',
            $data['series_id'] ?? null,
            $id
        ]);
        echo json_encode(['success' => true]);
        break;
    case 'DELETE':
        $id = $_GET['id'] ?? 0;
        $stmt = $db->prepare('DELETE FROM posts WHERE id=?');
        $stmt->execute([$id]);
        echo json_encode(['success' => true]);
        break;
    default:
        http_response_code(405);
        echo json_encode(['error' => 'Method not allowed']);
}
?>
