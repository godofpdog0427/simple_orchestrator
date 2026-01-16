#!/usr/bin/env python3
import os
import ast
import re

def count_classes_in_file(file_path):
    """统计文件中的 class 数量"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 方法1: 使用AST解析（更准确）
        try:
            tree = ast.parse(content)
            class_count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_count += 1
            return class_count
        except SyntaxError:
            # 如果AST解析失败，使用正则表达式作为备选
            class_pattern = re.compile(r'^\s*class\s+\w+.*?:', re.MULTILINE)
            matches = class_pattern.findall(content)
            return len(matches)
    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0

def main():
    # 获取所有 .py 文件
    py_files = []
    for root, dirs, files in os.walk('.'):
        # 排除虚拟环境目录
        if 'venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    
    # 统计每个文件的 class 数量
    file_class_counts = []
    for py_file in py_files:
        class_count = count_classes_in_file(py_file)
        file_class_counts.append((py_file, class_count))
        print(f"{py_file}: {class_count} classes")
    
    # 找出包含最多 class 的文件
    if file_class_counts:
        max_file, max_count = max(file_class_counts, key=lambda x: x[1])
        print(f"\n包含最多 class 的文件: {max_file} ({max_count} classes)")
        return max_file, max_count
    else:
        print("未找到任何 .py 文件")
        return None, 0

if __name__ == "__main__":
    main()