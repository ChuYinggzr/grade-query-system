-- 成绩查询系统 - 建库建表 + 示例数据
-- 警告：本文件会删除整个 grade_system 数据库；已有数据时不要执行。
-- SQLAlchemy 新版首次建表请使用 README 中的 --init-db 流程，不需要本脚本。
-- 在 DataGrip / PyCharm Database / MySQL 命令行中执行本文件。
-- 说明：本脚本可重复执行，每次运行会重建 grade_system 库（会清除已有数据）。

DROP DATABASE IF EXISTS grade_system;
CREATE DATABASE grade_system DEFAULT CHARACTER SET utf8mb4;

USE grade_system;

-- 学生表
CREATE TABLE student (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '学号',
    name VARCHAR(50) NOT NULL COMMENT '姓名',
    class_name VARCHAR(50) COMMENT '班级'
);

-- 课程表
CREATE TABLE course (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '课程号',
    name VARCHAR(50) NOT NULL COMMENT '课程名'
);

-- 成绩表
CREATE TABLE score (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '成绩记录ID',
    student_id INT NOT NULL COMMENT '学号',
    course_id INT NOT NULL COMMENT '课程号',
    score DECIMAL(5,2) NOT NULL COMMENT '分数',
    UNIQUE KEY uk_student_course (student_id, course_id)
);

-- 外键：删除学生或课程时，自动删除其成绩记录
ALTER TABLE score
ADD CONSTRAINT fk_score_student
FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE;

ALTER TABLE score
ADD CONSTRAINT fk_score_course
FOREIGN KEY (course_id) REFERENCES course(id) ON DELETE CASCADE;

-- 示例数据：学生
INSERT INTO student (name, class_name) VALUES
('张三', '计算机2401'),
('李四', '计算机2401'),
('王五', '软件工程2402');

-- 示例数据：课程
INSERT INTO course (name) VALUES
('Python程序设计'),
('MySQL数据库'),
('数据结构');

-- 示例数据：成绩
INSERT INTO score (student_id, course_id, score) VALUES
(1, 1, 88.5),
(1, 2, 92.0),
(1, 3, 79.0),
(2, 1, 75.0),
(2, 2, 83.5),
(2, 3, 90.0),
(3, 1, 68.0),
(3, 2, 71.5),
(3, 3, 65.0);
