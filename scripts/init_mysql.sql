-- A privileged MySQL administrator runs this file once before assigning schema grants.
-- Apply `alembic upgrade head` to each schema that will be used by the app.
CREATE DATABASE IF NOT EXISTS instructor_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS instructor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS instructor_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
