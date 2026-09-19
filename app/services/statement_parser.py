from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
from pypdf import PdfReader


@dataclass
class ParsedTransaction:
    transaction_date: date
    amount: Decimal
    merchant: str | None
    description: str | None
    transaction_type: str
    account_type: str | None = None


class StatementParser:
    DATE_COLUMNS = [
        "date",
        "transaction date",
        "transaction_date",
        "txn date",
        "value date",
        "posting date",
    ]

    DESCRIPTION_COLUMNS = [
        "description",
        "details",
        "narration",
        "transaction details",
        "particulars",
        "remarks",
    ]

    MERCHANT_COLUMNS = [
        "merchant",
        "merchant name",
        "payee",
        "beneficiary",
    ]

    AMOUNT_COLUMNS = [
        "amount",
        "transaction amount",
        "value",
    ]

    DEBIT_COLUMNS = [
        "debit",
        "withdrawal",
        "withdrawals",
        "debit amount",
    ]

    CREDIT_COLUMNS = [
        "credit",
        "deposit",
        "deposits",
        "credit amount",
    ]

    def parse_csv(self, content: bytes) -> list[ParsedTransaction]:
        df = pd.read_csv(io.BytesIO(content))

        if df.empty:
            return []

        normalized = {
            self._normalize_column(column): column
            for column in df.columns
        }

        date_col = self._find_column(
            normalized,
            self.DATE_COLUMNS,
        )

        description_col = self._find_column(
            normalized,
            self.DESCRIPTION_COLUMNS,
        )

        merchant_col = self._find_column(
            normalized,
            self.MERCHANT_COLUMNS,
        )

        amount_col = self._find_column(
            normalized,
            self.AMOUNT_COLUMNS,
        )

        debit_col = self._find_column(
            normalized,
            self.DEBIT_COLUMNS,
        )

        credit_col = self._find_column(
            normalized,
            self.CREDIT_COLUMNS,
        )

        if date_col is None:
            raise ValueError("Could not identify transaction date column.")

        if amount_col is None and debit_col is None and credit_col is None:
            raise ValueError(
                "Could not identify amount/debit/credit columns."
            )

        transactions: list[ParsedTransaction] = []

        for _, row in df.iterrows():
            parsed_date = self._parse_date(row[date_col])

            if parsed_date is None:
                continue

            description = (
                str(row[description_col]).strip()
                if description_col and pd.notna(row[description_col])
                else None
            )

            merchant = (
                str(row[merchant_col]).strip()
                if merchant_col and pd.notna(row[merchant_col])
                else None
            )

            if not merchant and description:
                merchant = self._extract_merchant(description)

            amount, transaction_type = self._extract_amount(
                row,
                amount_col,
                debit_col,
                credit_col,
            )

            if amount is None or amount == 0:
                continue

            transactions.append(
                ParsedTransaction(
                    transaction_date=parsed_date,
                    amount=abs(amount),
                    merchant=merchant,
                    description=description,
                    transaction_type=transaction_type,
                )
            )

        return transactions

    def parse_pdf(self, content: bytes) -> list[ParsedTransaction]:
        reader = PdfReader(io.BytesIO(content))

        pages = []

        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)

        text = "\n".join(pages)

        return self.parse_text(text)

    def parse_text(self, text: str) -> list[ParsedTransaction]:
        transactions: list[ParsedTransaction] = []

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        date_pattern = re.compile(
            r"(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        )

        amount_pattern = re.compile(
            r"(?P<amount>-?\s*[₹$€£]?\s*"
            r"\d[\d,]*(?:\.\d{1,2})?)"
        )

        for line in lines:
            date_match = date_pattern.search(line)

            if not date_match:
                continue

            amount_matches = list(amount_pattern.finditer(line))

            if not amount_matches:
                continue

            amount_match = amount_matches[-1]

            try:
                parsed_date = pd.to_datetime(
                    date_match.group("date"),
                    dayfirst=True,
                    errors="coerce",
                )

                if pd.isna(parsed_date):
                    continue

                amount = Decimal(
                    amount_match.group("amount")
                    .replace(",", "")
                    .replace("₹", "")
                    .replace("$", "")
                    .replace("€", "")
                    .replace("£", "")
                    .replace(" ", "")
                )

            except (InvalidOperation, ValueError):
                continue

            transaction_type = (
                "expense"
                if amount < 0
                else "income"
            )

            description = line

            transactions.append(
                ParsedTransaction(
                    transaction_date=parsed_date.date(),
                    amount=abs(amount),
                    merchant=self._extract_merchant(description),
                    description=description,
                    transaction_type=transaction_type,
                )
            )

        return transactions

    @staticmethod
    def _normalize_column(column: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            str(column).strip().lower(),
        )

    def _find_column(
        self,
        normalized: dict[str, str],
        candidates: list[str],
    ) -> str | None:
        for candidate in candidates:
            normalized_candidate = self._normalize_column(candidate)

            if normalized_candidate in normalized:
                return normalized[normalized_candidate]

        return None

    @staticmethod
    def _parse_date(value) -> date | None:
        parsed = pd.to_datetime(
            value,
            dayfirst=True,
            errors="coerce",
        )

        if pd.isna(parsed):
            return None

        return parsed.date()

    @staticmethod
    def _clean_amount(value) -> Decimal | None:
        if pd.isna(value):
            return None

        text = str(value).strip()

        if not text:
            return None

        negative = (
            "-" in text
            or "(" in text
        )

        text = re.sub(
            r"[^0-9.]",
            "",
            text,
        )

        if not text:
            return None

        amount = Decimal(text)

        return -amount if negative else amount

    def _extract_amount(
        self,
        row,
        amount_col,
        debit_col,
        credit_col,
    ):
        if amount_col:
            amount = self._clean_amount(row[amount_col])

            if amount is None:
                return None, "expense"

            return (
                amount,
                "expense" if amount < 0 else "income",
            )

        debit = (
            self._clean_amount(row[debit_col])
            if debit_col
            else None
        )

        credit = (
            self._clean_amount(row[credit_col])
            if credit_col
            else None
        )

        if debit is not None and debit != 0:
            return abs(debit), "expense"

        if credit is not None and credit != 0:
            return abs(credit), "income"

        return None, "expense"

    @staticmethod
    def _extract_merchant(description: str) -> str | None:
        if not description:
            return None

        cleaned = re.sub(
            r"\s+",
            " ",
            description,
        ).strip()

        # Remove common transaction reference patterns.
        cleaned = re.sub(
            r"\b(UPI|IMPS|NEFT|RTGS|POS|ATM)\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\b\d{6,}\b",
            "",
            cleaned,
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned,
        ).strip()

        return cleaned[:255] or None