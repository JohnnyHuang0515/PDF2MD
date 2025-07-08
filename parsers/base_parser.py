import re
from pathlib import Path
from typing import Dict, Any, Optional

def extract_file_info(file_path: str) -> Dict[str, str]:
    """從檔案路徑提取學期、年級、出版社、科目等資訊"""
    path = Path(file_path)
    parts = path.parts
    
    # 預設值
    info = {
        "semester": "",
        "grade": "",
        "publisher": "",
        "subject": "",
        "chapter": "",
        "scope": "國中"  # 預設為國中
    }
    
    try:
        # 解析路徑結構：input_md/111A/7/Hanlin/Math/檔案名.md
        if len(parts) >= 5:
            # 提取學期資訊 (111A -> 111上)
            year_sem = parts[-5]  # 111A
            if year_sem:
                year = ''.join(filter(str.isdigit, year_sem))  # 111
                semester_code = year_sem.replace(year, '')     # A
                semester_map = {'A': '上', 'B': '下'}
                info["semester"] = f"{year}{semester_map.get(semester_code, '')}"
            
            # 提取年級 (7 -> 七年級)
            grade_num = parts[-4]  # 7
            grade_map = {
                '7': '七年級', '8': '八年級', '9': '九年級',
                '1': '一年級', '2': '二年級', '3': '三年級',
                '4': '四年級', '5': '五年級', '6': '六年級'
            }
            info["grade"] = grade_map.get(grade_num, f"{grade_num}年級")
            
            # 提取出版社
            publisher_folder = parts[-3]  # Hanlin
            publisher_map = {
                'Hanlin': '翰林', 'Knsh': '康軒', 'Nani': '南一'
            }
            info["publisher"] = publisher_map.get(publisher_folder, publisher_folder)
            
            # 提取科目
            subject_folder = parts[-2]  # Math
            subject_map = {
                'Math': '數學',
                'Chinese': '國文', 
                'English': '英語',
                'Physics_and_Chemistry': '理化',
                'Biology': '生物',
                'Science': '自然',
                'History': '歷史',
                'Geography': '地理',
                'Civics_and_Society': '公民'
            }
            info["subject"] = subject_map.get(subject_folder, subject_folder)
        
        # 從檔案名提取章節資訊
        filename = path.stem
        chapter_match = re.search(r'(Ch\d+[-\d]*|L\d+|第\d+章|第\d+課)', filename)
        if chapter_match:
            info["chapter"] = chapter_match.group(1)
            
    except (IndexError, AttributeError):
        pass
    
    return info

def standard_question_dict(
    question_text: str,     # 題目內容
    options: Dict[str, str], # 選項
    answer: str,            # 答案
    file_path: str = "",    # 檔案路徑（用於提取資訊）
    image_path: Optional[str] = None,  # 圖片路徑
    subject: str = "",      # 科目（可覆蓋從路徑提取的）
    grade: str = "",        # 年級（可覆蓋從路徑提取的）
    publisher: str = "",    # 出版社（可覆蓋從路徑提取的）
    semester: str = "",     # 學期（可覆蓋從路徑提取的）
    chapter: str = "",      # 章節（可覆蓋從路徑提取的）
    scope: str = "國中"     # 範圍
) -> Dict[str, Any]:
    """創建標準化的題目字典格式"""
    
    # 從檔案路徑提取資訊
    file_info = extract_file_info(file_path) if file_path else {}
    
    # 使用提供的參數或從檔案路徑提取的資訊
    final_subject = subject or file_info.get("subject", "")
    final_grade = grade or file_info.get("grade", "")
    final_publisher = publisher or file_info.get("publisher", "")
    final_semester = semester or file_info.get("semester", "")
    final_chapter = chapter or file_info.get("chapter", "")
    final_scope = scope or file_info.get("scope", "國中")
    
    # 不再添加前綴，直接使用原始問題文字
    formatted_question = question_text
    
    return {
        "question": formatted_question,
        "options": options,
        "image_path": image_path,
        "scope": final_scope,
        "grade": final_grade,
        "subject": final_subject,
        "semester": final_semester,
        "publisher": final_publisher,
        "chapter": final_chapter,
        "answer": answer
    }
