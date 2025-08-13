<?php
require_once __DIR__ . '/../db.php';
require_login();
$db = get_db();
$type = $_GET['type'] ?? 'csv';

if ($type === 'csv') {
    header('Content-Type: text/csv');
    header('Content-Disposition: attachment; filename="posts.csv"');
    $out = fopen('php://output', 'w');
    fputcsv($out, ['id','platform','title','description','publish_date','status','tags','series_id']);
    foreach ($db->query('SELECT * FROM posts') as $row) {
        fputcsv($out, $row);
    }
    fclose($out);
    exit;
}

if ($type === 'ics') {
    header('Content-Type: text/calendar');
    header('Content-Disposition: attachment; filename="posts.ics"');
    echo "BEGIN:VCALENDAR\nVERSION:2.0\n";
    $stmt = $db->query("SELECT * FROM posts WHERE publish_date!=''");
    foreach ($stmt as $row) {
        $date = date('Ymd\THis', strtotime($row['publish_date']));
        echo "BEGIN:VEVENT\nUID:post{$row['id']}@sm_manager\nDTSTART:$date\nSUMMARY:{$row['title']}\nEND:VEVENT\n";
    }
    echo "END:VCALENDAR";
    exit;
}

http_response_code(400);
echo json_encode(['error'=>'unknown type']);
?>
