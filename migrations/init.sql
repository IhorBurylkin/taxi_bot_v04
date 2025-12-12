-- migrations/init.sql
-- Начальная миграция для создания таблиц

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================
-- Миграция: переименование колонок для совместимости с v4
-- ========================================
DO $$
BEGIN
    -- users: user_id -> id
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='user_id') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='id') THEN
            ALTER TABLE users RENAME COLUMN user_id TO id;
        END IF;
    END IF;

    -- orders
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='orders') THEN
        -- order_id -> id
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='order_id') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='id') THEN
            ALTER TABLE orders RENAME COLUMN order_id TO id;
        END IF;
        
        -- from_lat -> pickup_lat
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='from_lat') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='pickup_lat') THEN
            ALTER TABLE orders RENAME COLUMN from_lat TO pickup_lat;
        END IF;

        -- from_lon -> pickup_lon
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='from_lon') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='pickup_lon') THEN
            ALTER TABLE orders RENAME COLUMN from_lon TO pickup_lon;
        END IF;

        -- address_from -> pickup_address
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='address_from') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='pickup_address') THEN
            ALTER TABLE orders RENAME COLUMN address_from TO pickup_address;
        END IF;

        -- to_lat -> destination_lat
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='to_lat') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='destination_lat') THEN
            ALTER TABLE orders RENAME COLUMN to_lat TO destination_lat;
        END IF;

        -- to_lon -> destination_lon
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='to_lon') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='destination_lon') THEN
            ALTER TABLE orders RENAME COLUMN to_lon TO destination_lon;
        END IF;

        -- address_to -> destination_address
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='address_to') AND
           NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='destination_address') THEN
            ALTER TABLE orders RENAME COLUMN address_to TO destination_address;
        END IF;

        -- Convert id to UUID if it is BIGINT
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='id' AND data_type='bigint') THEN
            ALTER TABLE orders ADD COLUMN new_id UUID DEFAULT uuid_generate_v4();
            ALTER TABLE orders DROP COLUMN id CASCADE;
            ALTER TABLE orders RENAME COLUMN new_id TO id;
            ALTER TABLE orders ADD PRIMARY KEY (id);
        END IF;
    END IF;
END $$;

-- ========================================
-- Вспомогательная функция для безопасного добавления колонок
-- ========================================
CREATE OR REPLACE FUNCTION add_column_if_not_exists(
    t_name text,
    c_name text,
    c_type text
) RETURNS void AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name=t_name AND column_name=c_name) THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN %I %s', t_name, c_name, c_type);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- Таблица пользователей
-- ========================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(20),
    language VARCHAR(5) DEFAULT 'en',
    role VARCHAR(20) DEFAULT 'passenger',
    is_active BOOLEAN DEFAULT TRUE,
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Проверка колонок для users
SELECT add_column_if_not_exists('users', 'username', 'VARCHAR(255)');
SELECT add_column_if_not_exists('users', 'first_name', 'VARCHAR(255)');
SELECT add_column_if_not_exists('users', 'last_name', 'VARCHAR(255)');
SELECT add_column_if_not_exists('users', 'phone', 'VARCHAR(20)');
SELECT add_column_if_not_exists('users', 'language', 'VARCHAR(5) DEFAULT ''en''');
SELECT add_column_if_not_exists('users', 'role', 'VARCHAR(20) DEFAULT ''passenger''');
SELECT add_column_if_not_exists('users', 'is_active', 'BOOLEAN DEFAULT TRUE');
SELECT add_column_if_not_exists('users', 'is_blocked', 'BOOLEAN DEFAULT FALSE');
SELECT add_column_if_not_exists('users', 'created_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');
SELECT add_column_if_not_exists('users', 'updated_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');

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

-- Проверка колонок для driver_profiles
SELECT add_column_if_not_exists('driver_profiles', 'car_brand', 'VARCHAR(100)');
SELECT add_column_if_not_exists('driver_profiles', 'car_model', 'VARCHAR(100)');
SELECT add_column_if_not_exists('driver_profiles', 'car_color', 'VARCHAR(50)');
SELECT add_column_if_not_exists('driver_profiles', 'car_plate', 'VARCHAR(20)');
SELECT add_column_if_not_exists('driver_profiles', 'is_verified', 'BOOLEAN DEFAULT FALSE');
SELECT add_column_if_not_exists('driver_profiles', 'is_working', 'BOOLEAN DEFAULT FALSE');
SELECT add_column_if_not_exists('driver_profiles', 'rating', 'DECIMAL(3, 2) DEFAULT 5.00');
SELECT add_column_if_not_exists('driver_profiles', 'total_trips', 'INTEGER DEFAULT 0');
SELECT add_column_if_not_exists('driver_profiles', 'balance', 'DECIMAL(12, 2) DEFAULT 0.00');
SELECT add_column_if_not_exists('driver_profiles', 'created_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');
SELECT add_column_if_not_exists('driver_profiles', 'updated_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');

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

-- Проверка колонок для orders
SELECT add_column_if_not_exists('orders', 'passenger_id', 'BIGINT NOT NULL REFERENCES users(id)');
SELECT add_column_if_not_exists('orders', 'driver_id', 'BIGINT REFERENCES users(id)');
SELECT add_column_if_not_exists('orders', 'pickup_lat', 'DECIMAL(10, 7) NOT NULL');
SELECT add_column_if_not_exists('orders', 'pickup_lon', 'DECIMAL(10, 7) NOT NULL');
SELECT add_column_if_not_exists('orders', 'pickup_address', 'TEXT');
SELECT add_column_if_not_exists('orders', 'destination_lat', 'DECIMAL(10, 7)');
SELECT add_column_if_not_exists('orders', 'destination_lon', 'DECIMAL(10, 7)');
SELECT add_column_if_not_exists('orders', 'destination_address', 'TEXT');
SELECT add_column_if_not_exists('orders', 'distance_km', 'DECIMAL(8, 2)');
SELECT add_column_if_not_exists('orders', 'duration_min', 'INTEGER');
SELECT add_column_if_not_exists('orders', 'fare', 'DECIMAL(10, 2)');
SELECT add_column_if_not_exists('orders', 'currency', 'VARCHAR(3) DEFAULT ''RUB''');
SELECT add_column_if_not_exists('orders', 'status', 'VARCHAR(30) DEFAULT ''pending''');
SELECT add_column_if_not_exists('orders', 'payment_status', 'VARCHAR(20) DEFAULT ''pending''');
SELECT add_column_if_not_exists('orders', 'created_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');
SELECT add_column_if_not_exists('orders', 'accepted_at', 'TIMESTAMP WITH TIME ZONE');
SELECT add_column_if_not_exists('orders', 'arrived_at', 'TIMESTAMP WITH TIME ZONE');
SELECT add_column_if_not_exists('orders', 'started_at', 'TIMESTAMP WITH TIME ZONE');
SELECT add_column_if_not_exists('orders', 'completed_at', 'TIMESTAMP WITH TIME ZONE');
SELECT add_column_if_not_exists('orders', 'cancelled_at', 'TIMESTAMP WITH TIME ZONE');
SELECT add_column_if_not_exists('orders', 'cancellation_reason', 'TEXT');
SELECT add_column_if_not_exists('orders', 'notes', 'TEXT');

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

-- Проверка колонок для transactions
SELECT add_column_if_not_exists('transactions', 'user_id', 'BIGINT NOT NULL REFERENCES users(id)');
SELECT add_column_if_not_exists('transactions', 'order_id', 'UUID REFERENCES orders(id)');
SELECT add_column_if_not_exists('transactions', 'type', 'VARCHAR(30) NOT NULL');
SELECT add_column_if_not_exists('transactions', 'amount', 'DECIMAL(12, 2) NOT NULL');
SELECT add_column_if_not_exists('transactions', 'currency', 'VARCHAR(3) DEFAULT ''RUB''');
SELECT add_column_if_not_exists('transactions', 'status', 'VARCHAR(20) DEFAULT ''pending''');
SELECT add_column_if_not_exists('transactions', 'description', 'TEXT');
SELECT add_column_if_not_exists('transactions', 'created_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');
SELECT add_column_if_not_exists('transactions', 'processed_at', 'TIMESTAMP WITH TIME ZONE');

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

-- Проверка колонок для ratings
SELECT add_column_if_not_exists('ratings', 'order_id', 'UUID NOT NULL REFERENCES orders(id)');
SELECT add_column_if_not_exists('ratings', 'from_user_id', 'BIGINT NOT NULL REFERENCES users(id)');
SELECT add_column_if_not_exists('ratings', 'to_user_id', 'BIGINT NOT NULL REFERENCES users(id)');
SELECT add_column_if_not_exists('ratings', 'rating', 'INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5)');
SELECT add_column_if_not_exists('ratings', 'comment', 'TEXT');
SELECT add_column_if_not_exists('ratings', 'created_at', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()');

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
