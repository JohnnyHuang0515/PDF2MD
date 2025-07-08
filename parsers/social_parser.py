"""social_parser.py  -- v3
Parser for junior-high Social Studies Word exams → JSON (只保留純文字單選題)。

### 變更（v3）
* **添加 file_path 參數支援**：支援傳遞檔案路徑用於提取檔案資訊
* **使用統一格式**：使用 standard_question_dict 統一輸出格式
* **跳過含圖 / 表題目**：若題幹文字含「圖」「表」「附圖」「附表」等關鍵詞，直接略過。
* **跳過選項不完整或缺文字的題目**：若選項不足 A–D 或出現空字串，整題略過。

輸出欄位結構：
```json
{
  "question": "【社會-七年級-翰林】當河流下游的沙洲愈來愈寬廣時，代表河水的流速有何變化？",
  "options": {"A": "加快", "B": "減慢", "C": "不變", "D": "忽快忽慢"},
  "answer": "B",
  "image_path": null,
  "scope": "國中",
  "grade": "七年級",
  "subject": "社會",
  "semester": "113上",
  "publisher": "翰林",
  "chapter": "Ch1"
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
# Regex
# ────────────────────────────────────────────────────────────────────────────────
# 單選題格式：(　A　) 1.　題目內容
QUESTION_RE = re.compile(r"^[（(][\s　]*([Ａ-ＤABCD])[\s　]*[）)]\s*(\d+)[\.\s　]*(.*)")
# 題組格式：(　B　)(１) 題目內容 
GROUP_QUESTION_RE = re.compile(r"^[（(][\s　]*([Ａ-ＤABCD])[\s　]*[）)]\s*[（(]([１２３４５６７８９０\d]+)[）)]\s*(.*)")
# 題組引導：⊙ ...請問：
GROUP_INTRO_RE = re.compile(r"^[⊙○●]\s*(.*?)\s*請問[:：]?\s*$")
OPTION_INLINE_RE = re.compile(r"[（(]([Ａ-ＤABCD])[）)]\s*([^（()]+)")
OPTION_SINGLE_RE = re.compile(r"^[（(]([Ａ-ＤABCD])[）)]\s*(.+)")
SECTION_CHOICE = re.compile(r"^\*\*[一二三四五六七八九十]、.*[單选選擇]題")
SECTION_GROUP = re.compile(r"^\*\*[一二三四五六七八九十]、.*題組")
SECTION_END = re.compile(r"^[一二三四五六七八九十]、.*")
# 修正：只匹配真正的題目行（有題號），不匹配選項行
QUESTION_START = re.compile(r"^[（(][\s　]*[Ａ-ＤABCD][\s　]*[）)]\s*\d+[\.\s　]")

FW_MAP = str.maketrans("ＡＢＣＤ", "ABCD")
IDEOSP = "　"
BLANK_RE = re.compile(rf"[{IDEOSP} \t]{{2,}}")
SKIP_KEYWORDS = ("圖", "表", "附圖", "附表")
IMAGE_KEYWORDS = ("圖", "附圖", "如圖")

# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return BLANK_RE.sub("____", text.rstrip())

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

def _needs_image(text: str) -> bool:
    return any(k in text for k in IMAGE_KEYWORDS)

def _extract_inline_options(text: str, opts: Dict[str, str]):
    for m in OPTION_INLINE_RE.finditer(text):
        opts[m.group(1).translate(FW_MAP)] = m.group(2).strip()


def _collect_options(paragraphs, idx: int) -> tuple[Dict[str, str], int]:
    opts: Dict[str, str] = {}
    i, n = idx, len(paragraphs)
    first = True
    while i < n and len(opts) < 4:
        line = paragraphs[i].text.replace("\t", " ").rstrip()
        if not first and QUESTION_START.match(line):
            break
        first = False
        _extract_inline_options(line, opts)
        m_single = OPTION_SINGLE_RE.match(line.strip())
        if m_single:
            letter = m_single.group(1).translate(FW_MAP)
            if letter not in opts:
                opts[letter] = m_single.group(2).strip()
        i += 1
    return opts, i

# ────────────────────────────────────────────────────────────────────────────────
# Core parser
# ────────────────────────────────────────────────────────────────────────────────

def parse_social(paragraphs, file_path: str = "") -> List[dict]:
    """解析社會科考卷：歷史、地理、公民"""
    from .base_parser import standard_question_dict
    
    res: List[dict] = []
    current_section = None
    i, n = 0, len(paragraphs)
    img_idx = 0
    current_group_intro = None
    group_id = 0

    while i < n:
        line_raw = paragraphs[i].text.rstrip() if hasattr(paragraphs[i], 'text') else str(paragraphs[i]).rstrip()
        line = line_raw.strip()

        # 檢查章節標題
        if SECTION_CHOICE.match(line):
            current_section = "choice"
            current_group_intro = None
            i += 1
            continue
        elif SECTION_GROUP.match(line):
            current_section = "group"
            current_group_intro = None
            i += 1
            continue
        elif current_section and SECTION_END.match(line) and not (SECTION_CHOICE.match(line) or SECTION_GROUP.match(line)):
            current_section = None
            i += 1
            continue
            
        if not current_section:
            i += 1
            continue

        # 檢查題組引導
        group_intro_match = GROUP_INTRO_RE.match(line)
        if group_intro_match and current_section == "group":
            current_group_intro = group_intro_match.group(1).strip()
            group_id += 1
            i += 1
            continue

        # 處理單選題：(　A　) 1. 題目內容
        question_match = QUESTION_RE.match(line)
        if question_match:
            ans_raw, _num, rest = question_match.groups()
            answer = ans_raw.translate(FW_MAP).upper()
            
            # 清理題目文字，移除選項部分
            first_opt = OPTION_INLINE_RE.search(rest)
            q_text_part = rest[:first_opt.start()] if first_opt else rest
            question_str = _clean_question_text(_normalize(q_text_part))

            # 跳過含圖表的題目
            if any(kw in question_str for kw in ("圖", "表", "附圖", "附表")):
                i += 1
                continue

            opts, new_i = _collect_options(paragraphs, i)
            # 跳過選項不完整的題目
            if len(opts) != 4 or any(not v.strip() for v in opts.values()):
                i = new_i
                continue

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

        # 處理題組題：(　B　)(１) 題目內容
        group_question_match = GROUP_QUESTION_RE.match(line)
        if group_question_match and current_section == "group":
            ans_raw, sub_num, rest = group_question_match.groups()
            answer = ans_raw.translate(FW_MAP).upper()
            
            # 清理題目文字，移除選項部分
            first_opt = OPTION_INLINE_RE.search(rest)
            q_text_part = rest[:first_opt.start()] if first_opt else rest
            question_str = _clean_question_text(_normalize(q_text_part))

            # 跳過含圖表的題目
            if any(kw in question_str for kw in ("圖", "表", "附圖", "附表")):
                i += 1
                continue

            opts, new_i = _collect_options(paragraphs, i)
            # 跳過選項不完整的題目
            if len(opts) != 4 or any(not v.strip() for v in opts.values()):
                i = new_i
                continue

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

        i += 1

    return res

# ────────────────────────────────────────────────────────────────────────────────
# Interface
# ────────────────────────────────────────────────────────────────────────────────

def convert_to_json(docx_path: str, out_path: Optional[str] = None):
    doc = Document(docx_path)
    data = parse_social(doc.paragraphs, docx_path)
    out_path = out_path or str(Path(docx_path).with_suffix(".json"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Convert Social Studies exam .docx to JSON—文字單選題")
    ap.add_argument("docx", help="input .docx")
    ap.add_argument("json", nargs="?", help="output .json (optional)")
    args = ap.parse_args()
    path = convert_to_json(args.docx, args.json)
    print(f"✅ {args.docx} → {path}")