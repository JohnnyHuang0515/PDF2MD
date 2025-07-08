# chinese_parser_longpassage.py
import re
from typing import List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.image_naming import generate_image_path_for_parser

ANS_MAP = str.maketrans("ＡＢＣＤ", "ABCD")
LONG_LIMIT = 60               # 幾個字以上視為「長段落」
IMAGE_KEYWORDS = ("圖", "附圖", "如圖")

def _answer(text):
    # 匹配格式：( Ｂ )1. 或 (Ｂ)1. 
    m = re.match(r"^[（(]\s*([Ａ-ＤABCD])\s*[）)]\s*\d+", text)
    return m.group(1).translate(ANS_MAP) if m else None

def _options(lines):
    d = {}
    for ln in lines:
        # 匹配全形和半形括號及字母：(Ａ)內容 或 (A)內容
        for m in re.finditer(r"[（(]([Ａ-ＤABCD])[）)]([^（()）]+)", ln):
            letter = m.group(1).translate(ANS_MAP)  # 轉換為半形
            d[letter] = m.group(2).strip()
    return d if len(d) == 4 else None

def _clean(txt):
    # 移除答案標記：( Ｄ )1. 
    txt = re.sub(r"^[（(]\s*[Ａ-ＤABCD]\s*[）)]\s*\d+[.、]\s*", "", txt)
    # 移除可能的題號：1. 
    txt = re.sub(r"^(\d+[.、])\s*", "", txt)
    # 移除答案部分
    txt = re.sub(r"答：?[【\(（][^】)）]+[】)）]", "", txt)
    
    # 移除分數資訊
    txt = re.sub(r"每題\s*\d+\s*分", "", txt)
    txt = re.sub(r"共\s*\d+\s*分", "", txt)
    txt = re.sub(r"每題\s*\d+\s*分\s*，\s*共\s*\d+\s*分", "", txt)
    
    # 移除多餘的標點符號和空白
    txt = re.sub(r"^[\s，。、：；\u3000]+", "", txt)
    txt = re.sub(r"[\s，。、：；\u3000]+$", "", txt)
    
    return txt.strip()

def _is_q(text):
    # 匹配單選題格式：( Ｂ )1. 或 (Ｂ)1. 
    # 以及其他題型格式：1. 
    return bool(re.match(r"^[（(]\s*[Ａ-ＤABCD]\s*[）)]\s*\d+[.、]", text)) or \
           bool(re.match(r"^\d+[.、]", text))

def _needs_image(text: str) -> bool:
    """Return True if question references an image."""
    return any(kw in text for kw in IMAGE_KEYWORDS)

def parse_chinese(paragraphs, file_path: str = "") -> List[dict]:
    """解析中文考卷主函數"""
    from .base_parser import standard_question_dict
    
    res = []
    i, n, gid = 0, len(paragraphs), 0
    current_intro = []
    img_idx = 0

    def flush_intro():
        nonlocal current_intro, gid
        if current_intro:
            gid += 1
            intro_text = "\n".join(current_intro).rstrip()
            current_intro = []
            return intro_text
        return None

    while i < n:
        raw = paragraphs[i].text.rstrip() if hasattr(paragraphs[i], 'text') else str(paragraphs[i]).rstrip()
        txt = raw.strip()

        if _is_q(txt):                # 遇到題號
            intro_text = flush_intro()  # 若有文章先出清
            # 收集選項
            look, j = [], i
            # 首先檢查當前行是否包含選項
            if re.search(r"[（(][Ａ-ＤABCD][）)]", txt):
                look.append(txt)
            # 然後檢查後續行
            j = i + 1
            while j < n and j < i + 5:  # 最多檢查後續5行
                line_text = paragraphs[j].text.strip() if hasattr(paragraphs[j], 'text') else str(paragraphs[j]).strip()
                if re.search(r"[（(][Ａ-ＤABCD][）)]", line_text):
                    look.append(line_text)
                elif line_text and not re.match(r"^[（(]\s*[Ａ-ＤABCD]\s*[）)]\s*\d+[.、]", line_text):
                    # 如果不是空行且不是新題目，也加入（可能是選項的延續）
                    look.append(line_text)
                else:
                    break
                j += 1
            opts = _options(look)
            if opts:                  # 確定是四選項題
                # 分離題目和選項，只保留題目部分
                question_text = txt
                # 移除選項部分，只保留題目
                question_text = re.sub(r"[（(][Ａ-ＤABCD][）)][^（()]*", "", question_text)
                question_text = _clean(question_text)
                
                # ——— 圖片對應 ———
                if _needs_image(question_text):
                    img_idx += 1
                    img_name = generate_image_path_for_parser(file_path, str(img_idx), ".png")
                else:
                    img_name = None
                    
                # 使用新的標準格式
                formatted_q = standard_question_dict(
                    question_text=question_text,
                    options=opts,
                    answer=_answer(txt),
                    file_path=file_path,
                    image_path=img_name
                )
                res.append(formatted_q)
            i = j
        else:
            # 非題號 ⇒ 累積成文章段
            if txt or raw == "":
                current_intro.append(raw)
            i += 1

    return res
