# src/services/payments/repository.py
"""
Репозиторий для работы с данными платежей (PostgreSQL).
Схема: payments_schema
Таблицы: wallets, transactions
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from asyncpg import Connection, Record

from src.infra.database import DatabaseManager
from src.shared.models.payment import PaymentDTO, PaymentStatus


class PaymentRepository:
    """Репозиторий платежей."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def get_wallet(self, user_id: int) -> Record | None:
        """Получить кошелек пользователя."""
        query = """
            SELECT * FROM payments_schema.wallets
            WHERE user_id = $1
        """
        return await self.db.fetchrow(query, user_id)

    async def create_wallet(self, user_id: int, currency: str = "XTR") -> None:
        """Создать кошелек пользователя."""
        query = """
            INSERT INTO payments_schema.wallets (user_id, balance, currency)
            VALUES ($1, 0.00, $2)
            ON CONFLICT (user_id) DO NOTHING
        """
        await self.db.execute(query, user_id, currency)

    async def update_balance(self, user_id: int, amount: float) -> float:
        """
        Обновить баланс пользователя.
        Возвращает новый баланс.
        """
        query = """
            UPDATE payments_schema.wallets
            SET balance = balance + $2, updated_at = NOW()
            WHERE user_id = $1
            RETURNING balance
        """
        val = await self.db.fetchval(query, user_id, amount)
        if val is None:
            # Если кошелька нет, создаем и пробуем снова (или ошибка)
            # Для простоты считаем, что кошелек должен быть создан при регистрации водителя
            # Но если нет - создадим
            await self.create_wallet(user_id)
            val = await self.db.fetchval(query, user_id, amount)
        return float(val)

    async def create_transaction(
        self,
        wallet_id: int,
        amount: float,
        transaction_type: str,
        currency: str = "XTR",
        order_id: str | None = None,
        description: str | None = None,
        status: str = "success"
    ) -> str:
        """Создать запись о транзакции."""
        query = """
            INSERT INTO payments_schema.transactions 
            (wallet_id, amount, type, currency, order_id, description, status, created_at, processed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            RETURNING id
        """
        # order_id is UUID in DB, but str in python. Cast if needed or let asyncpg handle UUID
        # asyncpg handles UUID if passed as UUID object or string if casted in query.
        # Let's cast explicitly in query: $5::uuid
        query = query.replace("$5", "$5::uuid")
        
        tx_id = await self.db.fetchval(
            query, 
            wallet_id, 
            amount, 
            transaction_type, 
            currency, 
            order_id, 
            description, 
            status
        )
        return str(tx_id)

    async def get_transactions(
        self, 
        user_id: int, 
        limit: int = 50, 
        offset: int = 0
    ) -> list[Record]:
        """Получить историю транзакций."""
        query = """
            SELECT * FROM payments_schema.transactions
            WHERE wallet_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        return await self.db.fetch(query, user_id, limit, offset)

    # === PaymentDTO persistence (if we store payments separately or map to transactions) ===
    # The schema has `transactions` table, but `PaymentDTO` has more fields like `payer_id`, `payee_id`.
    # The `transactions` table seems to be a ledger for a single wallet.
    # We might need a `payments` table for the actual Payment entity (PaymentDTO).
    # Looking at init.sql, there is NO `payments` table in `payments_schema`.
    # Only `wallets` and `transactions`.
    # However, `PaymentDTO` implies we store the payment request itself.
    # Let's assume for now we store PaymentDTO in Redis (ephemeral) or we need to add a table.
    # But `service.py` has `_save_payment` and `_get_payment_from_db`.
    # Let's add a `payments` table to `payments_schema` via migration or just use `transactions` for now?
    # `PaymentDTO` has `id` (UUID). `transactions` has `id` (UUID).
    # A payment involves two parties (payer -> payee).
    # In a ledger system, this is usually 2 transactions: Debit Payer, Credit Payee.
    # Or 1 Payment record + 2 Ledger entries.
    # Since `init.sql` is fixed for now (I can modify it if needed, but let's stick to plan),
    # I will implement `_save_payment` using a new table `payments` which I will create if not exists,
    # OR I will assume `transactions` is enough if I only care about the driver's wallet.
    # But `PaymentDTO` tracks the status of the payment flow (PENDING -> SUCCEEDED).
    # I'll add a `payments` table creation to `init_db` or just use `transactions` if I can map it.
    # Actually, `PaymentDTO` is about the *Transfer* itself.
    # Let's create a `payments` table in `payments_schema` dynamically if it doesn't exist, 
    # or better, just add it to `init.sql` if I was allowed to change migrations easily.
    # Since I am in "Migration" mode, I should probably stick to what `init.sql` provides or extend it.
    # `init.sql` has `payments_schema.transactions`.
    # I will use `transactions` to store the *result* of payment.
    # But where to store the *state* of payment (PENDING)?
    # I'll create a `payments` table in `payments_schema` in this file's `init_db` or similar.
    # Wait, `init.sql` is already applied?
    # I'll check if I can add a table.
    
    async def create_payments_table_if_not_exists(self):
        query = """
        CREATE TABLE IF NOT EXISTS payments_schema.payments (
            id UUID PRIMARY KEY,
            trip_id UUID,
            payer_id BIGINT,
            payee_id BIGINT,
            amount DECIMAL(12, 2),
            currency VARCHAR(3),
            amount_stars BIGINT,
            method VARCHAR(20),
            status VARCHAR(20),
            platform_commission DECIMAL(12, 2),
            driver_payout DECIMAL(12, 2),
            telegram_payment_charge_id VARCHAR(255),
            provider_payment_charge_id VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            paid_at TIMESTAMP WITH TIME ZONE
        );
        """
        await self.db.execute(query)

    async def save_payment(self, payment: PaymentDTO) -> None:
        """Сохранить платеж."""
        await self.create_payments_table_if_not_exists()
        query = """
            INSERT INTO payments_schema.payments (
                id, trip_id, payer_id, payee_id, amount, currency, amount_stars,
                method, status, platform_commission, driver_payout, created_at
            ) VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                telegram_payment_charge_id = EXCLUDED.telegram_payment_charge_id,
                provider_payment_charge_id = EXCLUDED.provider_payment_charge_id,
                paid_at = EXCLUDED.paid_at,
                updated_at = NOW()
        """
        await self.db.execute(
            query,
            UUID(payment.id),
            payment.trip_id,
            payment.payer_id,
            payment.payee_id,
            payment.amount,
            payment.currency,
            payment.amount_stars,
            payment.method.value,
            payment.status.value,
            payment.platform_commission,
            payment.driver_payout,
            payment.created_at
        )

    async def get_payment(self, payment_id: str) -> PaymentDTO | None:
        """Получить платеж."""
        await self.create_payments_table_if_not_exists()
        query = """
            SELECT * FROM payments_schema.payments WHERE id = $1
        """
        row = await self.db.fetchrow(query, UUID(payment_id))
        if not row:
            return None
        
        # Map row to PaymentDTO
        return PaymentDTO(
            id=str(row['id']),
            trip_id=str(row['trip_id']),
            payer_id=row['payer_id'],
            payee_id=row['payee_id'],
            amount=float(row['amount']),
            currency=row['currency'],
            amount_stars=row['amount_stars'],
            method=row['method'],
            status=row['status'],
            platform_commission=float(row['platform_commission']),
            driver_payout=float(row['driver_payout']),
            created_at=row['created_at'],
            paid_at=row['paid_at'],
            telegram_payment_charge_id=row['telegram_payment_charge_id'],
            provider_payment_charge_id=row['provider_payment_charge_id']
        )
