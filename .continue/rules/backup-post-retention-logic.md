---
globs: "**/schedulers.py, **/post_management_service.py, **/calendar_manager.py"
alwaysApply: true
---

При удалении постов различай два случая: 1) Автоматическое удаление по истечении delete_time - удалять только из основных каналов, НЕ трогать бекап канал (посты остаются в календаре для истории). 2) Ручное удаление пользователем через кнопку - удалять из всех мест включая бекап канал (delete_from_backup=True). Используй параметр delete_from_backup в методе delete_post().