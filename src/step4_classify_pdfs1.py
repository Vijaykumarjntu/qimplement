import os
import shutil
import json
import PyPDF2
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ====================== MISTRAL SETUP ======================
mistral_key = os.getenv("MISTRAL_API_KEY")
if not mistral_key:
    print("❌ MISTRAL_API_KEY not found!")
    exit(1)

client = OpenAI(
    api_key=mistral_key,
    base_url="https://api.mistral.ai/v1"
)

# Create folder structure
os.makedirs('inbox_pdfs', exist_ok=True)
os.makedirs('classified/invoices', exist_ok=True)
os.makedirs('classified/not_invoices', exist_ok=True)
os.makedirs('classified/manual_review', exist_ok=True)
os.makedirs('classification_logs', exist_ok=True)

def extract_text_from_pdf(pdf_path):
    """Extract first 3 pages text for classification"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for i in range(min(3, len(reader.pages))):
                text += reader.pages[i].extract_text()
            return text[:3000]
    except Exception as e:
        print(f"   ❌ Error reading PDF: {e}")
        return ""

def rule_based_classify(text):
    """Stricter classification with higher thresholds"""
    if not text:
        return "UNKNOWN", "No text extracted"
    
    text_lower = text.lower()
    
    # Strong invoice indicators (must have multiple)
    invoice_keywords = [
        'invoice', 'invoice number', 'invoice no', 'invoice date',
        'po number', 'purchase order', 'total amount', 'subtotal',
        'amount due', 'payment due', 'vendor', 'bill to', 'remit to'
    ]
    
    # Strong non-invoice indicators
    non_invoice_keywords = [
        'resume', 'curriculum vitae', 'cv', 'job application',
        'objective', 'work experience', 'education',
        'chapter', 'exercise', 'homework', 'textbook',
        'certificate of completion', 'diploma', 'transcript'
    ]
    
    invoice_score = sum(1 for kw in invoice_keywords if kw in text_lower)
    non_invoice_score = sum(1 for kw in non_invoice_keywords if kw in text_lower)
    
    # Stricter thresholds
    if invoice_score >= 3 and invoice_score > non_invoice_score:
        return "INVOICE", f"Found {invoice_score} invoice keywords"
    elif non_invoice_score >= 2:
        return "NOT_INVOICE", f"Found {non_invoice_score} non-invoice keywords"
    elif invoice_score >= 2 and non_invoice_score == 0:
        return "INVOICE", f"Found {invoice_score} invoice keywords, no non-invoice signals"
    else:
        return "UNCERTAIN", f"Invoice score: {invoice_score}, Non-invoice: {non_invoice_score}"

def llm_classify(text):
    """Use LLM for uncertain cases"""
    response = client.chat.completions.create(
        model="mistral-small-latest",
        messages=[{
            "role": "user",
                        "content": f"""Classify this document as INVOICE or NOT_INVOICE.
            
Rules:
- INVOICE: Contains vendor name, customer name, invoice number, line items, total amount
- NOT_INVOICE: Resume, book chapter, article, receipt without vendor details, personal document

Document text:
{text[:2000]}

Respond with ONLY JSON:
{{"classification": "INVOICE" or "NOT_INVOICE", "confidence": 0.0-1.0, "reason": "brief reason"}}
"""
        }],
        response_format={"type": "json_object"}
    )
    
    import json
    # Handle potential non-JSON responses
    try:
        result = json.loads(response.choices[0].message.content)
    except:
        content = response.choices[0].message.content
        if "INVOICE" in content.upper():
            result = {"classification": "INVOICE", "confidence": 0.7, "reason": "LLM determined"}
        else:
            result = {"classification": "NOT_INVOICE", "confidence": 0.7, "reason": "LLM determined"}
    
    return result['classification'], result

def log_classification(pdf_name, rule_result, final_result, llm_details, destination):
    """Store classification record for audit"""
    log_entry = {
        "filename": pdf_name,
        "timestamp": datetime.now().isoformat(),
        "rule_based_result": rule_result,
        "final_classification": final_result,
        "llm_used": rule_result == "UNCERTAIN",
        "llm_details": llm_details if rule_result == "UNCERTAIN" else None,
        "destination": destination
    }
    
    log_file = f"classification_logs/{datetime.now().strftime('%Y%m%d')}.json"
    
    # Load existing logs or create new
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)
    
    return log_file

def classify_and_store():
    """Main function - classifies and moves PDFs to appropriate folders"""
    
    pdf_folder = 'inbox_pdfs'
    if not os.path.exists(pdf_folder):
        print("❌ No inbox_pdfs folder found. Run step3 first to download emails.")
        return
    
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    
    if not pdf_files:
        print("📭 No PDFs found in inbox_pdfs/")
        return
    
    print(f"📄 Found {len(pdf_files)} PDFs to classify\n")
    print("="*60)
    
    stats = {
        'invoice': [],
        'not_invoice': [],
        'uncertain': []
    }
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        print(f"\n🔍 Classifying: {pdf_file}")
        print("-" * 40)
        
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        
        if not text:
            print(f"   ⚠️ No text extracted → moving to MANUAL_REVIEW")
            dest = 'classified/manual_review'
            final_result = "UNCERTAIN"
            rule_result = "NO_TEXT"
            llm_details = None
            stats['uncertain'].append(pdf_file)
        else:
            # Step 1: Rule-based
            rule_result, rule_reason = rule_based_classify(text)
            print(f"   📊 Rule-based: {rule_result}")
            print(f"      Reason: {rule_reason}")
            
            # Step 2: If uncertain, use LLM
            if rule_result == "UNCERTAIN":
                print(f"   🤖 Uncertain → using LLM...")
                llm_result, llm_details = llm_classify(text)
                print(f"   🧠 LLM: {llm_result} (confidence: {llm_details.get('confidence', 0):.2f})")
                print(f"      Reason: {llm_details.get('reason', 'N/A')[:100]}")
                final_result = llm_result
            else:
                final_result = rule_result
                llm_details = None
            
            # Determine destination
            if final_result == "INVOICE":
                dest = 'classified/invoices'
                stats['invoice'].append(pdf_file)
                print(f"   ✅ → INVOICE (will process in Step 5)")
            elif final_result == "NOT_INVOICE":
                dest = 'classified/not_invoices'
                stats['not_invoice'].append(pdf_file)
                print(f"   ❌ → NOT INVOICE (ignored)")
            else:
                dest = 'classified/manual_review'
                stats['uncertain'].append(pdf_file)
                print(f"   ⚠️ → MANUAL REVIEW needed")
        
        # Move the file
        shutil.move(pdf_path, os.path.join(dest, pdf_file))
        print(f"   📁 Moved to: {dest}")
        
        # Log classification
        log_file = log_classification(pdf_file, rule_result, final_result, llm_details, dest)
    
    # Print summary
    print("\n" + "="*60)
    print("CLASSIFICATION COMPLETE")
    print("="*60)
    print(f"\n📊 SUMMARY:")
    print(f"   ✅ INVOICES ready: {len(stats['invoice'])}")
    for f in stats['invoice']:
        print(f"      - {f}")
    
    print(f"\n   ❌ NOT INVOICES (ignored): {len(stats['not_invoice'])}")
    for f in stats['not_invoice']:
        print(f"      - {f}")
    
    print(f"\n   ⚠️ MANUAL REVIEW needed: {len(stats['uncertain'])}")
    for f in stats['uncertain']:
        print(f"      - {f}")
    
    print(f"\n📝 Classification log saved to: {log_file}")
    print("\n📁 Folder structure:")
    print("   classified/invoices/     ← Run Step 5 on these")
    print("   classified/not_invoices/  ← Archived")
    print("   classified/manual_review/ ← Review manually")
    
    return stats

if __name__ == "__main__":
    classify_and_store()