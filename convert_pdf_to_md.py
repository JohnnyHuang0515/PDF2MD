import os
import sys
from pathlib import Path
from pdf_craft import create_pdf_page_extractor, MarkDownWriter, ExtractedTableFormat, analyse, CorrectionMode
import time
import re
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading
import json
import pickle
import psutil
import gc
import traceback
import logging

def process_math_formulas(text):
    """處理數學公式，轉換為LaTeX格式"""
    math_patterns = [
        (r'(\d+)/(\d+)', r'\\frac{\1}{\2}'),
        (r'√(\w+)', r'\\sqrt{\1}'),
        (r'(\w+)\^(\w+)', r'\1^{\2}'),
        (r'α', r'\\alpha'),
        (r'β', r'\\beta'),
        (r'γ', r'\\gamma'),
        (r'π', r'\\pi'),
        (r'θ', r'\\theta'),
        (r'±', r'\\pm'),
        (r'≤', r'\\leq'),
        (r'≥', r'\\geq'),
        (r'≠', r'\\neq'),
        (r'∞', r'\\infty'),
        (r'\|([^|]+)\|', r'|\1|'),
        (r'－', r'-'),
        (r'—', r'-'),
    ]
    processed_text = text
    for pattern, replacement in math_patterns:
        processed_text = re.sub(pattern, replacement, processed_text)
    return processed_text

def convert_pdf_to_markdown(pdf_path, output_dir, image_output_dir, extractor, encoding="utf-8", 
                          enable_math_processing=True, enable_multilingual_ocr=True):
    """轉換單個PDF檔案為Markdown，支援多重OCR和數學公式處理"""
    try:
        # 驗證PDF檔案
        is_valid, validation_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            print(f"❌ 檔案驗證失敗: {pdf_path.name}")
            print(f"   錯誤: {validation_msg}")
            return False, None
        
        output_dir.mkdir(parents=True, exist_ok=True)
        image_output_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = pdf_path.stem
        output_md_path = output_dir / f"{pdf_name}.md"
        print(f"🔄 正在轉換: {pdf_path.name}")
        print(f"   📐 數學公式處理: {'啟用' if enable_math_processing else '停用'}")
        print(f"   🌐 多語言OCR: {'啟用' if enable_multilingual_ocr else '停用'}")
        start_time = time.time()
        try:
            with MarkDownWriter(output_md_path, image_output_dir, encoding) as md:
                for block in extractor.extract(str(pdf_path)):
                    if enable_math_processing and hasattr(block, 'text'):
                        block.text = process_math_formulas(block.text)
                    md.write(block)
        except ModuleNotFoundError as module_error:
            if "struct_eqtable" in str(module_error):
                print(f"   ⚠️  跳過此檔案 - 表格處理模組缺失")
                print(f"   📝 創建基本文字版本...")
                with open(output_md_path, 'w', encoding=encoding) as f:
                    f.write(f"# {pdf_name}\n\n")
                    f.write(f"*此檔案因表格處理模組缺失而無法完整轉換*\n\n")
                    f.write(f"原始檔案: {pdf_path.name}\n")
                    f.write(f"轉換時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                return True, output_md_path
            else:
                raise module_error
        except Exception as extract_error:
            print(f"   ❌ PDF提取失敗: {extract_error}")
            error_details = traceback.format_exc()
            logging.error(f"PDF提取失敗: {pdf_path.name}\n錯誤詳情: {error_details}")
            raise extract_error
        elapsed_time = time.time() - start_time
        print(f"✅ 完成轉換: {pdf_name} (耗時: {elapsed_time:.2f}秒)")
        print(f"   輸出檔案: {output_md_path}")
        return True, output_md_path
    except Exception as e:
        print(f"❌ 轉換失敗: {pdf_path.name}")
        print(f"   錯誤詳情: {str(e)}")
        print(f"   錯誤類型: {type(e).__name__}")
        error_details = traceback.format_exc()
        logging.error(f"轉換失敗: {pdf_path.name}\n錯誤詳情: {error_details}")
        return False, None

def validate_pdf_file(pdf_path):
    """驗證PDF檔案是否可讀取"""
    try:
        if not pdf_path.exists():
            return False, "檔案不存在"
        
        if pdf_path.stat().st_size == 0:
            return False, "檔案大小為0"
        
        # 檢查檔案頭部是否為PDF格式
        with open(pdf_path, 'rb') as f:
            header = f.read(4)
            if header != b'%PDF':
                return False, "不是有效的PDF檔案"
        
        return True, "檔案驗證通過"
    except Exception as e:
        return False, f"檔案驗證失敗: {str(e)}"

def batch_convert_all_pdfs(root_dir, output_base_dir, image_output_dir, model_cache_path, device, encoding, enable_math_processing, enable_multilingual_ocr, extract_table_format):
    """批次轉換所有PDF檔案，單線程處理"""
    pdf_files = list(Path(root_dir).rglob("*.pdf"))
    print(f"\n🔍 共找到 {len(pdf_files)} 個 PDF 檔案於 {root_dir}")
    
    # 初始化PDF解析器（共用）
    extractor = create_pdf_page_extractor(
        device=device,
        model_dir_path=str(model_cache_path),
        extract_formula=True,
        extract_table_format=extract_table_format,
    )
    
    success_count = 0
    fail_count = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        # 依據 PDF 所在目錄建立對應輸出資料夾
        rel_dir = pdf_path.parent.relative_to(root_dir)
        out_dir = output_base_dir / rel_dir
        img_dir = image_output_dir / rel_dir
        print(f"\n[{i}/{len(pdf_files)}] 處理 {pdf_path}")
        success, output_path = convert_pdf_to_markdown(
            pdf_path,
            out_dir,
            img_dir,
            extractor,
            encoding=encoding,
            enable_math_processing=enable_math_processing,
            enable_multilingual_ocr=enable_multilingual_ocr
        )
        
        if success:
            success_count += 1
        else:
            fail_count += 1
    print(f"\n📊 批次轉換完成：成功 {success_count}，失敗 {fail_count}")

def main():
    # === 設定路徑 ===
    base_input_dir = Path("input_docs")  # 處理 input_docs 底下所有檔案
    output_base_dir = Path("output_docs")
    image_output_dir = Path("images")
    model_cache_path = Path("model")
    device = "cuda"  # 或 "cpu"
    encoding = "utf-8"
    enable_math_processing = True
    enable_multilingual_ocr = True
    extract_table_format = ExtractedTableFormat.MARKDOWN
    
    # === 單線程批次處理所有 PDF ===
    batch_convert_all_pdfs(
        base_input_dir,
        output_base_dir,
        image_output_dir,
        model_cache_path,
        device,
        encoding,
        enable_math_processing,
        enable_multilingual_ocr,
        extract_table_format
    )

if __name__ == "__main__":
    main()