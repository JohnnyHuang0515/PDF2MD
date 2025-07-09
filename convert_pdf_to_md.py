import os
import sys
from pathlib import Path
<<<<<<< HEAD
from pdf_craft import create_pdf_page_extractor, MarkDownWriter, ExtractedTableFormat
=======
from pdf_craft import create_pdf_page_extractor, MarkDownWriter, ExtractedTableFormat, analyse, CorrectionMode
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
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

<<<<<<< HEAD
# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('conversion.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def detect_gpu():
    """檢測可用的GPU設備"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
            print(f"🚀 檢測到 {gpu_count} 個GPU設備")
            print(f"   GPU 0: {gpu_name}")
            print(f"   GPU記憶體: {gpu_memory:.1f} GB")
            print(f"   CUDA版本: {torch.version.cuda}")
            return "cuda", gpu_count, gpu_memory
        else:
            print("⚠️  未檢測到可用的GPU，將使用CPU")
            return "cpu", 0, 0
    except ImportError:
        print("⚠️  PyTorch未安裝，無法檢測GPU，將使用CPU")
        return "cpu", 0, 0
    except Exception as e:
        print(f"⚠️  GPU檢測失敗: {e}，將使用CPU")
        return "cpu", 0, 0

def get_optimal_workers(device, gpu_count, gpu_memory):
    """根據系統資源計算最佳工作進程數"""
    cpu_count = mp.cpu_count()
    available_memory = psutil.virtual_memory().available / 1024**3  # GB
    
    print(f"💻 系統資源分析:")
    print(f"   CPU核心數: {cpu_count}")
    print(f"   可用記憶體: {available_memory:.1f} GB")
    
    if device == "cuda":
        # GPU處理：優化記憶體使用
        if gpu_memory >= 8:  # 8GB以上GPU
            workers = min(6, cpu_count)
        elif gpu_memory >= 6:  # 6-8GB GPU
            workers = min(4, cpu_count)
        elif gpu_memory >= 4:  # 4-6GB GPU (你的GTX 1650)
            workers = min(3, cpu_count)  # 從2增加到3
        else:  # 小於4GB GPU
            workers = min(2, cpu_count)  # 從1增加到2
        print(f"   🎯 GPU模式 - 建議工作進程數: {workers}")
    else:
        # CPU處理：考慮記憶體限制
        if available_memory >= 16:  # 16GB以上記憶體
            workers = min(cpu_count, 8)
        elif available_memory >= 8:  # 8-16GB記憶體
            workers = min(cpu_count // 2, 4)
        else:  # 小於8GB記憶體
            workers = min(cpu_count // 4, 2)
        print(f"   🎯 CPU模式 - 建議工作進程數: {workers}")
    
    return max(1, workers)  # 至少1個工作進程

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

=======
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
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

<<<<<<< HEAD
def convert_single_pdf_worker(args):
    """單個PDF轉換工作函數（用於多進程）"""
    pdf_path, output_dir, image_output_dir, device, model_cache_path, encoding, enable_math_processing, enable_multilingual_ocr, extract_table_format, worker_id = args
    
=======
def convert_pdf_to_markdown(pdf_path, output_dir, image_output_dir, extractor, encoding="utf-8", 
                          enable_math_processing=True, enable_multilingual_ocr=True):
    """轉換單個PDF檔案為Markdown，支援多重OCR和數學公式處理"""
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
    try:
        # 驗證PDF檔案
        is_valid, validation_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            return False, f"工作進程 {worker_id}: {validation_msg}"
        
        # 為每個工作進程創建獨立的extractor
        try:
            extractor = create_pdf_page_extractor(
                device=device,
                model_dir_path=str(model_cache_path),
                extract_formula=True,
                extract_table_format=extract_table_format,
            )
        except Exception as e:
            return False, f"工作進程 {worker_id}: PDF解析器初始化失敗 - {str(e)}"
        
        if not extractor:
            return False, f"工作進程 {worker_id}: PDF解析器初始化失敗"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        image_output_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = pdf_path.stem
        output_md_path = output_dir / f"{pdf_name}.md"
        
<<<<<<< HEAD
        start_time = time.time()
        
        try:
            with MarkDownWriter(output_md_path, image_output_dir, encoding) as md:
                for block in extractor.extract(str(pdf_path)):
                    if enable_math_processing and hasattr(block, 'text'):
                        block.text = process_math_formulas(block.text)
                    md.write(block)
                    
        except ModuleNotFoundError as module_error:
            if "struct_eqtable" in str(module_error):
                with open(output_md_path, 'w', encoding=encoding) as f:
                    f.write(f"# {pdf_name}\n\n")
                    f.write(f"*此檔案因表格處理模組缺失而無法完整轉換*\n\n")
                    f.write(f"原始檔案: {pdf_path.name}\n")
                    f.write(f"轉換時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                return True, f"工作進程 {worker_id}: 創建基本文字版本"
            else:
                return False, f"工作進程 {worker_id}: 模組錯誤 - {module_error}"
                
        except Exception as extract_error:
            error_details = traceback.format_exc()
            logging.error(f"PDF提取失敗: {pdf_path.name}\n錯誤詳情: {error_details}")
            return False, f"工作進程 {worker_id}: PDF提取失敗 - {extract_error}"
            
        elapsed_time = time.time() - start_time
        return True, f"工作進程 {worker_id}: 完成轉換 {pdf_name} (耗時: {elapsed_time:.2f}秒)"
=======
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
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
        
    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"工作進程 {worker_id} 未知錯誤: {pdf_path.name}\n錯誤詳情: {error_details}")
        return False, f"工作進程 {worker_id}: 未知錯誤 - {str(e)}"
    finally:
        # 優化GPU記憶體清理策略
        if device == "cuda":
            try:
                import torch
                # 只在記憶體使用超過80%時才清理
                if torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated() > 0.8:
                    torch.cuda.empty_cache()
                    gc.collect()
            except:
                pass

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

<<<<<<< HEAD
def batch_convert_parallel(root_dir, output_base_dir, image_output_dir, model_cache_path, device, encoding, enable_math_processing, enable_multilingual_ocr, extract_table_format, max_workers=None):
    """並行批次轉換PDF檔案"""
    excluded_subjects = {"Chinese", "English"}
    progress_file = output_base_dir / "conversion_progress.json"
    failed_files_file = output_base_dir / "failed_files.json"
    processed_files = set()
    failed_files = []
=======
def process_subject(subject, base_input_dir, output_base_dir, image_output_dir, model_cache_path, 
                   device, encoding, enable_math_processing, enable_multilingual_ocr, extract_table_format):
    """處理單個科目的所有PDF檔案"""
    print(f"\n{'='*20} 處理 {subject} 科目 {'='*20}")
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
    
    if progress_file.exists():
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                processed_files = set(progress_data.get('processed_files', []))
                failed_files = progress_data.get('failed_files', [])
                print(f"📋 發現進度檔案，已處理 {len(processed_files)} 個檔案")
                print(f"❌ 失敗檔案: {len(failed_files)} 個")
                print(f"🔄 將從未處理的檔案開始繼續轉換")
        except Exception as e:
            print(f"⚠️  讀取進度檔案失敗: {e}")
    
    all_pdfs = list(Path(root_dir).rglob("*.pdf"))
    print(f"\n🔍 掃描目錄: {root_dir}")
    print(f"📄 找到 {len(all_pdfs)} 個PDF檔案")
    print(f"🚫 排除科目: {', '.join(excluded_subjects)}")
    
<<<<<<< HEAD
    pdfs_to_process = []
    for pdf_path in all_pdfs:
        path_parts = pdf_path.parts
        root_parts = Path(root_dir).parts
        if len(path_parts) > len(root_parts):
            subject_name = path_parts[-2]
            if subject_name not in excluded_subjects:
                if str(pdf_path) not in processed_files:
                    pdfs_to_process.append(pdf_path)
                else:
                    print(f"⏭️  跳過已處理的檔案: {pdf_path.name}")
            else:
                print(f"⏭️  跳過 {subject_name} 科目檔案: {pdf_path.name}")
=======
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
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
        else:
            print(f"⚠️  跳過路徑結構不正確的檔案: {pdf_path}")
    
    # 計算最佳工作進程數
    device_type, gpu_count, gpu_memory = detect_gpu()
    if max_workers is None:
        max_workers = get_optimal_workers(device_type, gpu_count, gpu_memory)
    
<<<<<<< HEAD
    print(f"✅ 將處理 {len(pdfs_to_process)} 個PDF檔案")
    if len(pdfs_to_process) == 0:
        print("🎉 所有檔案都已處理完成！")
        return
    
    # 強制使用單一進程
    max_workers = 1
    print(f"🚀 使用 {max_workers} 個並行工作進程")
    
    # 準備工作任務
    tasks = []
    for i, pdf_path in enumerate(pdfs_to_process):
        rel_path = pdf_path.parent.relative_to(root_dir)
        output_dir = output_base_dir / rel_path
        image_dir = image_output_dir / rel_path
        
        task_args = (
            pdf_path,
            output_dir,
            image_dir,
            device,
            model_cache_path,
            encoding,
            enable_math_processing,
            enable_multilingual_ocr,
            extract_table_format,
            i + 1  # worker_id
=======
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
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
        )
        tasks.append(task_args)
    
    total_success = 0
    total_failed = 0
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任務
            future_to_task = {executor.submit(convert_single_pdf_worker, task): task for task in tasks}
            
            # 處理完成的任務
            for i, future in enumerate(as_completed(future_to_task), 1):
                task = future_to_task[future]
                pdf_path = task[0]
                
                try:
                    success, message = future.result()
                    print(f"\n{'='*20} 完成任務 {i}/{len(tasks)} {'='*20}")
                    print(f"📄 檔案: {pdf_path.name}")
                    print(f"📁 路徑: {pdf_path}")
                    print(f"📋 結果: {message}")
                    
                    processed_files.add(str(pdf_path))
                    
                    if success:
                        total_success += 1
                        print(f"✅ 成功轉換: {pdf_path.name}")
                    else:
                        total_failed += 1
                        failed_files.append({
                            'file': str(pdf_path),
                            'error': message,
                            'timestamp': time.time()
                        })
                        print(f"❌ 轉換失敗: {pdf_path.name}")
                    
                    # 每處理10個檔案保存一次進度
                    if i % 10 == 0:
                        save_progress(progress_file, processed_files, total_success, total_failed, failed_files)
                        print(f"💾 已保存進度 ({i}/{len(tasks)})")
                        
                except Exception as e:
                    total_failed += 1
                    failed_files.append({
                        'file': str(pdf_path),
                        'error': str(e),
                        'timestamp': time.time()
                    })
                    print(f"❌ 任務執行失敗: {pdf_path.name}")
                    print(f"   錯誤: {str(e)}")
                    
    except KeyboardInterrupt:
        print(f"\n⚠️  使用者中斷轉換")
        print(f"💾 正在保存進度...")
        save_progress(progress_file, processed_files, total_success, total_failed, failed_files)
        print(f"📋 進度已保存，下次執行將從未完成的檔案開始")
        return
    
    print(f"\n{'='*50}")
    print(f"🎉 並行批次轉換完成報告")
    print(f"📄 處理檔案: {len(pdfs_to_process)} 個")
    print(f"✅ 總成功: {total_success} 個檔案")
    print(f"❌ 總失敗: {total_failed} 個檔案")
    print(f"🚀 使用工作進程: {max_workers} 個")
    print(f"📁 輸出目錄: {output_base_dir}")
    print(f"🖼️  圖片目錄: {image_output_dir}")
    
    # 保存失敗檔案清單
    if failed_files:
        with open(failed_files_file, 'w', encoding='utf-8') as f:
            json.dump(failed_files, f, ensure_ascii=False, indent=2)
        print(f"📋 失敗檔案清單已保存至: {failed_files_file}")
    
    if progress_file.exists():
        progress_file.unlink()
        print(f"🧹 已清理進度檔案")
    
    if output_base_dir.exists():
        print(f"\n📂 輸出目錄結構:")
        for output_file in output_base_dir.rglob("*.md"):
            rel_path = output_file.relative_to(output_base_dir)
            print(f"   📄 {rel_path}")

def batch_convert_exclude_chinese_english(root_dir, output_base_dir, image_output_dir, model_cache_path, device, encoding, enable_math_processing, enable_multilingual_ocr, extract_table_format):
    """順序批次轉換（保持原有功能）"""
    excluded_subjects = {"Chinese", "English"}
    progress_file = output_base_dir / "conversion_progress.json"
    failed_files_file = output_base_dir / "failed_files.json"
    processed_files = set()
    failed_files = []
    
    if progress_file.exists():
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                processed_files = set(progress_data.get('processed_files', []))
                failed_files = progress_data.get('failed_files', [])
                print(f"📋 發現進度檔案，已處理 {len(processed_files)} 個檔案")
                print(f"❌ 失敗檔案: {len(failed_files)} 個")
                print(f"🔄 將從未處理的檔案開始繼續轉換")
        except Exception as e:
            print(f"⚠️  讀取進度檔案失敗: {e}")
    
    all_pdfs = list(Path(root_dir).rglob("*.pdf"))
    print(f"\n🔍 掃描目錄: {root_dir}")
    print(f"📄 找到 {len(all_pdfs)} 個PDF檔案")
    print(f"🚫 排除科目: {', '.join(excluded_subjects)}")
    pdfs_to_process = []
    for pdf_path in all_pdfs:
        path_parts = pdf_path.parts
        root_parts = Path(root_dir).parts
        if len(path_parts) > len(root_parts):
            subject_name = path_parts[-2]
            if subject_name not in excluded_subjects:
                if str(pdf_path) not in processed_files:
                    pdfs_to_process.append(pdf_path)
                else:
                    print(f"⏭️  跳過已處理的檔案: {pdf_path.name}")
            else:
                print(f"⏭️  跳過 {subject_name} 科目檔案: {pdf_path.name}")
        else:
<<<<<<< HEAD
            print(f"⚠️  跳過路徑結構不正確的檔案: {pdf_path}")
    print(f"✅ 將處理 {len(pdfs_to_process)} 個PDF檔案")
    if len(pdfs_to_process) == 0:
        print("🎉 所有檔案都已處理完成！")
        return
    extractor = create_pdf_page_extractor(
        device=device,
        model_dir_path=str(model_cache_path),
        extract_formula=True,
        extract_table_format=extract_table_format,
    )
    if not extractor:
        print("❌ PDF解析器初始化失敗")
        return
    total_success = 0
    total_failed = 0
    output_base_dir.mkdir(parents=True, exist_ok=True)
    try:
        for i, pdf_path in enumerate(pdfs_to_process, 1):
            print(f"\n{'='*20} 處理檔案 {i}/{len(pdfs_to_process)} {'='*20}")
            print(f"📄 檔案: {pdf_path.name}")
            print(f"📁 路徑: {pdf_path}")
            rel_path = pdf_path.parent.relative_to(root_dir)
            output_dir = output_base_dir / rel_path
            image_dir = image_output_dir / rel_path
            print(f"📂 輸出目錄: {output_dir}")
            print(f"🖼️  圖片目錄: {image_dir}")
            success, output_path = convert_pdf_to_markdown(
                pdf_path,
                output_dir,
                image_dir,
                extractor,
                encoding=encoding,
                enable_math_processing=enable_math_processing,
                enable_multilingual_ocr=enable_multilingual_ocr
            )
            processed_files.add(str(pdf_path))
            if success:
                total_success += 1
                print(f"✅ 成功轉換: {pdf_path.name}")
            else:
                total_failed += 1
                failed_files.append({
                    'file': str(pdf_path),
                    'error': '轉換失敗',
                    'timestamp': time.time()
                })
                print(f"❌ 轉換失敗: {pdf_path.name}")
            if i % 10 == 0:
                save_progress(progress_file, processed_files, total_success, total_failed, failed_files)
                print(f"💾 已保存進度 ({i}/{len(pdfs_to_process)})")
    except KeyboardInterrupt:
        print(f"\n⚠️  使用者中斷轉換")
        print(f"💾 正在保存進度...")
        save_progress(progress_file, processed_files, total_success, total_failed, failed_files)
        print(f"📋 進度已保存，下次執行將從未完成的檔案開始")
        return
    print(f"\n{'='*50}")
    print(f"🎉 批次轉換完成報告")
    print(f"📄 處理檔案: {len(pdfs_to_process)} 個")
    print(f"✅ 總成功: {total_success} 個檔案")
    print(f"❌ 總失敗: {total_failed} 個檔案")
    print(f"📁 輸出目錄: {output_base_dir}")
    print(f"🖼️  圖片目錄: {image_output_dir}")
    
    # 保存失敗檔案清單
    if failed_files:
        with open(failed_files_file, 'w', encoding='utf-8') as f:
            json.dump(failed_files, f, ensure_ascii=False, indent=2)
        print(f"📋 失敗檔案清單已保存至: {failed_files_file}")
    
    if progress_file.exists():
        progress_file.unlink()
        print(f"🧹 已清理進度檔案")
    if output_base_dir.exists():
        print(f"\n📂 輸出目錄結構:")
        for output_file in output_base_dir.rglob("*.md"):
            rel_path = output_file.relative_to(output_base_dir)
            print(f"   📄 {rel_path}")

def save_progress(progress_file, processed_files, total_success, total_failed, failed_files=None):
    progress_data = {
        'processed_files': list(processed_files),
        'total_success': total_success,
        'total_failed': total_failed,
        'failed_files': failed_files or [],
        'timestamp': time.time()
    }
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  保存進度失敗: {e}")

def main():
    base_input_dir = Path("input_docs")
    output_base_dir = Path("output_docs/test_batch_all_exclude_chinese_english")
    image_output_dir = Path("images/test_batch_all_exclude_chinese_english")
=======
            fail_count += 1
    print(f"\n📊 批次轉換完成：成功 {success_count}，失敗 {fail_count}")

def main():
    # === 設定路徑 ===
    base_input_dir = Path("input_docs")  # 處理 input_docs 底下所有檔案
    output_base_dir = Path("output_docs")
    image_output_dir = Path("images")
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816
    model_cache_path = Path("model")
    device, gpu_count, gpu_memory = detect_gpu()
    encoding = "utf-8"
    enable_math_processing = True
    enable_multilingual_ocr = True
<<<<<<< HEAD
    extract_table_format = ExtractedTableFormat.DISABLE
    
    # 多工處理設定
    use_parallel = True  # 設為False使用順序處理
    max_workers = None   # None表示自動計算，或指定數字如4
    
    print(f"🚀 開始PDF轉換任務")
    print(f"   📁 輸入目錄: {base_input_dir}")
    print(f"   📁 輸出目錄: {output_base_dir}")
    print(f"   🖼️  圖片目錄: {image_output_dir}")
    print(f"   🔧 設備: {device}")
    print(f"   📐 數學公式處理: {'啟用' if enable_math_processing else '停用'}")
    print(f"   🌐 多語言OCR: {'啟用' if enable_multilingual_ocr else '停用'}")
    print(f"   📊 表格提取: 停用 (避免模組缺失錯誤)")
    print(f"   🚀 並行處理: {'啟用' if use_parallel else '停用'}")
    
    try:
        if use_parallel:
            batch_convert_parallel(
                base_input_dir,
                output_base_dir,
                image_output_dir,
                model_cache_path,
                device,
                encoding,
                enable_math_processing,
                enable_multilingual_ocr,
                extract_table_format,
                max_workers
            )
        else:
            batch_convert_exclude_chinese_english(
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
    except Exception as e:
        print(f"❌ 程式執行失敗: {e}")
        error_details = traceback.format_exc()
        logging.error(f"程式執行失敗\n錯誤詳情: {error_details}")
        return 1
    print(f"🎉 程式執行完成")
    return 0
=======
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
>>>>>>> c5fd878ef717c3e7aee6fd715ea2cfcec3472816

if __name__ == "__main__":
    main()