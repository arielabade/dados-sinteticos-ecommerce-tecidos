-- O usuário de análise lê o banco bruto e cria os schemas do dbt (tecidos_*).
GRANT ALL PRIVILEGES ON `tecidos`.* TO 'analista'@'%';
GRANT ALL PRIVILEGES ON `tecidos\_%`.* TO 'analista'@'%';
FLUSH PRIVILEGES;
