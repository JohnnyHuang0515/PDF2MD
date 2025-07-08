import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from .base_parser import standard_question_dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.image_naming import generate_image_path_for_parser

def load_docx_paragraphs(docx_path: str) -> List[str]:
    """從 DOCX 檔案載入段落列表"""
    from docx import Document
    from pathlib import Path
    
    docx_path = Path(docx_path)
    doc = Document(docx_path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]

def load_md_paragraphs(md_path: str) -> List[Any]:
    """從 MD 檔案載入段落列表，返回與 DOCX 段落相似的結構"""
    class MockParagraph:
        def __init__(self, text):
            self.text = text
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    paragraphs = []
    for line in content.split('\n'):
        if line.strip():
            paragraphs.append(MockParagraph(line.strip()))
    
    return paragraphs

def extract_answer_from_question_header(text: str) -> Optional[str]:
    """從題目標頭提取答案，如 '( Ｂ )1.' -> 'B'"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    # 匹配各種括號內答案格式
    patterns = [
        r'[（(]\s*([Ａ-ＦABCDEF])\s*[）)]',  # 全形或半形括號
        r'[（(]\s*([A-F])\s*[）)]'           # 標準格式
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            answer = match.group(1)
            # 轉換全形字母為半形
            answer = answer.translate(str.maketrans("ＡＢＣＤＥＦ", "ABCDEF"))
            return answer
    return None

def extract_question_number(text: str) -> Optional[str]:
    """提取題目編號，如 '( Ｂ )1.' -> '1'"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    # 匹配題目編號格式
    patterns = [
        r'[（(]\s*[Ａ-ＦABCDEF]\s*[）)]\s*(\d+)[．.]',  # 選擇題格式
        r'^(\d+)[．.]',                                   # 填充題格式
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def extract_options_from_text(text: str) -> Optional[Dict[str, str]]:
    """從文字中提取選項"""
    options = {}
    
    # 匹配選項格式 (A)、(B)、(C)、(D)
    pattern = r'[（(]([A-D])[）)]\s*([^（(]*?)(?=[（(][A-D][）)]|$)'
    matches = re.finditer(pattern, text)
    
    for match in matches:
        option_key = match.group(1)
        option_text = match.group(2).strip()
        if option_text:
            # 清理選項文字
            option_text = re.sub(r'[；;]+$', '', option_text)  # 移除末尾分號
            option_text = option_text.strip()
            if option_text:
                options[option_key] = option_text
    
    return options if len(options) >= 2 else None

def clean_question_text(text: str) -> str:
    """清理題目文字"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    # 移除答案前綴 ( Ｂ )1. 或 1.
    text = re.sub(r'^[（(]\s*[Ａ-ＦABCDEF]\s*[）)]\s*\d+[．.]\s*', '', text)
    text = re.sub(r'^\d+[．.]\s*', '', text)
    
    # 移除選項部分
    text = re.sub(r'[（(][A-D][）)].*$', '', text, flags=re.DOTALL)
    
    # 移除分數資訊
    text = re.sub(r'每題\s*\d+\s*分', '', text)
    text = re.sub(r'共\s*\d+\s*分', '', text)
    
    # 清理空白和標點
    text = re.sub(r'^[\s，。、：；]+', '', text)
    text = re.sub(r'[\s，。、：；]+$', '', text)
    
    return text.strip()

def is_section_header(text: str) -> Optional[str]:
    """識別區塊標題"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    headers = [
        r'A部分[/／]?實力養成題',
        r'B部分[/／]?概念延伸題',
        r'\*\*A部分[/／]?實力養成題',
        r'\*\*B部分[/／]?概念延伸題',
        r'一、基礎選擇題',
        r'二、填充題',
        r'三、題組題',
        r'四、.*題',
        r'五、.*題',
        r'\*\*一、基礎選擇題',
        r'\*\*二、填充題',
        r'\*\*三、題組題',
        r'\*\*四、.*題',
        r'\*\*五、.*題'
    ]
    
    for header in headers:
        if re.search(header, text):
            return text
    return None

def is_choice_question(text: str) -> bool:
    """判斷是否為選擇題"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    # 檢查是否有答案格式 ( Ｂ )1.
    if re.search(r'[（(]\s*[Ａ-ＦABCDEF]\s*[）)]\s*\d+[．.]', text):
        return True
    return False

def is_fill_blank_question(text: str) -> bool:
    """判斷是否為填充題"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    # 檢查是否為純數字編號格式 1.
    if re.match(r'^\d+[．.]', text) and not is_choice_question(text):
        return True
    return False

def is_group_intro(text: str) -> bool:
    """判斷是否為題組說明"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    return text.startswith('◎')

def has_image_reference(text: str) -> bool:
    """檢查是否有圖片引用"""
    # 確保 text 是字串
    if hasattr(text, 'text'):
        text = text.text
    text = str(text)
    
    image_keywords = ['圖', '附圖', '如圖', '下圖', '上圖', '圖表', '附表']
    return any(keyword in text for keyword in image_keywords)

def parse_science_questions(file_path: str) -> List[Dict[str, Any]]:
    """解析自然科檔案中的題目，支援 DOCX 和 MD 格式"""
    from pathlib import Path
    
    file_path = Path(file_path)
    
    # 根據副檔名決定使用哪個載入函數
    if file_path.suffix.lower() == '.md':
        paragraphs = load_md_paragraphs(str(file_path))
    else:
        paragraphs = load_docx_paragraphs(str(file_path))
    questions = []
    
    current_section = None
    current_group = None
    current_group_id = 0
    img_counter = 0
    
    i = 0
    while i < len(paragraphs):
        paragraph = paragraphs[i]
        text = paragraph.text if hasattr(paragraph, 'text') else str(paragraph)
        
        # 檢查區塊標題
        section_header = is_section_header(text)
        if section_header:
            current_section = section_header
            current_group = None
            i += 1
            continue
        
        # 檢查題組說明
        if is_group_intro(text):
            current_group_id += 1
            current_group = {
                'id': current_group_id,
                'intro': text[1:].strip(),  # 移除◎符號
                'image_path': None
            }
            
            # 檢查題組是否有圖片
            if has_image_reference(text):
                img_counter += 1
                current_group['image_path'] = generate_image_path_for_parser(file_path, str(img_counter), ".png")
            
            i += 1
            continue
        
        # 解析選擇題
        if is_choice_question(text):
            question_num = extract_question_number(text)
            answer = extract_answer_from_question_header(text)
            question_text = clean_question_text(text)
            
            # 尋找選項（可能在當前行或後續幾行）
            options = extract_options_from_text(text)
            if not options:
                # 在後續行中尋找選項
                j = i + 1
                option_text = text
                while j < len(paragraphs) and j < i + 3:
                    next_paragraph = paragraphs[j]
                    next_text = next_paragraph.text if hasattr(next_paragraph, 'text') else str(next_paragraph)
                    if is_choice_question(next_text) or is_fill_blank_question(next_text) or is_group_intro(next_text):
                        break
                    option_text += " " + next_text
                    j += 1
                options = extract_options_from_text(option_text)
            
            if options and len(options) >= 2:
                # 檢查圖片引用
                image_path = None
                if has_image_reference(question_text):
                    img_counter += 1
                    image_path = generate_image_path_for_parser(file_path, str(img_counter), ".png")
                
                # 決定題目類型
                if current_group:
                    question_type = "題組題"
                else:
                    question_type = "選擇題"
                
                question_dict = {
                    "subject": "Physics_and_Chemistry",
                    "question_text": question_text,
                    "options": options,
                    "answer": answer,
                    "question_type": question_type,
                    "image_path": image_path,
                    "section": current_section,
                    "question_number": question_num
                }
                
                # 如果是題組題，添加題組資訊
                if current_group:
                    question_dict["group_id"] = current_group['id']
                    question_dict["group_intro"] = current_group['intro']
                    question_dict["group_image_path"] = current_group['image_path']
                
                questions.append(question_dict)
            
            i += 1
            continue
        
        # 解析填充題
        if is_fill_blank_question(text):
            question_num = extract_question_number(text)
            question_text = clean_question_text(text)
            
            # 填充題的答案通常需要人工標記或從題目中推斷
            # 這裡暫時設為空，可以後續改進
            
            # 檢查圖片引用
            image_path = None
            if has_image_reference(question_text):
                img_counter += 1
                image_path = generate_image_path_for_parser(file_path, str(img_counter), ".png")
            
            question_dict = {
                "subject": "Physics_and_Chemistry", 
                "question_text": question_text,
                "options": None,
                "answer": None,  # 填充題答案需要特別處理
                "question_type": "填充題",
                "image_path": image_path,
                "section": current_section,
                "question_number": question_num
            }
            
            questions.append(question_dict)
            i += 1
            continue
        
        i += 1
    
    return questions

def parse_science(docx_path: str) -> List[Dict[str, Any]]:
    """主要的自然科解析函數 - 兼容舊版本調用"""
    try:
        questions = parse_science_questions(docx_path)
        
        # 使用新的 standard_question_dict 格式化輸出
        formatted_questions = []
        for q in questions:
            formatted_q = standard_question_dict(
                question_text=q["question_text"],
                options=q["options"] if q["options"] else {},
                answer=q["answer"] if q["answer"] else "",
                file_path=docx_path,
                image_path=q.get("image_path")
            )
            
            formatted_questions.append(formatted_q)
        
        return formatted_questions
        
    except Exception as e:
        print(f"解析自然科檔案時發生錯誤: {e}")
        return []
