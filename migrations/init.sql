-- migrations/init.sql
-- Миграция для микросервисной архитектуры (Schema-based separation)

-- Расширения (должны быть в public схеме)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================
-- Схема: users (Users Service)
-- ========================================
CREATE SCHEMA IF NOT EXISTS users_schema;

CREATE TABLE IF NOT EXISTS users_schema.users (
    id BIGINT PRIMARY KEY, -- Telegram ID
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(20),
    language VARCHAR(5) DEFAULT 'en',
    role VARCHAR(20) DEFAULT 'passenger', -- passenger, driver, admin
    is_active BOOLEAN DEFAULT TRUE,
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users_schema.driver_profiles (
    user_id BIGINT PRIMARY KEY, -- Ссылка на users.id (внутри схемы можно FK)
    car_brand VARCHAR(100),
    car_model VARCHAR(100),
    car_color VARCHAR(50),
    car_plate VARCHAR(20),
    is_verified BOOLEAN DEFAULT FALSE,
    is_working BOOLEAN DEFAULT FALSE,
    rating DECIMAL(3, 2) DEFAULT 5.00,
    total_trips INTEGER DEFAULT 0,
    -- balance убран отсюда в payments_schema
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users_schema.users(id) ON DELETE CASCADE
);

-- Индексы users
CREATE INDEX IF NOT EXISTS idx_users_role ON users_schema.users(role);
CREATE INDEX IF NOT EXISTS idx_driver_profiles_is_working ON users_schema.driver_profiles(is_working);

-- ========================================
-- Схема: trips (Trip Service)
-- ========================================
CREATE SCHEMA IF NOT EXISTS trips_schema;

CREATE TABLE IF NOT EXISTS trips_schema.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    passenger_id BIGINT NOT NULL, -- Нет FK на users_schema!
    driver_id BIGINT,             -- Нет FK на users_schema!
    
    -- Геолокация (Pickup)
    pickup_lat DECIMAL(10, 7) NOT NULL,
    pickup_lon DECIMAL(10, 7) NOT NULL,
    pickup_address TEXT,
    
    -- Геолокация (Destination)
    destination_lat DECIMAL(10, 7),
    destination_lon DECIMAL(10, 7),
    destination_address TEXT,
    
    -- Остановки (JSONB для гибкости)
    stops JSONB DEFAULT '[]'::jsonb, 
    
    -- Детали поездки
    distance_km DECIMAL(8, 2),
    duration_min INTEGER,
    fare DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'EUR',
    
    -- Статусы
    status VARCHAR(30) DEFAULT 'draft', -- draft, new, searching, on_way, arrived, started, completed, cancelled
    payment_method VARCHAR(20) DEFAULT 'cash', -- cash, stars, card
    payment_status VARCHAR(20) DEFAULT 'pending',
    
    -- Временные метки
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accepted_at TIMESTAMP WITH TIME ZONE,
    arrived_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    
    cancellation_reason TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS trips_schema.ratings (
    id SERIAL PRIMARY KEY,
    order_id UUID NOT NULL, -- Внутри схемы можно FK, но orders может быть архивирован. Оставим FK.
    from_user_id BIGINT NOT NULL,
    to_user_id BIGINT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES trips_schema.orders(id)
);

-- Индексы trips
CREATE INDEX IF NOT EXISTS idx_orders_passenger_id ON trips_schema.orders(passenger_id);
CREATE INDEX IF NOT EXISTS idx_orders_driver_id ON trips_schema.orders(driver_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON trips_schema.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON trips_schema.orders(created_at DESC);

-- ========================================
-- Схема: payments (Payments Service)
-- ========================================
CREATE SCHEMA IF NOT EXISTS payments_schema;

CREATE TABLE IF NOT EXISTS payments_schema.wallets (
    user_id BIGINT PRIMARY KEY, -- Telegram ID
    balance DECIMAL(12, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'EUR',
    is_frozen BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments_schema.transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id BIGINT NOT NULL, -- Ссылка на wallets.user_id
    order_id UUID, -- Просто ID, без FK на trips_schema
    type VARCHAR(30) NOT NULL, -- deposit, withdrawal, payment, refund, fee
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    status VARCHAR(20) DEFAULT 'pending', -- pending, success, failed
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_wallet FOREIGN KEY (wallet_id) REFERENCES payments_schema.wallets(user_id)
);

-- Индексы payments
CREATE INDEX IF NOT EXISTS idx_transactions_wallet_id ON payments_schema.transactions(wallet_id);
CREATE INDEX IF NOT EXISTS idx_transactions_order_id ON payments_schema.transactions(order_id);

-- ========================================
-- Триггеры для updated_at (Generic)
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Users Schema Triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users_schema.users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users_schema.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_driver_profiles_updated_at ON users_schema.driver_profiles;
CREATE TRIGGER update_driver_profiles_updated_at
    BEFORE UPDATE ON users_schema.driver_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Payments Schema Triggers
DROP TRIGGER IF EXISTS update_wallets_updated_at ON payments_schema.wallets;
CREATE TRIGGER update_wallets_updated_at
    BEFORE UPDATE ON payments_schema.wallets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
