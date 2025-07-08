from __future__ import annotations

"""math_parser.py
提供擷取 LaTeX 數學式的工具函式。
目前僅偵測 `$...$` inline 與 `$$...$$` block 兩種常見表示法。
之後若有其他格式，可再擴充。
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.image_naming import generate_image_path_for_parser

# ────────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ────────────────────────────────────────────────────────────────────────────────
# 非貪婪匹配，確保同一行內多式子可分開擷取
INLINE_MATH_RE = re.compile(r"\\$(.+?)\\$")
BLOCK_MATH_RE = re.compile(r"\\$\\$(.+?)\\$\\$", re.DOTALL)

# 改進的答案識別模式
ANSWER_PREFIX_RE = re.compile(r"^[（(]\s*([Ａ-ＤABCD])\s*[）)]\s*(\d+\.?)?")
OPTION_RE = re.compile(r"[（(]([Ａ-ＤABCD])[）)]\s*([^（()]+?)(?=[（(][Ａ-ＤABCD][）)]|$)")
FW_MAP = str.maketrans("ＡＢＣＤ", "ABCD")
IMAGE_KEYWORDS = ("圖", "附圖", "如圖")
IMAGE_PATH_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")

# 題目分隔標記
QUESTION_SEPARATOR_RE = re.compile(r"^\s*(\d+)\.?\s+")
FILL_IN_BLANK_RE = re.compile(r"^\*\*.*?\*\*|^二、填充題|^三、非選題|^四、計算題|^五、應用題")
SECTION_HEADER_RE = re.compile(r"^[一二三四五六七八九十]+、")

__all__ = [
    "extract_math_expressions",
    "parse_math_markdown",
]

# ────────────────────────────────────────────────────────────────────────────────
# Public APIs
# ────────────────────────────────────────────────────────────────────────────────

def extract_math_expressions(text: str) -> List[str]:
    """回傳 *依序* 出現的數學式 list，不重複去重。"""
    formulas = []
    # 先抓 block，再抓 inline
    for m in BLOCK_MATH_RE.finditer(text):
        formulas.append(m.group(1).strip())
    for m in INLINE_MATH_RE.finditer(text):
        formulas.append(m.group(1).strip())
    return formulas

# ────────────────────────────────────────────────────────────────────────────────
# Markdown multiple-choice parser (line-wise) for Math exams
# ────────────────────────────────────────────────────────────────────────────────

def _needs_image(text: str) -> bool:
    return any(k in text for k in IMAGE_KEYWORDS)

def _clean_image_paths(text: str, img_idx: int) -> tuple[str, Optional[str]]:
    """清理題目中的圖片路徑，統一格式為 img_XXX.png"""
    if not IMAGE_PATH_RE.search(text) and not _needs_image(text):
        return text, None
        
    img_name = f"img_{img_idx:03d}.png"
    # 移除 Markdown 圖片語法
    text = IMAGE_PATH_RE.sub("", text)
    return text.strip(), img_name

def _is_multiple_choice_question(text: str) -> bool:
    """判斷是否為選擇題"""
    # 檢查是否有答案前綴 (A) (B) 等
    if ANSWER_PREFIX_RE.match(text):
        return True
    # 檢查是否包含選項
    options = OPTION_RE.findall(text)
    return len(options) >= 2

def _extract_answer_from_prefix(text: str) -> Optional[str]:
    """從題目前綴提取答案"""
    match = ANSWER_PREFIX_RE.match(text)
    if match:
        return match.group(1).translate(FW_MAP)
    return None

def _extract_options_from_text(text: str) -> Dict[str, str]:
    """從文本中提取選項"""
    options = {}
    for match in OPTION_RE.finditer(text):
        letter = match.group(1).translate(FW_MAP)
        content = match.group(2).strip()
        # 過濾掉空選項、只有符號的選項或過短的選項
        if content and content != "![]" and len(content) > 1 and not content.isspace():
            # 移除多餘的符號和空白
            content = re.sub(r"^\s*[>＞]+\s*", "", content)
            content = re.sub(r"\s*[>＞]+\s*$", "", content)
            content = content.strip()
            if content and not re.match(r"^[>＞\s]+$", content):
                options[letter] = content
    return options

def _clean_question_text(text: str, options: Dict[str, str]) -> str:
    """清理題目文本，移除答案前綴和選項"""
    # 移除答案前綴
    text = ANSWER_PREFIX_RE.sub("", text)
    
    # 移除題號前綴（包括各種格式）
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r"^[（(]?\d+[）)]?\s*", "", text)
    
    # 移除選項部分
    for letter, content in options.items():
        pattern = f"[（(]{letter}[）)]\\s*{re.escape(content)}"
        text = re.sub(pattern, "", text)
    
    # 移除分數資訊
    text = re.sub(r"每題\s*\d+\s*分", "", text)
    text = re.sub(r"共\s*\d+\s*分", "", text)
    text = re.sub(r"每題\s*\d+\s*分\s*，\s*共\s*\d+\s*分", "", text)
    
    # 移除多餘的符號和格式
    text = re.sub(r">\s*>", "", text)  # 移除 > >
    text = re.sub(r"\\(C\\)|\\(D\\)", "", text)  # 移除轉義的選項
    text = re.sub(r"\s+", " ", text)  # 合併多個空白
    text = re.sub(r"^[\s，。、：；>＞]+", "", text)  # 移除開頭的標點
    text = re.sub(r"[\s，。、：；>＞]+$", "", text)  # 移除結尾的標點
    
    return text.strip()

def _is_valid_question(text: str, options: Dict[str, str]) -> bool:
    """判斷是否為有效題目"""
    # 題目太短
    if len(text) < 10:
        return False
    
    # 選項不足
    if len(options) < 2:
        return False
    
    # 只包含選項字母
    if re.match(r"^[ABCD\s]+$", text):
        return False
    
    # 包含填充題或非選題標記
    if FILL_IN_BLANK_RE.search(text) or SECTION_HEADER_RE.match(text):
        return False
    
    # 包含過多的填充題內容
    if "填充題" in text or "非選題" in text or "計算題" in text:
        return False
    
    # 題目過長（可能包含多題）
    if len(text) > 500:
        return False
    
    return True

def _get_question_hash(text: str) -> str:
    """生成題目的唯一哈希值"""
    # 標準化文本
    normalized = re.sub(r"[\s\u3000，。；：！？()（）\[\]【】「」『』""'']+", "", text)
    normalized = re.sub(r"^\d+", "", normalized)
    normalized = normalized.lower()
    
    # 生成 MD5 哈希
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()

def load_md_content(md_path: str) -> str:
    """載入 MD 檔案內容"""
    with open(md_path, 'r', encoding='utf-8') as f:
        return f.read()

def extract_answer_from_choice_header(text: str) -> Optional[str]:
    """從單選題標頭提取答案，如 '( A )1.' -> 'A'"""
    pattern = r'[（(]\s*([A-D])\s*[）)]\s*\d+\.'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

def extract_question_number(text: str) -> Optional[str]:
    """提取題目編號"""
    # 單選題格式: ( A )1.
    match = re.search(r'[（(]\s*[A-D]\s*[）)]\s*(\d+)\.', text)
    if match:
        return match.group(1)
    
    # 填充題/非選題格式: 1.
    match = re.search(r'^(\d+)\.', text)
    if match:
        return match.group(1)
    
    return None

def extract_options_from_lines(lines: List[str]) -> Optional[Dict[str, str]]:
    """從多行文字中提取選項"""
    options = {}
    
    for line in lines:
        # 匹配選項格式 (A)、(B)、(C)、(D)
        matches = re.finditer(r'[（(]([A-D])[）)]\s*([^（(]*?)(?=[（(][A-D][）)]|$)', line)
        for match in matches:
            option_key = match.group(1)
            option_text = match.group(2).strip()
            if option_text:
                # 清理選項文字
                option_text = re.sub(r'[\u3000\s]+$', '', option_text)  # 移除末尾空白
                option_text = option_text.replace('　', ' ').strip()
                if option_text and len(option_text) > 1:
                    options[option_key] = option_text
    
    return options if len(options) >= 2 else None

def clean_question_text(text: str) -> str:
    """清理題目文字"""
    # 移除答案前綴 ( A )1.
    text = re.sub(r'^[（(]\s*[A-D]\s*[）)]\s*\d+\.\s*', '', text)
    
    # 移除題號前綴 1. 或 1\.
    text = re.sub(r'^\d+\\?\.\s*', '', text)
    
    # 移除選項部分
    text = re.sub(r'[（(][A-D][）)].*$', '', text, flags=re.DOTALL)
    
    # 移除分數資訊
    text = re.sub(r'每題\s*\d+\s*分', '', text)
    text = re.sub(r'共\s*\d+\s*分', '', text)
    
    # 清理空白和標點
    text = re.sub(r'^\s*[，。、：；]+', '', text)
    text = re.sub(r'[，。、：；]+\s*$', '', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_fill_blank_answer(text: str) -> Optional[str]:
    """從填充題中提取答案"""
    # 匹配下劃線包圍的答案: <u>　答案　</u>
    pattern = r'<u>\s*[　\s]*([^<>]+?)[　\s]*</u>'
    match = re.search(pattern, text)
    if match:
        answer = match.group(1).strip()
        return answer if answer else None
    return None

def has_image_reference(text: str) -> bool:
    """檢查是否有圖片引用"""
    image_keywords = ['圖', '附圖', '如圖', '如附圖', '見圖', '![', 'media/image']
    return any(keyword in text for keyword in image_keywords)

def clean_image_references(text: str) -> str:
    """清理圖片引用語法"""
    # 移除 Markdown 圖片語法
    text = re.sub(r'!\[.*?\]\([^)]*\)', '', text)
    # 移除 HTML 圖片標籤（如果有）
    text = re.sub(r'<img[^>]*>', '', text)
    return text.strip()

def is_section_header(text: str) -> Optional[str]:
    """識別區塊標題"""
    # 移除 Markdown 加粗標記和其他格式
    clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    clean_text = clean_text.strip()
    
    headers = [
        r'一、單選題',
        r'二、填充題', 
        r'三、非選題',
        r'四、計算題',
        r'五、應用題'
    ]
    
    for header in headers:
        if re.search(header, clean_text):
            return clean_text
    return None

def parse_multiple_choice_question(lines: List[str], start_idx: int) -> Tuple[Optional[Dict], int]:
    """解析單選題"""
    if start_idx >= len(lines):
        return None, start_idx
    
    current_line = lines[start_idx].strip()
    
    # 檢查是否為單選題格式
    if not re.search(r'[（(]\s*[A-D]\s*[）)]\s*\d+\.', current_line):
        return None, start_idx
    
    # 提取答案和題號
    answer = extract_answer_from_choice_header(current_line)
    question_num = extract_question_number(current_line)
    
    # 收集題目和選項內容
    question_lines = [current_line]
    i = start_idx + 1
    
    # 繼續讀取直到下一題或區塊結束
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # 如果遇到下一題的開頭，停止
        if (re.search(r'[（(]\s*[A-D]\s*[）)]\s*\d+\.', line) or 
            re.search(r'^\d+\.\s', line) or
            is_section_header(line)):
            break
        
        question_lines.append(line)
        i += 1
    
    # 合併所有行
    full_text = ' '.join(question_lines)
    
    # 提取選項
    options = extract_options_from_lines(question_lines)
    
    # 清理題目文字
    question_text = clean_question_text(full_text)
    question_text = clean_image_references(question_text)
    
    if not question_text or not options:
        return None, i
    
    # 檢查圖片引用
    image_path = None
    if has_image_reference(full_text):
        # 簡單的圖片編號生成（將在後續統一處理）
        image_path = f"img_{question_num.zfill(3)}.png" if question_num else "img_001.png"
    
    question_dict = {
        "question_text": question_text,
        "options": options,
        "answer": answer,
        "question_type": "單選題",
        "image_path": image_path,
        "question_number": question_num
    }
    
    return question_dict, i

def parse_fill_blank_question(lines: List[str], start_idx: int) -> Tuple[Optional[Dict], int]:
    """解析填充題"""
    if start_idx >= len(lines):
        return None, start_idx
    
    current_line = lines[start_idx].strip()
    
    # 檢查是否為填充題格式 (數字\. 開頭，非選擇題)
    if not re.match(r'^\d+\\\.\s', current_line) and not re.match(r'^\d+\.\s', current_line):
        return None, start_idx
    
    # 確保不是選擇題格式
    if re.search(r'[（(]\s*[A-D]\s*[）)]', current_line):
        return None, start_idx
    
    # 提取題號
    question_num_match = re.search(r'^(\d+)[\\\.]', current_line)
    question_num = question_num_match.group(1) if question_num_match else None
    
    # 收集題目內容
    question_lines = [current_line]
    i = start_idx + 1
    
    # 繼續讀取直到下一題
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # 如果遇到下一題的開頭，停止
        if (re.match(r'^\d+[\\\.]', line) or 
            re.search(r'[（(]\s*[A-D]\s*[）)]\s*\d+\.', line) or
            is_section_header(line)):
            break
        
        question_lines.append(line)
        i += 1
    
    # 合併所有行
    full_text = ' '.join(question_lines)
    
    # 提取答案
    answer = extract_fill_blank_answer(full_text)
    
    # 清理題目文字
    question_text = clean_question_text(full_text)
    question_text = clean_image_references(question_text)
    
    # 移除答案部分
    question_text = re.sub(r'<u>.*?</u>', '____', question_text)
    
    # 格式化題目的數學表達式
    formatted_question = format_math_for_web(question_text)
    
    if not question_text:
        return None, i
    
    # 檢查圖片引用
    image_path = None
    if has_image_reference(full_text):
        image_path = f"img_{question_num.zfill(3)}.png" if question_num else "img_001.png"
    
    question_dict = {
        "question_text": formatted_question,
        "options": None,
        "answer": answer,
        "question_type": "填充題",
        "image_path": image_path,
        "question_number": question_num
    }
    
    return question_dict, i

def parse_essay_question(lines: List[str], start_idx: int) -> Tuple[Optional[Dict], int]:
    """解析非選題"""
    if start_idx >= len(lines):
        return None, start_idx
    
    current_line = lines[start_idx].strip()
    
    # 檢查是否為非選題格式 (數字\. 開頭，非選擇題)
    if not re.match(r'^\d+\\\.\s', current_line) and not re.match(r'^\d+\.\s', current_line):
        return None, start_idx
    
    # 確保不是選擇題格式
    if re.search(r'[（(]\s*[A-D]\s*[）)]', current_line):
        return None, start_idx
    
    # 提取題號
    question_num_match = re.search(r'^(\d+)[\\\.]', current_line)
    question_num = question_num_match.group(1) if question_num_match else None
    
    # 收集題目內容
    question_lines = [current_line]
    answer_lines = []
    in_answer_section = False
    
    i = start_idx + 1
    
    # 繼續讀取直到下一題
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # 檢查是否進入答案區域
        if line.startswith('答案：') or line.startswith('答：'):
            in_answer_section = True
            answer_lines.append(line)
            i += 1
            continue
        
        # 如果遇到下一題的開頭，停止
        if (re.match(r'^\d+[\\\.]', line) or 
            re.search(r'[（(]\s*[A-D]\s*[）)]\s*\d+\.', line) or
            is_section_header(line)):
            break
        
        if in_answer_section:
            answer_lines.append(line)
        else:
            question_lines.append(line)
        
        i += 1
    
    # 處理題目和答案
    question_text = ' '.join(question_lines)
    answer_text = ' '.join(answer_lines) if answer_lines else None
    
    # 清理題目文字
    question_text = clean_question_text(question_text)
    question_text = clean_image_references(question_text)
    
    # 格式化題目的數學表達式
    formatted_question = format_math_for_web(question_text)
    
    # 清理和格式化答案文字
    formatted_answer = None
    if answer_text:
        answer_text = re.sub(r'^答案：|^答：', '', answer_text).strip()
        formatted_answer = format_math_for_web(answer_text)
    
    if not question_text:
        return None, i
    
    # 檢查圖片引用
    image_path = None
    if has_image_reference(' '.join(question_lines)):
        image_path = f"img_{question_num.zfill(3)}.png" if question_num else "img_001.png"
    
    question_dict = {
        "question_text": formatted_question,
        "options": None,
        "answer": formatted_answer,
        "question_type": "非選題",
        "image_path": image_path,
        "question_number": question_num
    }
    
    return question_dict, i

def parse_math_md(md_path: str) -> List[Dict[str, Any]]:
    """解析數學 MD 檔案中的題目"""
    content = load_md_content(md_path)
    lines = content.split('\n')
    
    questions = []
    current_section = None
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳過空行
        if not line:
            i += 1
            continue
        
        # 檢查區塊標題
        section_header = is_section_header(line)
        if section_header:
            current_section = section_header
            i += 1
            continue
        
        # 跳過表格和其他格式內容
        if line.startswith('<') or line.startswith('|') or line.startswith('**'):
            i += 1
            continue
        
        # 根據當前區塊解析題目
        question_dict = None
        next_i = i
        
        if current_section and '單選題' in current_section:
            question_dict, next_i = parse_multiple_choice_question(lines, i)
        elif current_section and '填充題' in current_section:
            question_dict, next_i = parse_fill_blank_question(lines, i)
        elif current_section and '非選題' in current_section:
            question_dict, next_i = parse_essay_question(lines, i)
        else:
            # 嘗試自動判斷題型
            if re.search(r'[（(]\s*[A-D]\s*[）)]\s*\d+\.', line):
                question_dict, next_i = parse_multiple_choice_question(lines, i)
                if not current_section:
                    current_section = "單選題"
            elif re.match(r'^\d+\.\s', line):
                # 先嘗試填充題，再嘗試非選題
                question_dict, next_i = parse_fill_blank_question(lines, i)
                if not question_dict:
                    question_dict, next_i = parse_essay_question(lines, i)
        
        if question_dict:
            question_dict["section"] = current_section
            questions.append(question_dict)
        
        i = max(next_i, i + 1)  # 防止無限循環
    
    return questions

def parse_math_markdown(md_path: str) -> List[Dict[str, Any]]:
    """主要的數學解析函數 - 兼容舊版本調用"""
    try:
        # 嘗試相對導入
        from .base_parser import standard_question_dict
    except ImportError:
        # 如果相對導入失敗，嘗試直接導入
        try:
            from base_parser import standard_question_dict
        except ImportError:
            # 如果都失敗，使用內建的簡單函數
            def standard_question_dict(question_text, options, answer, file_path="", image_path=None, **kwargs):
                return {
                    "question": question_text,
                    "options": options,
                    "image_path": image_path,
                    "scope": "國中",
                    "grade": "七年級",
                    "subject": "數學",
                    "semester": "111上",
                    "publisher": "翰林",
                    "chapter": "",
                    "answer": answer
                }
    
    try:
        questions = parse_math_md(md_path)
        
        # 使用新的 standard_question_dict 格式化輸出
        formatted_questions = []
        img_counter = 0  # 全局圖片計數器，按照圖片在文件中出現的順序編號
        
        for q in questions:
            # 處理複雜的題目文字格式
            question_text = q["question_text"]
            if isinstance(question_text, dict):
                # 如果是複雜的數學格式，優先取 display_text，然後 latex_text，最後 original_text
                question_text = (question_text.get("display_text") or 
                               question_text.get("latex_text") or 
                               question_text.get("original_text", ""))
            
            # 確保題目文字是字符串
            question_text = str(question_text)
            
            # 處理選項
            options = q.get("options", {})
            if not options:
                options = {}
            
            # 處理答案
            answer = q.get("answer", "")
            if isinstance(answer, dict):
                # 如果是複雜的答案格式，優先取 display_text，然後 latex_text，最後 original_text
                answer = (answer.get("display_text") or 
                         answer.get("latex_text") or 
                         answer.get("original_text", ""))
            
            # 確保答案是字符串
            answer = str(answer)
            
            # 處理圖片路徑 - 使用圖片計數器而非題目編號
            new_image_path = None
            original_image_path = q.get("image_path")
            if original_image_path or has_image_reference(question_text):
                img_counter += 1  # 按照圖片在文件中出現的順序編號
                new_image_path = generate_image_path_for_parser(md_path, str(img_counter), ".png")
            
            formatted_q = standard_question_dict(
                question_text=question_text,
                options=options,
                answer=answer,
                file_path=md_path,
                image_path=new_image_path
            )
            
            formatted_questions.append(formatted_q)
        
        return formatted_questions
        
    except Exception as e:
        print(f"解析數學檔案時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return []

# 向後兼容
def extract_math_expressions(text: str) -> List[str]:
    """提取數學表達式（向後兼容）"""
    # 簡單的 LaTeX 數學表達式提取
    latex_patterns = [
        r'\$\$(.+?)\$\$',  # 塊級數學
        r'\$(.+?)\$',      # 行內數學
    ]
    
    expressions = []
    for pattern in latex_patterns:
        matches = re.finditer(pattern, text, re.DOTALL)
        for match in matches:
            expressions.append(match.group(1).strip())
    
    return expressions 

def convert_math_expressions(text: str) -> str:
    """將數學表達式轉換為 LaTeX 格式"""
    if not text:
        return text
    
    # 保存原始文本
    original_text = text
    
    # 轉換規則字典
    math_conversions = {
        # 絕對值符號 - 修正正則表達式
        r'∣([^∣]+)∣': r'|\1|',
        r'｜([^｜]+)｜': r'|\1|',
        r'\\\|\s*([^|]+)\s*\\\|': r'|\1|',
        
        # 數學運算符號
        r'＋': '+',
        r'－': '-',
        r'＜': '<',
        r'＞': '>',
        r'＝': '=',
        r'×': r'\\times',
        r'÷': r'\\div',
        r'±': r'\\pm',
        r'∓': r'\\mp',
        
        # 分數符號 - 修正正則表達式
        r'(\d+)/(\d+)': r'\\frac{\1}{\2}',
        
        # 指數符號 - 修正正則表達式
        r'(\w+)\^(\w+)': r'\1^{\2}',
        r'(\w+)²': r'\1^2',
        r'(\w+)³': r'\1^3',
        
        # 根號 - 修正正則表達式
        r'√(\w+)': r'\\sqrt{\1}',
        r'∛(\w+)': r'\\sqrt[3]{\1}',
        
        # 希臘字母
        r'α': r'\\alpha',
        r'β': r'\\beta',
        r'γ': r'\\gamma',
        r'δ': r'\\delta',
        r'θ': r'\\theta',
        r'λ': r'\\lambda',
        r'μ': r'\\mu',
        r'π': r'\\pi',
        r'σ': r'\\sigma',
        r'φ': r'\\phi',
        r'ω': r'\\omega',
        
        # 特殊符號
        r'∞': r'\\infty',
        r'∑': r'\\sum',
        r'∏': r'\\prod',
        r'∫': r'\\int',
        r'∂': r'\\partial',
        r'∇': r'\\nabla',
        r'∆': r'\\Delta',
        
        # 集合符號
        r'∈': r'\\in',
        r'∉': r'\\notin',
        r'⊂': r'\\subset',
        r'⊃': r'\\supset',
        r'∩': r'\\cap',
        r'∪': r'\\cup',
        r'∅': r'\\emptyset',
        
        # 邏輯符號
        r'∧': r'\\land',
        r'∨': r'\\lor',
        r'¬': r'\\lnot',
        r'→': r'\\rightarrow',
        r'↔': r'\\leftrightarrow',
        r'∀': r'\\forall',
        r'∃': r'\\exists',
        
        # 幾何符號
        r'∠': r'\\angle',
        r'△': r'\\triangle',
        r'□': r'\\square',
        r'○': r'\\circ',
        r'⊥': r'\\perp',
        r'∥': r'\\parallel',
        r'≅': r'\\cong',
        r'∼': r'\\sim',
        
        # 不等式符號
        r'≤': r'\\leq',
        r'≥': r'\\geq',
        r'≠': r'\\neq',
        r'≈': r'\\approx',
        r'≡': r'\\equiv',
        
        # 省略號
        r'…': r'\\ldots',
        r'⋯': r'\\cdots',
        
        # 溫度符號
        r'℃': r'^{\\circ}\\text{C}',
        r'℉': r'^{\\circ}\\text{F}',
    }
    
    # 應用轉換規則
    for pattern, replacement in math_conversions.items():
        text = re.sub(pattern, replacement, text)
    
    # 處理斜體變數 (*a* -> $a$)
    text = re.sub(r'\*([a-zA-Z])\*', r'$\1$', text)
    
    # 處理數學表達式中的空格
    text = re.sub(r'\s*([<>=])\s*', r' \1 ', text)
    
    # 簡化數學符號處理 - 不要過度包裝
    # 只在確實需要時才包裝為 LaTeX
    
    return text

def format_math_for_web(text: str) -> Dict[str, Any]:
    """格式化數學表達式以供網頁顯示"""
    # 提取數學表達式
    math_expressions = extract_math_expressions(text)
    
    # 轉換為 LaTeX 格式
    latex_text = convert_math_expressions(text)
    
    # 檢查是否需要 MathJax 渲染
    needs_mathjax = bool(math_expressions) or '\\' in latex_text or '$' in latex_text
    
    return {
        'original_text': text,
        'latex_text': latex_text,
        'math_expressions': math_expressions,
        'needs_mathjax': needs_mathjax,
        'display_text': latex_text  # 前端顯示用的文本
    } 