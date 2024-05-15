from flask_login import current_user

# Политики доступа к ресурсам
# Класс имеет в себе набор методов, каждый из которых отвечает за определенные действия
class UsersPolicy:
    def __init__(self, record):
		# Передаем запись из БД, над которой будут производиться действия
        self.record = record

    def create(self):
        return current_user.is_admin()

    def delete(self):
        return current_user.is_admin()

    def show(self):
        return True
    
    def edit(self):
        # Может редактировать, если id соответствует id из записи
        if current_user.id == self.record.id:
            return True
        # Иначе срабатывает функция на проверку админки
        return current_user.is_admin()

    # Разрешение просматривать статистику администратору
    def show_statistics(self):
        return current_user.is_admin()

    # Возможность иметь кнопку в меню виситс
    def show_user_visits(self):
        return current_user.is_admin()
    
    def show_all_view_button(self):
        return current_user.is_admin()
    
	# Назначать роль может только администратор
    def change_role(self):
        return current_user.is_admin()