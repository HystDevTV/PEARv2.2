CREATE TABLE IF NOT EXISTS customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  name VARCHAR(255),
  email VARCHAR(255),
  phone VARCHAR(64),
  address TEXT,
  source_subject TEXT,
  source_from_email VARCHAR(255),
  source_to_email VARCHAR(255),
  raw_json JSON
);
