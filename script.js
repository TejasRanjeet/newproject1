$(document).ready(function() {
    $('#startExam').click(function() {
        $.get('/start_exam', function(data) {
            alert(data.status);
            startStatusCheck();
        });
    });

    $('#endExam').click(function() {
        $.get('/end_exam', function(data) {
            alert(data.status);
            stopStatusCheck();
        });
    });

    function updateStatus() {
        $.get('/check_status', function(data) {
            $('#status').html(
                'Exam in progress: ' + data.exam_in_progress + 
                '<br>Exam terminated: ' + data.exam_terminated +
                '<br>Current window: ' + data.current_window +
                '<br>Noise level: ' + data.noise_level
            );
            if (data.exam_terminated) {
                stopStatusCheck();
                alert("Exam has been terminated. This could be due to no face detected, multiple face detected , tab switch, or excessive noise.");
            }
        });
    }

    let statusInterval;
    function startStatusCheck() {
        statusInterval = setInterval(updateStatus, 1000);
    }

    function stopStatusCheck() {
        clearInterval(statusInterval);
    }
});