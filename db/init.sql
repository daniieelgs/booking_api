-- Reseteo de la base de datos 'bbdd'

-- Eliminar tablas si existen
DROP TABLE IF EXISTS image;
DROP TABLE IF EXISTS session_token;
DROP TABLE IF EXISTS user_session;
DROP TABLE IF EXISTS timetable;
DROP TABLE IF EXISTS service_booking;
DROP TABLE IF EXISTS service;
DROP TABLE IF EXISTS work_group_worker;
DROP TABLE IF EXISTS work_group;
DROP TABLE IF EXISTS booking;
DROP TABLE IF EXISTS worker;
DROP TABLE IF EXISTS status;
DROP TABLE IF EXISTS weekday;
DROP TABLE IF EXISTS smtp_settings;
DROP TABLE IF EXISTS local_settings;
DROP TABLE IF EXISTS file;
DROP TABLE IF EXISTS local;
DROP TABLE IF EXISTS api_settings;

-- Eliminar triggers de inserción si existen

DROP TRIGGER IF EXISTS before_insert_booking;

DROP TRIGGER IF EXISTS before_insert_local;

DROP TRIGGER IF EXISTS before_insert_service_booking;

DROP TRIGGER IF EXISTS before_insert_service;

DROP TRIGGER IF EXISTS before_insert_session_token;

DROP TRIGGER IF EXISTS before_insert_work_group;

DROP TRIGGER IF EXISTS before_insert_worker;

-- Eliminar triggers de actualización si existen

DROP TRIGGER IF EXISTS before_update_booking;

DROP TRIGGER IF EXISTS before_update_local;

DROP TRIGGER IF EXISTS before_update_service_booking;

DROP TRIGGER IF EXISTS before_update_service;

DROP TRIGGER IF EXISTS before_update_work_group;

DROP TRIGGER IF EXISTS before_update_worker;

-- Creación de la base de datos 'bbdd'

-- Creación de la tabla 'api_settings'
CREATE TABLE api_settings (
    id INT PRIMARY KEY,
    mail_contact VARCHAR(100),
    smtp_port INT,
    smtp_host VARCHAR(100),
    smtp_user VARCHAR(100),
    smtp_mail VARCHAR(100),
    smtp_password VARCHAR(100)
);

-- Creación de la tabla 'local'
CREATE TABLE local (
    id CHAR(32) PRIMARY KEY,
    name VARCHAR(45) NOT NULL,
    tlf VARCHAR(13) NOT NULL,
    email VARCHAR(70) NOT NULL UNIQUE,
    description MEDIUMTEXT,
    address VARCHAR(120),
    postal_code CHAR(5),
    village VARCHAR(45),
    province VARCHAR(45),
    location VARCHAR(30) NOT NULL,
    password VARCHAR(200) NOT NULL,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL
);

-- Creación de la tabla 'local_settings'
CREATE TABLE local_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    local_id CHAR(32) NOT NULL,
    domain VARCHAR(100),
    website VARCHAR(300),
    instagram VARCHAR(100),
    facebook VARCHAR(100),
    twitter VARCHAR(100),
    whatsapp VARCHAR(100),
    linkedin VARCHAR(100),
    tiktok VARCHAR(100),
    maps VARCHAR(800),
    email_contact VARCHAR(70),
    phone_contact VARCHAR(13),
    email_support VARCHAR(70),
    confirmation_link VARCHAR(500),
    cancel_link VARCHAR(500),
    `update_link` VARCHAR(500),
    booking_timeout INT,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL,
    FOREIGN KEY (local_id) REFERENCES local(id) ON DELETE CASCADE
);

-- Creación de la tabla 'smtp_settings'
CREATE TABLE smtp_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    local_settings_id INT NOT NULL,
    name VARCHAR(45) NOT NULL,
    host VARCHAR(100) NOT NULL,
    port INT NOT NULL,
    user VARCHAR(100) NOT NULL,
    mail VARCHAR(100) NOT NULL,
    password VARCHAR(100) NOT NULL,
    priority INT NOT NULL,
    send_per_day INT NOT NULL,
    send_per_month INT NOT NULL,
    max_send_per_day INT,
    max_send_per_month INT,
    reset_send_per_day DATETIME,
    reset_send_per_month DATETIME,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL,
    FOREIGN KEY (local_settings_id) REFERENCES local_settings(id) ON DELETE CASCADE,
    UNIQUE (local_settings_id, name),
    UNIQUE (local_settings_id, priority)
);


-- Creación de la tabla 'user_session'
CREATE TABLE user_session (
    id INT PRIMARY KEY,
    user CHAR(1) NOT NULL UNIQUE,
    name VARCHAR(45) NOT NULL
);

-- Creación de la tabla 'session_token'
CREATE TABLE session_token (
    id CHAR(32) PRIMARY KEY,
    jti CHAR(36) NOT NULL,
    local_id CHAR(32),
    user_session_id INT NOT NULL,
    name VARCHAR(30),
    datetime_created DATETIME NOT NULL,
    FOREIGN KEY (local_id) REFERENCES local(id) ON DELETE CASCADE,
    FOREIGN KEY (user_session_id) REFERENCES user_session(id)
);

-- Creación de la tabla 'images'
CREATE TABLE file (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(300) NOT NULL,
    local_id CHAR(32) NOT NULL,
    path VARCHAR(300) NOT NULL,
    mimetype VARCHAR(45) NOT NULL,
    FOREIGN KEY (local_id) REFERENCES local(id) ON DELETE CASCADE,
    UNIQUE (name, path, local_id)
);

-- Creación de la tabla 'weekday'
CREATE TABLE weekday(
    id INT PRIMARY KEY,
    weekday CHAR(2) NOT NULL UNIQUE,
    name VARCHAR(45) NOT NULL
);

-- Creación de la tabla 'timetable'
CREATE TABLE timetable(
    id INT PRIMARY KEY AUTO_INCREMENT,
    opening_time TIME NOT NULL,
    closing_time TIME NOT NULL,
    description MEDIUMTEXT,
    local_id CHAR(32) NOT NULL,
    weekday_id INT NOT NULL,
    FOREIGN KEY (local_id) REFERENCES local(id) ON DELETE CASCADE,
    FOREIGN KEY (weekday_id) REFERENCES weekday(id)
);

-- Creación de la tabla 'work_group'
CREATE TABLE work_group (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(45) NOT NULL,
    description MEDIUMTEXT,
    local_id CHAR(32) NOT NULL,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL,
    FOREIGN KEY (local_id) REFERENCES local(id) ON DELETE CASCADE,
    UNIQUE (name, local_id)
);

-- Creación de la tabla 'worker'
CREATE TABLE worker (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(35) NOT NULL,
    last_name VARCHAR(70),
    email VARCHAR(70),
    tlf VARCHAR(13),
    image VARCHAR(300),
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL
);

-- Relacion n:m de 'worker' y 'work_group'
CREATE TABLE work_group_worker(
    id INT PRIMARY KEY AUTO_INCREMENT,
    work_group_id INT NOT NULL,
    worker_id INT NOT NULL,
    FOREIGN KEY (work_group_id) REFERENCES work_group(id) ON DELETE CASCADE,
    FOREIGN KEY (worker_id) REFERENCES worker(id) ON DELETE CASCADE
);

-- Creación de la tabla 'service'
CREATE TABLE service (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(45) NOT NULL,
    duration INT NOT NULL,
    price DOUBLE NOT NULL,
    work_group_id INT NOT NULL,
    description MEDIUMTEXT,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL,
    FOREIGN KEY (work_group_id) REFERENCES work_group(id) ON DELETE CASCADE,
    UNIQUE (name, work_group_id)
);

-- Creación de la tabla 'status'
CREATE TABLE status(
	id INT PRIMARY KEY,
    status CHAR(1) NOT NULL UNIQUE,
    name VARCHAR(45)
);

-- Creación de la tabla 'booking'
CREATE TABLE booking (
    id INT PRIMARY KEY AUTO_INCREMENT,
    datetime_init DATETIME NOT NULL,
    datetime_end DATETIME NOT NULL,
    client_name VARCHAR(45),
    client_tlf VARCHAR(13),
    client_email VARCHAR(70),
    comment MEDIUMTEXT,
    status_id INT NOT NULL,
    worker_id INT,
    email_confirm BOOLEAN NOT NULL DEFAULT 0,
    email_confirmed BOOLEAN NOT NULL DEFAULT 0,
    email_cancelled BOOLEAN NOT NULL DEFAULT 0,
    email_updated BOOLEAN NOT NULL DEFAULT 0,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL,
    FOREIGN KEY (status_id) REFERENCES status(id),
    FOREIGN KEY (worker_id) REFERENCES worker(id) ON DELETE CASCADE
);

-- Creación de la tabla 'service_booking'
CREATE TABLE service_booking (
    id INT PRIMARY KEY AUTO_INCREMENT,
    service_id INT NOT NULL,
    booking_id INT NOT NULL,
    datetime_created DATETIME NOT NULL,
    datetime_updated DATETIME NOT NULL,
    FOREIGN KEY (service_id) REFERENCES service(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES booking(id) ON DELETE CASCADE
);

-- Insertar datos en la tabla 'weekday'
INSERT INTO weekday (id, weekday, name) VALUES (1, 'MO', 'Monday');
INSERT INTO weekday (id, weekday, name) VALUES (2, 'TU', 'Tuesday');
INSERT INTO weekday (id, weekday, name) VALUES (3, 'WE', 'Wednesday');
INSERT INTO weekday (id, weekday, name) VALUES (4, 'TH', 'Thursday');
INSERT INTO weekday (id, weekday, name) VALUES (5, 'FR', 'Friday');
INSERT INTO weekday (id, weekday, name) VALUES (6, 'SA', 'Saturday');
INSERT INTO weekday (id, weekday, name) VALUES (7, 'SU', 'Sunday');

-- Insertar datos en la tabla 'status'
INSERT INTO status (id, status, name) VALUES (1, 'P', 'Pending');
INSERT INTO status (id, status, name) VALUES (2, 'C', 'Confirmed');
INSERT INTO status (id, status, name) VALUES (3, 'D', 'Done');
INSERT INTO status (id, status, name) VALUES (4, 'X', 'Cancelled');

-- Insertat datos en la tabla 'user_session'
INSERT INTO user_session (id, user, name) VALUES (1, 'A', 'Admin');
INSERT INTO user_session (id, user, name) VALUES (2, 'L', 'Local');
INSERT INTO user_session (id, user, name) VALUES (3, 'U', 'User');

-- Creación de los triggers

DELIMITER $$

-- Insert triggers

CREATE TRIGGER before_insert_booking
BEFORE INSERT ON booking
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_insert_local
BEFORE INSERT ON local
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_insert_service_booking
BEFORE INSERT ON service_booking
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_insert_service
BEFORE INSERT ON service
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_insert_session_token
BEFORE INSERT ON session_token
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
END $$

CREATE TRIGGER before_insert_work_group
BEFORE INSERT ON work_group
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_insert_worker
BEFORE INSERT ON worker
FOR EACH ROW
BEGIN
    SET NEW.datetime_created = NOW();
    SET NEW.datetime_updated = NOW();
END $$

-- Update triggers

CREATE TRIGGER before_update_booking
BEFORE UPDATE ON booking
FOR EACH ROW
BEGIN
    IF NEW.datetime_created <> OLD.datetime_created THEN
        SET NEW.datetime_created = OLD.datetime_created;
    END IF;
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_update_local
BEFORE UPDATE ON local
FOR EACH ROW
BEGIN
    IF NEW.datetime_created <> OLD.datetime_created THEN
        SET NEW.datetime_created = OLD.datetime_created;
    END IF;
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_update_service_booking
BEFORE UPDATE ON service_booking
FOR EACH ROW
BEGIN
    IF NEW.datetime_created <> OLD.datetime_created THEN
        SET NEW.datetime_created = OLD.datetime_created;
    END IF;
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_update_service
BEFORE UPDATE ON service
FOR EACH ROW
BEGIN
    IF NEW.datetime_created <> OLD.datetime_created THEN
        SET NEW.datetime_created = OLD.datetime_created;
    END IF;
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_update_work_group
BEFORE UPDATE ON work_group
FOR EACH ROW
BEGIN
    IF NEW.datetime_created <> OLD.datetime_created THEN
        SET NEW.datetime_created = OLD.datetime_created;
    END IF;
    SET NEW.datetime_updated = NOW();
END $$

CREATE TRIGGER before_update_worker
BEFORE UPDATE ON worker
FOR EACH ROW
BEGIN
    IF NEW.datetime_created <> OLD.datetime_created THEN
        SET NEW.datetime_created = OLD.datetime_created;
    END IF;
    SET NEW.datetime_updated = NOW();
END $$

DELIMITER ;