-- Reference DDL generated from app.models. Apply Alembic for an application database.

CREATE TABLE accounts (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	username VARCHAR(64), 
	email VARCHAR(254), 
	name VARCHAR(100), 
	organization VARCHAR(100), 
	phone VARCHAR(32), 
	password_hash VARCHAR(255), 
	`role` VARCHAR(16) NOT NULL, 
	deleted_at DATETIME(6), 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_accounts PRIMARY KEY (id), 
	CONSTRAINT ck_accounts_role CHECK (role IN ('teacher', 'instructor', 'admin')), 
	CONSTRAINT uq_accounts_username UNIQUE (username), 
	CONSTRAINT uq_accounts_email UNIQUE (email)
);

CREATE TABLE admin_login_attempts (
	username VARCHAR(64) NOT NULL, 
	failures SMALLINT NOT NULL DEFAULT 0, 
	window_started_at DATETIME(6) NOT NULL, 
	blocked_until DATETIME(6), 
	CONSTRAINT pk_admin_login_attempts PRIMARY KEY (username)
);

CREATE INDEX ix_admin_login_attempts_window_started_at ON admin_login_attempts (window_started_at);

CREATE TABLE post_deletions (
	post_id BIGINT NOT NULL, 
	deleted_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_post_deletions PRIMARY KEY (post_id)
);

CREATE TABLE activity_logs (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	actor_id BIGINT NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	resource VARCHAR(30) NOT NULL, 
	resource_id BIGINT NOT NULL, 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_activity_logs PRIMARY KEY (id), 
	CONSTRAINT fk_activity_logs_actor_id_accounts FOREIGN KEY(actor_id) REFERENCES accounts (id)
);

CREATE INDEX ix_activity_logs_actor_id ON activity_logs (actor_id);

CREATE INDEX ix_activity_logs_created ON activity_logs (created_at, id);

CREATE TABLE dm_rooms (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	low_id BIGINT NOT NULL, 
	high_id BIGINT NOT NULL, 
	low_active BOOL NOT NULL DEFAULT 1, 
	high_active BOOL NOT NULL DEFAULT 1, 
	low_read_id BIGINT NOT NULL DEFAULT 0, 
	high_read_id BIGINT NOT NULL DEFAULT 0, 
	low_hidden_through BIGINT NOT NULL DEFAULT 0, 
	high_hidden_through BIGINT NOT NULL DEFAULT 0, 
	last_message_id BIGINT NOT NULL DEFAULT 0, 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_dm_rooms PRIMARY KEY (id), 
	CONSTRAINT uq_dm_rooms_low_id UNIQUE (low_id, high_id), 
	CONSTRAINT ck_dm_rooms_participant_order CHECK (low_id < high_id), 
	CONSTRAINT fk_dm_rooms_low_id_accounts FOREIGN KEY(low_id) REFERENCES accounts (id), 
	CONSTRAINT fk_dm_rooms_high_id_accounts FOREIGN KEY(high_id) REFERENCES accounts (id)
);

CREATE INDEX ix_dm_rooms_high_active ON dm_rooms (high_id, high_active, last_message_id);

CREATE INDEX ix_dm_rooms_low_active ON dm_rooms (low_id, low_active, last_message_id);

CREATE TABLE instructor_profiles (
	account_id BIGINT NOT NULL, 
	photo_url VARCHAR(2048), 
	specialty VARCHAR(255), 
	experience TEXT, 
	bio TEXT, 
	kind VARCHAR(16) NOT NULL DEFAULT 'personal', 
	category VARCHAR(80), 
	skills VARCHAR(500), 
	audience VARCHAR(500), 
	distance_km INTEGER, 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_instructor_profiles PRIMARY KEY (account_id), 
	CONSTRAINT ck_instructor_profiles_kind CHECK (kind IN ('personal', 'company')), 
	CONSTRAINT ck_instructor_profiles_distance CHECK (distance_km >= 0), 
	CONSTRAINT fk_instructor_profiles_account_id_accounts FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
);

CREATE TABLE login_sessions (
	token_hash BINARY(32) NOT NULL, 
	account_id BIGINT NOT NULL, 
	expires_at DATETIME(6) NOT NULL, 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_login_sessions PRIMARY KEY (token_hash), 
	CONSTRAINT fk_login_sessions_account_id_accounts FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
);

CREATE INDEX ix_login_sessions_account_id ON login_sessions (account_id);

CREATE INDEX ix_login_sessions_expires_at ON login_sessions (expires_at);

CREATE TABLE password_resets (
	account_id BIGINT NOT NULL, 
	nonce BINARY(32) NOT NULL, 
	code_hash BINARY(32), 
	ticket_hash BINARY(32), 
	failures SMALLINT NOT NULL DEFAULT 0, 
	expires_at DATETIME(6) NOT NULL, 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_password_resets PRIMARY KEY (account_id), 
	CONSTRAINT fk_password_resets_account_id_accounts FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
);

CREATE TABLE posts (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	author_id BIGINT NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body MEDIUMTEXT NOT NULL, 
	category VARCHAR(80) NOT NULL, 
	audience VARCHAR(80) NOT NULL, 
	scale VARCHAR(80) NOT NULL, 
	skills VARCHAR(500), 
	tech_stack VARCHAR(500), 
	region VARCHAR(100), 
	availability VARCHAR(500), 
	duration_minutes INTEGER, 
	distance_km INTEGER, 
	price INTEGER, 
	additional_info TEXT, 
	view_count BIGINT NOT NULL DEFAULT 0, 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_posts PRIMARY KEY (id), 
	CONSTRAINT ck_posts_views CHECK (view_count >= 0), 
	CONSTRAINT ck_posts_duration CHECK (duration_minutes IS NULL OR duration_minutes > 0), 
	CONSTRAINT ck_posts_distance CHECK (distance_km >= 0), 
	CONSTRAINT ck_posts_price CHECK (price >= 0), 
	CONSTRAINT fk_posts_author_id_accounts FOREIGN KEY(author_id) REFERENCES accounts (id)
);

CREATE INDEX ix_posts_audience_created ON posts (audience, created_at, id);

CREATE INDEX ix_posts_author_created ON posts (author_id, created_at, id);

CREATE INDEX ix_posts_category_created ON posts (category, created_at, id);

CREATE INDEX ix_posts_created ON posts (created_at, id);

CREATE INDEX ix_posts_region_created ON posts (region, created_at, id);

CREATE INDEX ix_posts_view_order ON posts (view_count, created_at, id);

CREATE TABLE comments (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	post_id BIGINT NOT NULL, 
	author_id BIGINT NOT NULL, 
	parent_id BIGINT, 
	body TEXT, 
	deleted_at DATETIME(6), 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_comments PRIMARY KEY (id), 
	CONSTRAINT uq_comments_post_id UNIQUE (post_id, id), 
	CONSTRAINT fk_comments_parent_same_post FOREIGN KEY(post_id, parent_id) REFERENCES comments (post_id, id) ON DELETE CASCADE, 
	CONSTRAINT fk_comments_post_id_posts FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_comments_author_id_accounts FOREIGN KEY(author_id) REFERENCES accounts (id)
);

CREATE INDEX ix_comments_author_created ON comments (author_id, created_at, id);

CREATE INDEX ix_comments_post_created ON comments (post_id, created_at, id);

CREATE INDEX ix_comments_post_parent ON comments (post_id, parent_id);

CREATE TABLE dm_messages (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	room_id BIGINT NOT NULL, 
	sender_id BIGINT NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	body TEXT, 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_dm_messages PRIMARY KEY (id), 
	CONSTRAINT uq_dm_messages_room_id UNIQUE (room_id, sender_id, client_id), 
	CONSTRAINT fk_dm_messages_room_id_dm_rooms FOREIGN KEY(room_id) REFERENCES dm_rooms (id) ON DELETE CASCADE, 
	CONSTRAINT fk_dm_messages_sender_id_accounts FOREIGN KEY(sender_id) REFERENCES accounts (id)
);

CREATE INDEX ix_dm_messages_room_order ON dm_messages (room_id, id);

CREATE INDEX ix_dm_messages_sender_id ON dm_messages (sender_id);

CREATE TABLE post_attachments (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	post_id BIGINT NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	media_type VARCHAR(64) NOT NULL, 
	size INTEGER NOT NULL, 
	data MEDIUMBLOB NOT NULL, 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_post_attachments PRIMARY KEY (id), 
	CONSTRAINT fk_post_attachments_post_id_posts FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE
);

CREATE INDEX ix_post_attachments_post_id ON post_attachments (post_id);

CREATE TABLE reaction_changes (
	post_id BIGINT NOT NULL, 
	account_id BIGINT NOT NULL, 
	changed_at DATETIME(6) NOT NULL, 
	CONSTRAINT pk_reaction_changes PRIMARY KEY (post_id, account_id), 
	CONSTRAINT fk_reaction_changes_post_id_posts FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_reaction_changes_account_id_accounts FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
);

CREATE INDEX ix_reaction_changes_account_id ON reaction_changes (account_id);

CREATE TABLE reactions (
	post_id BIGINT NOT NULL, 
	account_id BIGINT NOT NULL, 
	value SMALLINT NOT NULL, 
	CONSTRAINT pk_reactions PRIMARY KEY (post_id, account_id), 
	CONSTRAINT ck_reactions_value CHECK (value IN (-1, 1)), 
	CONSTRAINT fk_reactions_post_id_posts FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_reactions_account_id_accounts FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
);

CREATE INDEX ix_reactions_account_id ON reactions (account_id);

CREATE INDEX ix_reactions_post_value ON reactions (post_id, value);

CREATE TABLE reviews (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	post_id BIGINT NOT NULL, 
	author_id BIGINT NOT NULL, 
	rating SMALLINT NOT NULL, 
	body TEXT NOT NULL, 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	CONSTRAINT pk_reviews PRIMARY KEY (id), 
	CONSTRAINT uq_reviews_post_id UNIQUE (post_id, author_id), 
	CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5), 
	CONSTRAINT fk_reviews_post_id_posts FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_reviews_author_id_accounts FOREIGN KEY(author_id) REFERENCES accounts (id)
);

CREATE INDEX ix_reviews_author_id ON reviews (author_id);

CREATE INDEX ix_reviews_post_created ON reviews (post_id, created_at, id);

CREATE INDEX ix_reviews_post_rating ON reviews (post_id, rating, created_at, id);

CREATE TABLE dm_attachments (
	message_id BIGINT NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	media_type VARCHAR(64) NOT NULL, 
	size INTEGER NOT NULL, 
	data MEDIUMBLOB NOT NULL, 
	CONSTRAINT pk_dm_attachments PRIMARY KEY (message_id), 
	CONSTRAINT fk_dm_attachments_message_id_dm_messages FOREIGN KEY(message_id) REFERENCES dm_messages (id) ON DELETE CASCADE
);
