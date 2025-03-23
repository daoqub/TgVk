@echo off
chcp 65001 > nul
echo Сборка всех Python файлов в один...

python -c "
import os
from pathlib import Path

def collect_files_content(root_dir, output_file):
    try:
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write('СОДЕРЖИМОЕ ВСЕХ PYTHON ФАЙЛОВ ПРОЕКТА\n\n')
            for dirpath, dirnames, filenames in os.walk(root_dir):
                for filename in filenames:
                    if filename.endswith('.py'):
                        file_path = os.path.join(dirpath, filename)
                        relative_path = os.path.relpath(file_path, root_dir)
                        
                        out_file.write('\n\n')
                        out_file.write('=' * 80 + '\n')
                        out_file.write(f'ФАЙЛ: {relative_path}\n')
                        out_file.write('=' * 80 + '\n\n')
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                out_file.write(f.read())
                        except UnicodeDecodeError:
                            try:
                                with open(file_path, 'r', encoding='cp1251') as f:
                                    out_file.write(f.read())
                            except Exception as e:
                                out_file.write(f'ОШИБКА ЧТЕНИЯ ФАЙЛА: {e}\n')
            
            out_file.write('\n\nСБОРКА ЗАВЕРШЕНА\n')
        print(f'Файлы успешно собраны в {output_file}')
    except Exception as e:
        print(f'Ошибка при сборке файлов: {e}')

# Директория текущего скрипта - корень проекта
root_directory = '.'
output_filename = 'project_all_python_files.txt'
collect_files_content(root_directory, output_filename)
" 

echo.
echo Процесс завершен.
pause
