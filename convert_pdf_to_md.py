import os
import sys
from pathlib import Path
from pdf_craft import create_pdf_page_extractor, MarkDownWriter, ExtractedTableFormat, analyse, CorrectionMode
import time
import re
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading

def process_math_formulas(text):
    """處理數學公式，轉換為LaTeX格式"""
    # 識別常見的數學符號和表達式
    math_patterns = [
        # 分數
        (r'(\d+)/(\d+)', r'\\frac{\1}{\2}'),
        # 平方根
        (r'√(\w+)', r'\\sqrt{\1}'),
        # 指數
        (r'(\w+)\^(\w+)', r'\1^{\2}'),
        # 希臘字母
        (r'α', r'\\alpha'),
        (r'β', r'\\beta'),
        (r'γ', r'\\gamma'),
        (r'π', r'\\pi'),
        (r'θ', r'\\theta'),
        # 數學運算符
        (r'±', r'\\pm'),
        (r'≤', r'\\leq'),
        (r'≥', r'\\geq'),
        (r'≠', r'\\neq'),
        (r'∞', r'\\infty'),
        # 絕對值
        (r'\|([^|]+)\|', r'|\1|'),
        # 負號
        (r'－', r'-'),  # 全形負號轉半形
        (r'—', r'-'),   # 破折號轉負號
    ]
    
    processed_text = text
    for pattern, replacement in math_patterns:
        processed_text = re.sub(pattern, replacement, processed_text)
    
    return processed_text

def convert_pdf_to_markdown(pdf_path, output_dir, image_output_dir, extractor, encoding="utf-8", 
                          enable_math_processing=True, enable_multilingual_ocr=True):
    """轉換單個PDF檔案為Markdown，支援多重OCR和數學公式處理"""
    try:
        # 建立輸出目錄
        output_dir.mkdir(parents=True, exist_ok=True)
        image_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成輸出檔案名稱
        pdf_name = pdf_path.stem
        output_md_path = output_dir / f"{pdf_name}.md"
        
        print(f"🔄 正在轉換: {pdf_path.name}")
        print(f"   📐 數學公式處理: {'啟用' if enable_math_processing else '停用'}")
        print(f"   🌐 多語言OCR: {'啟用' if enable_multilingual_ocr else '停用'}")
        start_time = time.time()
        
        # 直接轉換PDF為Markdown
        with MarkDownWriter(output_md_path, image_output_dir, encoding) as md:
            for block in extractor.extract(str(pdf_path)):
                if enable_math_processing and hasattr(block, 'text'):
                    block.text = process_math_formulas(block.text)
                
                # 寫入區塊
                md.write(block)
        
        elapsed_time = time.time() - start_time
        print(f"✅ 完成轉換: {pdf_name} (耗時: {elapsed_time:.2f}秒)")
        print(f"   輸出檔案: {output_md_path}")
        
        return True, output_md_path
        
    except Exception as e:
        print(f"❌ 轉換失敗: {pdf_path.name} - {e}")
        return False, None

def process_subject(subject, base_input_dir, output_base_dir, image_output_dir, model_cache_path, 
                   device, encoding, enable_math_processing, enable_multilingual_ocr, extract_table_format):
    """處理單個科目的所有PDF檔案"""
    print(f"\n{'='*20} 處理 {subject} 科目 {'='*20}")
    
    subject_dir = base_input_dir / subject
    if not subject_dir.exists():
        print(f"❌ 科目目錄不存在: {subject_dir}")
        return subject, 0, 0
        
    subject_pdfs = list(subject_dir.glob("*.pdf"))
    if not subject_pdfs:
        print(f"❌ 未找到 {subject} 科目的PDF檔案")
        return subject, 0, 0
        
    print(f"📚 {subject}: 找到 {len(subject_pdfs)} 個PDF檔案")
    
    # 為科目建立輸出目錄
    subject_output_dir = output_base_dir / subject
    subject_image_dir = image_output_dir / subject
    
    # 初始化PDF解析器（每個進程獨立）
    extractor = create_pdf_page_extractor(
        device=device,
        model_dir_path=str(model_cache_path),
        extract_formula=True,
        extract_table_format=extract_table_format,
    )
    
    if not extractor:
        print(f"❌ {subject} PDF解析器初始化失敗")
        return subject, 0, len(subject_pdfs)
    
    subject_successful = 0
    subject_failed = 0
    
    for i, pdf_path in enumerate(subject_pdfs, 1):
        print(f"\n[{i}/{len(subject_pdfs)}] 處理 {subject} 檔案...")
        
        success, output_path = convert_pdf_to_markdown(
            pdf_path, 
            subject_output_dir, 
            subject_image_dir, 
            extractor, 
            encoding,
            enable_math_processing=enable_math_processing,
            enable_multilingual_ocr=enable_multilingual_ocr
        )
        
        if success:
            subject_successful += 1
        else:
            subject_failed += 1
    
    # 科目完成報告
    print(f"\n📊 {subject} 科目完成報告:")
    print(f"   ✅ 成功: {subject_successful} 個檔案")
    print(f"   ❌ 失敗: {subject_failed} 個檔案")
    print(f"   📁 輸出目錄: {subject_output_dir}")
    
    return subject, subject_successful, subject_failed

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
    # === 設定參數 ===
    device = "cpu"  # 或 "cuda"
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