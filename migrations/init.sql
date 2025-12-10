-- migrations/init.sql
-- Начальная миграция для создания таблиц

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================
-- Таблица пользователей
-- ========================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(20),
    language VARCHAR(5) DEFAULT 'ru',
    role VARCHAR(20) DEFAULT 'passenger',
    is_active BOOLEAN DEFAULT TRUE,
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- ========================================
-- Таблица профилей водителей
-- ========================================
CREATE TABLE IF NOT EXISTS driver_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    car_brand VARCHAR(100),
    car_model VARCHAR(100),
    car_color VARCHAR(50),
    car_plate VARCHAR(20),
    is_verified BOOLEAN DEFAULT FALSE,
    is_working BOOLEAN DEFAULT FALSE,
    rating DECIMAL(3, 2) DEFAULT 5.00,
    total_trips INTEGER DEFAULT 0,
    balance DECIMAL(12, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_driver_profiles_is_working ON driver_profiles(is_working);
CREATE INDEX IF NOT EXISTS idx_driver_profiles_is_verified ON driver_profiles(is_verified);

-- ========================================
-- Таблица заказов
-- ========================================
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    passenger_id BIGINT NOT NULL REFERENCES users(id),
    driver_id BIGINT REFERENCES users(id),
    
    -- Геолокация
    pickup_lat DECIMAL(10, 7) NOT NULL,
    pickup_lon DECIMAL(10, 7) NOT NULL,
    pickup_address TEXT,
    destination_lat DECIMAL(10, 7),
    destination_lon DECIMAL(10, 7),
    destination_address TEXT,
    
    -- Маршрут и стоимость
    distance_km DECIMAL(8, 2),
    duration_min INTEGER,
    fare DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'RUB',
    
    -- Статусы
    status VARCHAR(30) DEFAULT 'pending',
    payment_status VARCHAR(20) DEFAULT 'pending',
    
    -- Временные метки
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accepted_at TIMESTAMP WITH TIME ZONE,
    arrived_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    
    -- Дополнительно
    cancellation_reason TEXT,
    notes TEXT
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_orders_passenger_id ON orders(passenger_id);
CREATE INDEX IF NOT EXISTS idx_orders_driver_id ON orders(driver_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

-- ========================================
-- Таблица транзакций
-- ========================================
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL REFERENCES users(id),
    order_id UUID REFERENCES orders(id),
    type VARCHAR(30) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',
    status VARCHAR(20) DEFAULT 'pending',
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_order_id ON transactions(order_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);

-- ========================================
-- Таблица рейтингов
-- ========================================
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    from_user_id BIGINT NOT NULL REFERENCES users(id),
    to_user_id BIGINT NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(order_id, from_user_id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_ratings_to_user_id ON ratings(to_user_id);

-- ========================================
-- Функция обновления updated_at
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_driver_profiles_updated_at ON driver_profiles;
CREATE TRIGGER update_driver_profiles_updated_at
    BEFORE UPDATE ON driver_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- Представления
-- ========================================

-- Активные заказы
CREATE OR REPLACE VIEW v_active_orders AS
SELECT 
    o.*,
    u_p.first_name as passenger_name,
    u_d.first_name as driver_name,
    dp.car_brand,
    dp.car_model,
    dp.car_plate
FROM orders o
LEFT JOIN users u_p ON o.passenger_id = u_p.id
LEFT JOIN users u_d ON o.driver_id = u_d.id
LEFT JOIN driver_profiles dp ON o.driver_id = dp.user_id
WHERE o.status IN ('pending', 'accepted', 'arrived', 'in_progress');

-- Статистика водителей
CREATE OR REPLACE VIEW v_driver_stats AS
SELECT 
    dp.user_id,
    u.first_name,
    u.last_name,
    dp.rating,
    dp.total_trips,
    dp.balance,
    dp.is_working,
    (SELECT COUNT(*) FROM orders WHERE driver_id = dp.user_id AND status = 'completed') as completed_trips,
    (SELECT COALESCE(SUM(fare), 0) FROM orders WHERE driver_id = dp.user_id AND status = 'completed') as total_earnings
FROM driver_profiles dp
JOIN users u ON dp.user_id = u.id;

-- ========================================
-- Начальные данные (опционально)
-- ========================================
-- INSERT INTO users (id, username, first_name, role) 
-- VALUES (123456789, 'admin', 'Admin', 'admin')
-- ON CONFLICT (id) DO NOTHING;
