import mysql.connector
from flask import g # импортируем для переменной, в которой будут храниться данные для текущего запроса

# Класс MySQL, который ничего не наследует
class MySQL:
	# Метод __init__ получает объект приложения, т.к в нем хранится конфигурация приложения и базы данных
	def __init__(self, app):
		self.app = app
		# метод teardown_appcontext, его не вызываем, а указываем, чтобы приложение само могло его вызвать и закрыть подключение, когда это будет необходимо
		self.app.teardown_appcontext(self.close_connection)
	
	# Метод config, извлекает из приложения конфигурацию и возвращает её в виде словаря
	def config(self):
		return {
            "user": self.app.config['MYSQL_USER'], 
            "password": self.app.config['MYSQL_PASSWORD'],
            "host": self.app.config['MYSQL_HOST'],
            "database": self.app.config['MYSQL_DATABASE']
        }

	# Метод close_connection отвечает за закрытие соединения c БД
	def close_connection(self, e=None):
		# Обращается к значению db в глобальном объекте g при помощи метода pop(то есть оно удаляется и возвращается), если такого значения нет, то None
		db = g.pop('db', None)
		# Если какое-то соединение было открыто, то есть в переменную db было записано значение НЕ None, то соединение закрываем
		if db is not None:
			db.close()

	# Метод connection, устанавливает соединение и возвращает объект соединения
	def connection(self):
		# Если соединения нет, то мы будем его устанавливать
		if 'db' not in g:
			# При помощи двух звездочек вызванный словарь распаковывается
			g.db = mysql.connector.connect(**self.config())
		# Если соединение было ранее установлено, то просто возвращается объект этого соединения
		return g.db