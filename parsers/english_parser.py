"""english_parser.py  -- v8
國中英文段考 (教師版) .docx → JSON list[dict]

🚫 **題組題已完全移除**
此版本僅擷取「三、單選題」區的 4 選 1 題目。

規則回到你先前確認 OK 的設定：
* `question` 去掉題號，只保留題幹文字。
* 連續空白 (含全形空格) → 固定 4 條底線 `____`。
* `options` 必須含 4 個鍵 `A B C D`，缺少即跳過。

輸出欄位：
```json
{
  "type": "單選題",
  "question": "Leo is more ____ than his brother.",
  "options": {"A": "pretty", "B": "successful", "C": "thinner", "D": "tall"},
  "answer": "B"
}
```
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import List, Dict, Optional

from docx import Document
import sys
sys.path.append(str(Path(__file__).parent.parent))
from utils.image_naming import generate_image_path_for_parser

# ────────────────────────────────────────────────────────────────────────────────
# Regex 池
# ────────────────────────────────────────────────────────────────────────────────
QUESTION_RE = re.compile(r"^[（(]\s*([Ａ-ＤABCD])\s*[）)]\s*(\d+)\.\s*(.*)")  # ( Ｂ )1. …
READING_Q_RE = re.compile(r"^[（(]\s*[）)]\s*[（(](\d+)[）)]\s*(.*)")      # ( ) (1) …
OPTION_INLINE_RE = re.compile(r"[（(]([Ａ-ＤABCD])[）)]\s*([^（()]+)")     # (A) xxx inline  
OPTION_SINGLE_RE = re.compile(r"^[（(]([Ａ-ＤABCD])[）)]\s*(.+)")        # (A) xxx on own line
SECTION_VOCAB = re.compile(r"^\*\*一、.*字彙選擇")                    # **一、字彙選擇：每題2分，共40分**
SECTION_GRAMMAR = re.compile(r"^\*\*二、.*文法")                        # **二、文法：每題2分，共40分**
SECTION_READING = re.compile(r"^\*\*三、.*閱讀測驗")                    # **三、閱讀測驗：每題2分，共20分**
QUESTION_START_MARK = re.compile(r"^[（(]\s*[Ａ-ＤABCD]?\s*[）)]\s*[\(\d]")  # ( Ｃ )12. 或 ( ) (1)

FW_MAP = str.maketrans("ＡＢＣＤ", "ABCD")
IDEOSP = "　"
BLANK_RE = re.compile(rf"[{IDEOSP} \t]{{2,}}")  # 連續半形/全形空白≥2 → ____
IMAGE_KEYWORDS = ("figure", "picture", "圖", "附圖", "如圖")

# ────────────────────────────────────────────────────────────────────────────────
# 工具函式
# ────────────────────────────────────────────────────────────────────────────────

def _normalize_blank(text: str) -> str:
    return BLANK_RE.sub("____", text)

def _clean_question_text(text: str) -> str:
    """清理題目文本，移除分數信息和其他不必要的內容"""
    # 移除分數資訊
    text = re.sub(r"每題\s*\d+\s*分", "", text)
    text = re.sub(r"共\s*\d+\s*分", "", text)
    text = re.sub(r"每題\s*\d+\s*分\s*，\s*共\s*\d+\s*分", "", text)
    
    # 移除多餘的標點符號和空白
    text = re.sub(r"^[\s，。、：；]+", "", text)
    text = re.sub(r"[\s，。、：；]+$", "", text)
    
    return text.strip()

def _extract_inline_options(text: str, opt: Dict[str, str]):
    for m in OPTION_INLINE_RE.finditer(text):
        letter = m.group(1).translate(FW_MAP)  # 轉換為半形
        opt[letter] = m.group(2).strip()


def _collect_options(paragraphs, start_idx: int) -> tuple[Dict[str, str], int]:
    """從 start_idx 開始累積直到取得 4 個選項或遇下一題。"""
    opts: Dict[str, str] = {}
    i, n = start_idx, len(paragraphs)
    
    # 檢查當前行是否包含選項
    current_line = paragraphs[i].text.replace("\t", " ").rstrip()
    _extract_inline_options(current_line, opts)
    
    # 檢查後續行
    i += 1
    while i < n and len(opts) < 4:
        line = paragraphs[i].text.replace("\t", " ").rstrip()
        
        # 如果遇到新題目，停止
        if QUESTION_START_MARK.match(line.strip()):
            break
            
        # 提取行內選項
        _extract_inline_options(line, opts)
        
        # 檢查獨立行選項
        m_single = OPTION_SINGLE_RE.match(line.strip())
        if m_single:
            letter = m_single.group(1).translate(FW_MAP)
            if letter not in opts:
                opts[letter] = m_single.group(2).strip()
        
        i += 1
    
    return opts, i

def _needs_image(text: str) -> bool:
    return any(kw.lower() in text.lower() for kw in IMAGE_KEYWORDS)

# ────────────────────────────────────────────────────────────────────────────────
# 主解析
# ────────────────────────────────────────────────────────────────────────────────

def parse_english(paragraphs, file_path: str = "") -> List[dict]:
    """解析英文考卷：字彙選擇、文法、閱讀測驗。"""
    from .base_parser import standard_question_dict
    
    res: List[dict] = []
    current_section = None
    i, n = 0, len(paragraphs)
    img_idx = 0
    current_passage = None

    while i < n:
        line_raw = paragraphs[i].text.rstrip() if hasattr(paragraphs[i], 'text') else str(paragraphs[i]).rstrip()
        line = line_raw.strip()

        # 檢查章節標題
        if SECTION_VOCAB.match(line):
            current_section = "vocab"
            i += 1
            continue
        elif SECTION_GRAMMAR.match(line):
            current_section = "grammar"  
            i += 1
            continue
        elif SECTION_READING.match(line):
            current_section = "reading"
            current_passage = []
            i += 1
            continue

        if not current_section:
            i += 1
            continue

        # 處理一般題目：( B )1. 
        q_match = QUESTION_RE.match(line)
        if q_match:
            ans_fw, _num, rest = q_match.groups()
            answer = ans_fw.translate(FW_MAP)
            
            # 清理題目文字，移除選項部分
            question_text = rest
            first_opt = OPTION_INLINE_RE.search(rest)
            if first_opt:
                question_text = rest[:first_opt.start()]
            question_str = _clean_question_text(_normalize_blank(question_text.rstrip()))

            if question_str:  # 確保題目不為空
                opts, new_i = _collect_options(paragraphs, i)
                if len(opts) == 4:
                    # 處理圖片
                    if _needs_image(question_str):
                        img_idx += 1
                        img_name = generate_image_path_for_parser(file_path, str(img_idx), ".png")
                    else:
                        img_name = None
                        
                    # 使用新的標準格式
                    formatted_q = standard_question_dict(
                        question_text=question_str,
                        options={k: opts[k] for k in sorted(opts)},
                        answer=answer,
                        file_path=file_path,
                        image_path=img_name
                    )
                    res.append(formatted_q)
                i = new_i
                continue

        # 處理閱讀測驗題目：( ) (1)
        reading_match = READING_Q_RE.match(line)
        if reading_match and current_section == "reading":
            _num, rest = reading_match.groups()
            
            # 清理題目文字
            question_text = rest
            first_opt = OPTION_INLINE_RE.search(rest)
            if first_opt:
                question_text = rest[:first_opt.start()]
            question_str = _clean_question_text(_normalize_blank(question_text.rstrip()))

            if question_str:  # 確保題目不為空
                opts, new_i = _collect_options(paragraphs, i)
                if len(opts) == 4:
                    # 處理圖片
                    if _needs_image(question_str):
                        img_idx += 1
                        img_name = generate_image_path_for_parser(file_path, str(img_idx), ".png")
                    else:
                        img_name = None
                        
                    # 使用新的標準格式
                    formatted_q = standard_question_dict(
                        question_text=question_str,
                        options={k: opts[k] for k in sorted(opts)},
                        answer="",  # 閱讀測驗題目可能沒有明確答案
                        file_path=file_path,
                        image_path=img_name
                    )
                    res.append(formatted_q)
                i = new_i
                continue

        # 收集閱讀文章內容
        if current_section == "reading" and not (q_match or reading_match):
            if current_passage is not None:
                current_passage.append(line)

        i += 1

    return res

# ────────────────────────────────────────────────────────────────────────────────
# CLI & 呼叫端
# ────────────────────────────────────────────────────────────────────────────────

def convert_to_json(docx_path: str, out_path: Optional[str] = None):
    doc = Document(docx_path)
    data = parse_english(doc.paragraphs, docx_path)
    if out_path is None:
        out_path = str(Path(docx_path).with_suffix(".json"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Convert English exam .docx (teacher ver.) to JSON (單選題 only)")
    ap.add_argument("docx", help="input .docx")
    ap.add_argument("json", nargs="?", help="output .json (optional)")
    args = ap.parse_args()
    outp = convert_to_json(args.docx, args.json)
    print(f"✅ {args.docx} → {outp}")
