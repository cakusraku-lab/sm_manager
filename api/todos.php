<?php
require_once __DIR__ . '/../db.php';
require_login();
header('Content-Type: application/json');
$db = get_db();
$method = $_SERVER['REQUEST_METHOD'];

switch ($method) {
    case 'GET':
        $stmt = $db->query('SELECT * FROM todos ORDER BY due_date');
        echo json_encode($stmt->fetchAll(PDO::FETCH_ASSOC));
        break;
    case 'POST':
        $data = json_decode(file_get_contents('php://input'), true);
        $stmt = $db->prepare('INSERT INTO todos (title, description, due_date, status) VALUES (?,?,?,?)');
        $stmt->execute([
            $data['title'] ?? '',
            $data['description'] ?? '',
            $data['due_date'] ?? '',
            $data['status'] ?? 'open'
        ]);
        echo json_encode(['id' => $db->lastInsertId()]);
        break;
    case 'PUT':
        $id = $_GET['id'] ?? 0;
        $data = json_decode(file_get_contents('php://input'), true);
        $stmt = $db->prepare('UPDATE todos SET title=?, description=?, due_date=?, status=? WHERE id=?');
        $stmt->execute([
            $data['title'] ?? '',
            $data['description'] ?? '',
            $data['due_date'] ?? '',
            $data['status'] ?? '',
            $id
        ]);
        echo json_encode(['success' => true]);
        break;
    case 'DELETE':
        $id = $_GET['id'] ?? 0;
        $stmt = $db->prepare('DELETE FROM todos WHERE id=?');
        $stmt->execute([$id]);
        echo json_encode(['success' => true]);
        break;
    default:
        http_response_code(405);
        echo json_encode(['error' => 'Method not allowed']);
}
?>
