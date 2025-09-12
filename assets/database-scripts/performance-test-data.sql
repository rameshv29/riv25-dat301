-- Performance Test Data for AI PostgreSQL Workshop
-- This script creates additional test data for performance monitoring scenarios

-- Create performance monitoring schema
CREATE SCHEMA IF NOT EXISTS performance_monitoring;

-- Create performance metrics table
CREATE TABLE IF NOT EXISTS performance_monitoring.query_performance (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(50) NOT NULL,
    query_text TEXT NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    rows_examined INTEGER,
    rows_returned INTEGER,
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_mb INTEGER,
    io_reads INTEGER,
    io_writes INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    database_name VARCHAR(100),
    user_name VARCHAR(100),
    connection_id VARCHAR(50)
);

-- Create index for performance queries
CREATE INDEX IF NOT EXISTS idx_query_performance_executed_at 
ON performance_monitoring.query_performance(executed_at);

CREATE INDEX IF NOT EXISTS idx_query_performance_query_id 
ON performance_monitoring.query_performance(query_id);

-- Create connection metrics table
CREATE TABLE IF NOT EXISTS performance_monitoring.connection_metrics (
    id SERIAL PRIMARY KEY,
    connection_id VARCHAR(50) NOT NULL,
    connection_count INTEGER NOT NULL,
    active_connections INTEGER NOT NULL,
    idle_connections INTEGER NOT NULL,
    waiting_connections INTEGER NOT NULL,
    max_connections INTEGER NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create system metrics table
CREATE TABLE IF NOT EXISTS performance_monitoring.system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,2) NOT NULL,
    metric_unit VARCHAR(20),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50) DEFAULT 'cloudwatch'
);

-- Insert sample performance data
INSERT INTO performance_monitoring.query_performance 
(query_id, query_text, execution_time_ms, rows_examined, rows_returned, cpu_usage_percent, memory_usage_mb, io_reads, io_writes, database_name, user_name, connection_id)
VALUES 
-- Fast queries
('Q001', 'SELECT * FROM users WHERE id = $1', 2, 1, 1, 0.1, 1, 1, 0, 'workshop_db', 'app_user', 'conn_001'),
('Q002', 'SELECT COUNT(*) FROM orders WHERE status = ''active''', 15, 1250, 1, 0.5, 2, 5, 0, 'workshop_db', 'app_user', 'conn_002'),
('Q003', 'SELECT name, email FROM users WHERE created_at > $1', 45, 500, 125, 1.2, 3, 8, 0, 'workshop_db', 'app_user', 'conn_003'),

-- Medium performance queries
('Q004', 'SELECT u.*, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id', 250, 5000, 1000, 5.5, 15, 25, 0, 'workshop_db', 'app_user', 'conn_004'),
('Q005', 'SELECT * FROM orders WHERE created_at BETWEEN $1 AND $2 ORDER BY total_amount DESC', 180, 2500, 500, 3.2, 8, 18, 0, 'workshop_db', 'app_user', 'conn_005'),
('Q006', 'UPDATE users SET last_login = NOW() WHERE id IN (SELECT user_id FROM sessions WHERE active = true)', 320, 1500, 1500, 4.8, 12, 15, 30, 'workshop_db', 'app_user', 'conn_006'),

-- Slow queries (potential issues)
('Q007', 'SELECT * FROM orders o JOIN users u ON o.user_id = u.id WHERE o.created_at > $1 AND u.status = ''premium''', 1250, 50000, 2500, 15.5, 45, 120, 0, 'workshop_db', 'app_user', 'conn_007'),
('Q008', 'SELECT DISTINCT u.email FROM users u WHERE u.id IN (SELECT user_id FROM orders WHERE total_amount > 1000)', 2100, 75000, 150, 25.2, 85, 200, 0, 'workshop_db', 'app_user', 'conn_008'),
('Q009', 'DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL ''90 days''', 5500, 100000, 25000, 35.8, 120, 300, 500, 'workshop_db', 'admin_user', 'conn_009'),

-- Very slow queries (definite issues)
('Q010', 'SELECT * FROM users u CROSS JOIN orders o WHERE u.created_at > $1', 15000, 1000000, 50000, 85.5, 500, 2000, 0, 'workshop_db', 'app_user', 'conn_010'),
('Q011', 'SELECT u.*, o.*, p.* FROM users u, orders o, products p WHERE u.status = ''active''', 25000, 5000000, 100000, 95.2, 800, 5000, 0, 'workshop_db', 'app_user', 'conn_011');

-- Insert connection metrics data
INSERT INTO performance_monitoring.connection_metrics 
(connection_id, connection_count, active_connections, idle_connections, waiting_connections, max_connections, recorded_at)
VALUES 
('metrics_001', 25, 15, 8, 2, 100, NOW() - INTERVAL '1 hour'),
('metrics_002', 32, 22, 8, 2, 100, NOW() - INTERVAL '50 minutes'),
('metrics_003', 45, 35, 8, 2, 100, NOW() - INTERVAL '40 minutes'),
('metrics_004', 58, 45, 10, 3, 100, NOW() - INTERVAL '30 minutes'),
('metrics_005', 72, 55, 12, 5, 100, NOW() - INTERVAL '20 minutes'),
('metrics_006', 85, 68, 12, 5, 100, NOW() - INTERVAL '10 minutes'),
('metrics_007', 92, 75, 12, 5, 100, NOW() - INTERVAL '5 minutes'),
('metrics_008', 88, 70, 13, 5, 100, NOW());

-- Insert system metrics data
INSERT INTO performance_monitoring.system_metrics 
(metric_name, metric_value, metric_unit, recorded_at, source)
VALUES 
-- CPU metrics
('CPUUtilization', 15.5, 'Percent', NOW() - INTERVAL '1 hour', 'cloudwatch'),
('CPUUtilization', 22.3, 'Percent', NOW() - INTERVAL '50 minutes', 'cloudwatch'),
('CPUUtilization', 35.8, 'Percent', NOW() - INTERVAL '40 minutes', 'cloudwatch'),
('CPUUtilization', 45.2, 'Percent', NOW() - INTERVAL '30 minutes', 'cloudwatch'),
('CPUUtilization', 65.5, 'Percent', NOW() - INTERVAL '20 minutes', 'cloudwatch'),
('CPUUtilization', 78.9, 'Percent', NOW() - INTERVAL '10 minutes', 'cloudwatch'),
('CPUUtilization', 85.2, 'Percent', NOW() - INTERVAL '5 minutes', 'cloudwatch'),
('CPUUtilization', 72.1, 'Percent', NOW(), 'cloudwatch'),

-- Memory metrics
('FreeableMemory', 2048.5, 'MB', NOW() - INTERVAL '1 hour', 'cloudwatch'),
('FreeableMemory', 1856.2, 'MB', NOW() - INTERVAL '50 minutes', 'cloudwatch'),
('FreeableMemory', 1654.8, 'MB', NOW() - INTERVAL '40 minutes', 'cloudwatch'),
('FreeableMemory', 1423.5, 'MB', NOW() - INTERVAL '30 minutes', 'cloudwatch'),
('FreeableMemory', 1205.2, 'MB', NOW() - INTERVAL '20 minutes', 'cloudwatch'),
('FreeableMemory', 985.8, 'MB', NOW() - INTERVAL '10 minutes', 'cloudwatch'),
('FreeableMemory', 756.3, 'MB', NOW() - INTERVAL '5 minutes', 'cloudwatch'),
('FreeableMemory', 892.1, 'MB', NOW(), 'cloudwatch'),

-- I/O metrics
('ReadIOPS', 125.5, 'Count/Second', NOW() - INTERVAL '1 hour', 'cloudwatch'),
('ReadIOPS', 185.2, 'Count/Second', NOW() - INTERVAL '50 minutes', 'cloudwatch'),
('ReadIOPS', 245.8, 'Count/Second', NOW() - INTERVAL '40 minutes', 'cloudwatch'),
('ReadIOPS', 325.1, 'Count/Second', NOW() - INTERVAL '30 minutes', 'cloudwatch'),
('ReadIOPS', 425.5, 'Count/Second', NOW() - INTERVAL '20 minutes', 'cloudwatch'),
('ReadIOPS', 525.8, 'Count/Second', NOW() - INTERVAL '10 minutes', 'cloudwatch'),
('ReadIOPS', 625.2, 'Count/Second', NOW() - INTERVAL '5 minutes', 'cloudwatch'),
('ReadIOPS', 485.3, 'Count/Second', NOW(), 'cloudwatch'),

('WriteIOPS', 45.2, 'Count/Second', NOW() - INTERVAL '1 hour', 'cloudwatch'),
('WriteIOPS', 65.8, 'Count/Second', NOW() - INTERVAL '50 minutes', 'cloudwatch'),
('WriteIOPS', 85.5, 'Count/Second', NOW() - INTERVAL '40 minutes', 'cloudwatch'),
('WriteIOPS', 125.2, 'Count/Second', NOW() - INTERVAL '30 minutes', 'cloudwatch'),
('WriteIOPS', 165.8, 'Count/Second', NOW() - INTERVAL '20 minutes', 'cloudwatch'),
('WriteIOPS', 205.5, 'Count/Second', NOW() - INTERVAL '10 minutes', 'cloudwatch'),
('WriteIOPS', 245.2, 'Count/Second', NOW() - INTERVAL '5 minutes', 'cloudwatch'),
('WriteIOPS', 185.8, 'Count/Second', NOW(), 'cloudwatch');

-- Create views for easy analysis
CREATE OR REPLACE VIEW performance_monitoring.slow_queries AS
SELECT 
    query_id,
    query_text,
    execution_time_ms,
    cpu_usage_percent,
    memory_usage_mb,
    executed_at,
    CASE 
        WHEN execution_time_ms > 10000 THEN 'Critical'
        WHEN execution_time_ms > 5000 THEN 'High'
        WHEN execution_time_ms > 1000 THEN 'Medium'
        ELSE 'Low'
    END as severity_level
FROM performance_monitoring.query_performance
WHERE execution_time_ms > 1000
ORDER BY execution_time_ms DESC;

CREATE OR REPLACE VIEW performance_monitoring.resource_usage_summary AS
SELECT 
    DATE_TRUNC('hour', recorded_at) as hour,
    metric_name,
    AVG(metric_value) as avg_value,
    MAX(metric_value) as max_value,
    MIN(metric_value) as min_value,
    COUNT(*) as sample_count
FROM performance_monitoring.system_metrics
GROUP BY DATE_TRUNC('hour', recorded_at), metric_name
ORDER BY hour DESC, metric_name;

-- Create function to simulate real-time performance issues
CREATE OR REPLACE FUNCTION performance_monitoring.simulate_performance_issue()
RETURNS TABLE(
    issue_type TEXT,
    severity TEXT,
    description TEXT,
    recommendation TEXT
) AS $$
BEGIN
    -- Simulate high CPU usage
    IF (SELECT AVG(metric_value) FROM performance_monitoring.system_metrics 
        WHERE metric_name = 'CPUUtilization' AND recorded_at > NOW() - INTERVAL '10 minutes') > 80 THEN
        
        RETURN QUERY SELECT 
            'High CPU Usage'::TEXT,
            'Critical'::TEXT,
            'CPU utilization is above 80% for the last 10 minutes'::TEXT,
            'Check for long-running queries and consider scaling up the instance'::TEXT;
    END IF;
    
    -- Simulate low memory
    IF (SELECT AVG(metric_value) FROM performance_monitoring.system_metrics 
        WHERE metric_name = 'FreeableMemory' AND recorded_at > NOW() - INTERVAL '10 minutes') < 1000 THEN
        
        RETURN QUERY SELECT 
            'Low Memory'::TEXT,
            'High'::TEXT,
            'Available memory is below 1GB for the last 10 minutes'::TEXT,
            'Consider increasing instance memory or optimizing query memory usage'::TEXT;
    END IF;
    
    -- Simulate slow queries
    IF EXISTS (SELECT 1 FROM performance_monitoring.query_performance 
               WHERE execution_time_ms > 5000 AND executed_at > NOW() - INTERVAL '1 hour') THEN
        
        RETURN QUERY SELECT 
            'Slow Queries Detected'::TEXT,
            'Medium'::TEXT,
            'Queries taking longer than 5 seconds detected in the last hour'::TEXT,
            'Review and optimize slow queries, check for missing indexes'::TEXT;
    END IF;
    
    -- Simulate connection issues
    IF (SELECT MAX(active_connections) FROM performance_monitoring.connection_metrics 
        WHERE recorded_at > NOW() - INTERVAL '10 minutes') > 80 THEN
        
        RETURN QUERY SELECT 
            'High Connection Count'::TEXT,
            'Medium'::TEXT,
            'Active connections are above 80% of maximum capacity'::TEXT,
            'Monitor connection pooling and consider increasing max_connections'::TEXT;
    END IF;
    
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT USAGE ON SCHEMA performance_monitoring TO PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA performance_monitoring TO PUBLIC;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA performance_monitoring TO PUBLIC;

-- Create sample incident detection data
INSERT INTO performance_monitoring.query_performance 
(query_id, query_text, execution_time_ms, rows_examined, rows_returned, cpu_usage_percent, memory_usage_mb, io_reads, io_writes, executed_at, database_name, user_name, connection_id)
VALUES 
-- Recent incidents
('INCIDENT_001', 'SELECT * FROM large_table WHERE unindexed_column LIKE ''%pattern%''', 45000, 10000000, 5000, 95.5, 1200, 8000, 0, NOW() - INTERVAL '5 minutes', 'workshop_db', 'app_user', 'conn_incident_001'),
('INCIDENT_002', 'UPDATE users SET status = ''inactive'' WHERE last_login < NOW() - INTERVAL ''1 year''', 35000, 2500000, 125000, 88.2, 800, 5000, 2500, NOW() - INTERVAL '3 minutes', 'workshop_db', 'admin_user', 'conn_incident_002'),
('INCIDENT_003', 'SELECT u.*, o.*, p.*, i.* FROM users u JOIN orders o ON u.id = o.user_id JOIN order_items oi ON o.id = oi.order_id JOIN products p ON oi.product_id = p.id JOIN inventory i ON p.id = i.product_id WHERE u.created_at > $1', 28000, 5000000, 50000, 75.8, 650, 4500, 0, NOW() - INTERVAL '1 minute', 'workshop_db', 'app_user', 'conn_incident_003');

COMMIT;