import asyncio
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import fitz  # PyMuPDF для PDF
import pytesseract
from PIL import Image
import io

@dataclass
class BankPayment:
    amount: Decimal
    currency: str
    counterparty: str
    purpose: str
    date: datetime
    account_from: str
    account_to: str
    reference: Optional[str] = None

class BankDocumentOCR:
    def __init__(self):
        self.tesseract_config = r'--oem 3 --psm 6 -l rus+eng'
        self.patterns = {
            'amount': [
                r'(\d+(?:\s?\d{3})*[,\.]\d{2})\s*(?:руб|рублей|USD|EUR|CNY)',
                r'Сумма:?\s*(\d+(?:\s?\d{3})*[,\.]\d{2})',
                r'К\s*доплате:?\s*(\d+(?:\s?\d{3})*[,\.]\d{2})'
            ],
            'currency': [
                r'(\d+(?:\s?\d{3})*[,\.]\d{2})\s*(руб|рублей|USD|EUR|CNY)',
                r'Валюта:?\s*(RUB|USD|EUR|CNY)'
            ],
            'account': [
                r'Счет:?\s*(\d{20})',
                r'Р/?с\s*(\d{20})',
                r'(\d{20})'
            ],
            'date': [
                r'(\d{1,2}[\.\/]\d{1,2}[\.\/]\d{2,4})',
                r'Дата:?\s*(\d{1,2}[\.\/]\d{1,2}[\.\/]\d{2,4})',
                r'(\d{2}\.\d{2}\.\d{4})'
            ],
            'counterparty': [
                r'(?:ООО|ИП|ЗАО|ОАО|АО)\s+"?([^"\n\r]{3,50})"?',
                r'Плательщик:?\s*([^\n\r]{10,80})',
                r'Получатель:?\s*([^\n\r]{10,80})'
            ]
        }
    async def process_bank_document(self, file_path: str) -> List[BankPayment]:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._process_document_sync, file_path)
        except Exception as e:
            raise Exception(f"Ошибка обработки банковского документа: {str(e)}")
    def _process_document_sync(self, file_path: str) -> List[BankPayment]:
        doc = fitz.open(file_path)
        all_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            if len(text.strip()) < 100:
                text = self._ocr_page(page)
            all_text.append(text)
        doc.close()
        full_text = "\n\n".join(all_text)
        payments = self._extract_payments(full_text)
        return payments
    def _ocr_page(self, page) -> str:
        try:
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            text = pytesseract.image_to_string(img, config=self.tesseract_config)
            return text
        except Exception:
            return ""
    def _extract_payments(self, text: str) -> List[BankPayment]:
        payments = []
        blocks = self._split_into_payment_blocks(text)
        for block in blocks:
            payment = self._extract_single_payment(block)
            if payment:
                payments.append(payment)
        return payments
    def _split_into_payment_blocks(self, text: str) -> List[str]:
        separators = [
            r'^\s*\d+\.\s*',
            r'Операция\s*№',
            r'Документ\s*№',
            r'={20,}',
            r'-{20,}'
        ]
        blocks = [text]
        for separator in separators:
            new_blocks = []
            for block in blocks:
                parts = re.split(separator, block, flags=re.MULTILINE)
                new_blocks.extend([part.strip() for part in parts if part.strip()])
            blocks = new_blocks
        return [block for block in blocks if len(block) > 50]
    def _extract_single_payment(self, text: str) -> Optional[BankPayment]:
        try:
            amount = self._extract_amount(text)
            if not amount:
                return None
            currency = self._extract_currency(text)
            date = self._extract_date(text)
            counterparty = self._extract_counterparty(text)
            accounts = self._extract_accounts(text)
            account_from = accounts[0] if len(accounts) > 0 else ""
            account_to = accounts[1] if len(accounts) > 1 else ""
            purpose = text[:100].replace('\n', ' ').strip()
            return BankPayment(
                amount=amount,
                currency=currency,
                counterparty=counterparty,
                purpose=purpose,
                date=date,
                account_from=account_from,
                account_to=account_to
            )
        except Exception:
            return None
    def _extract_amount(self, text: str) -> Optional[Decimal]:
        for pattern in self.patterns['amount']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    return Decimal(amount_str)
                except:
                    continue
        return None
    def _extract_currency(self, text: str) -> str:
        for pattern in self.patterns['currency']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                currency = match.group(2).upper()
                if currency in ['РУБЛЕЙ', 'РУБ']:
                    return 'RUB'
                return currency
        return 'RUB'
    def _extract_date(self, text: str) -> Optional[datetime]:
        for pattern in self.patterns['date']:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%d.%m.%y']:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except:
                        continue
        return datetime.now()
    def _extract_counterparty(self, text: str) -> str:
        for pattern in self.patterns['counterparty']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Не определен"
    def _extract_accounts(self, text: str) -> List[str]:
        accounts = []
        for pattern in self.patterns['account']:
            matches = re.findall(pattern, text)
            accounts.extend(matches)
        return list(set(accounts)) 