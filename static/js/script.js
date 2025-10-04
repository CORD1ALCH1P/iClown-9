document.addEventListener('DOMContentLoaded', function() {
    // Переключение темы
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('change', function() {
            fetch('/toggle_theme', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.reload();
                }
            });
        });
    }

    // Прогресс загрузки файла
    const fileInput = document.getElementById('file-input');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                progressContainer.style.display = 'block';
                
                // Симуляция прогресса (в реальном приложении используйте XMLHttpRequest или Fetch API с отслеживанием прогресса)
                let progress = 0;
                const interval = setInterval(() => {
                    progress += Math.random() * 10;
                    if (progress >= 100) {
                        progress = 100;
                        clearInterval(interval);
                    }
                    progressBar.style.width = progress + '%';
                    progressText.textContent = Math.round(progress) + '%';
                }, 1);
            }
        });
    }

    // Автоматическое скрытие flash-сообщений
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.display = 'none';
        }, 3000);
    });
});
