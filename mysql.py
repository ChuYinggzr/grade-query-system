"""成绩管理系统：使用熟悉的 Flask-SQLAlchemy 写法操作数据库。"""

import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


# 读取项目目录中的 .env 配置文件。
load_dotenv(Path(__file__).with_name(".env"))

app = Flask(__name__)

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "grade_system")

# 正常运行时连接 MySQL；测试时可以通过 DATABASE_URL 临时改用 SQLite。
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL") or (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ------------------- 数据模型：对应三张数据库表 -------------------
class Student(db.Model):
    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    class_name = db.Column(db.String(50))


class Course(db.Model):
    __tablename__ = "course"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)


class Score(db.Model):
    __tablename__ = "score"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id", name="fk_score_student", ondelete="CASCADE"),
        nullable=False,
    )
    course_id = db.Column(
        db.Integer,
        db.ForeignKey("course.id", name="fk_score_course", ondelete="CASCADE"),
        nullable=False,
    )
    score = db.Column(db.Numeric(5, 2), nullable=False)

    # 同一名学生的同一门课程只能保存一条成绩。
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uk_student_course"),
    )


def init_tables():
    """创建缺少的表，不删除已有表和数据。"""
    try:
        db.create_all()
        print("表初始化完成：已有的表和数据不会被重建")
        return True
    except SQLAlchemyError:
        print("数据库初始化失败：请检查MySQL服务、配置、权限和数据库是否已创建")
        return False


def validate_score(value):
    """检查成绩是否为0到100之间、最多两位小数的数字。"""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        print("错误：分数必须是数字")
        return None

    if not number.is_finite() or not 0 <= number <= 100:
        print("错误：成绩必须在0到100之间")
        return None

    if number != number.quantize(Decimal("0.01")):
        print("错误：成绩最多保留两位小数")
        return None

    return number


# ------------------- 常用查询：与用户账户项目写法一致 -------------------
def select_student_by_id(student_id):
    return db.session.get(Student, student_id)


def select_course_by_id(course_id):
    return db.session.get(Course, course_id)


def select_score(student_id, course_id):
    return Score.query.filter_by(
        student_id=student_id,
        course_id=course_id,
    ).first()


# ------------------- 增加数据 -------------------
def add_student(name, class_name):
    name = name.strip()
    class_name = class_name.strip() or "未分班"

    if not name:
        print("错误：学生姓名不能为空")
        return None

    if len(name) > 50 or len(class_name) > 50:
        print("错误：学生姓名和班级不能超过50个字符")
        return None

    try:
        student = Student(name=name, class_name=class_name)
        db.session.add(student)
        db.session.commit()
        print(f"已添加学生：{name}，学号：{student.id}")
        return student.id
    except SQLAlchemyError:
        db.session.rollback()
        print("添加学生失败：请检查数据库连接、表结构和权限")
        return None


def add_course(name):
    name = name.strip()

    if not name or len(name) > 50:
        print("错误：课程名不能为空，且不能超过50个字符")
        return None

    try:
        course = Course(name=name)
        db.session.add(course)
        db.session.commit()
        print(f"已添加课程：{name}，课程号：{course.id}")
        return course.id
    except SQLAlchemyError:
        db.session.rollback()
        print("添加课程失败：请检查数据库连接、表结构和权限")
        return None


def add_score(student_id, course_id, score):
    score = validate_score(score)
    if score is None:
        return False

    try:
        if select_student_by_id(student_id) is None:
            print(f"错误：学生ID {student_id} 不存在")
            return False

        if select_course_by_id(course_id) is None:
            print(f"错误：课程ID {course_id} 不存在")
            return False

        if select_score(student_id, course_id) is not None:
            print("错误：该学生的这门课程成绩已存在，请使用修改功能")
            return False

        record = Score(
            student_id=student_id,
            course_id=course_id,
            score=score,
        )
        db.session.add(record)
        db.session.commit()
        print("已录入成绩")
        return True
    except IntegrityError:
        db.session.rollback()
        print("录入失败：成绩重复，或学生、课程已被删除")
        return False
    except SQLAlchemyError:
        db.session.rollback()
        print("录入失败：请检查数据库连接、表结构和权限")
        return False


# ------------------- 修改数据 -------------------
def update_score(student_id, course_id, new_score):
    new_score = validate_score(new_score)
    if new_score is None:
        return False

    try:
        record = select_score(student_id, course_id)
        if record is None:
            print("错误：没有这条成绩记录，无法修改")
            return False

        record.score = new_score
        db.session.commit()
        print("成绩修改成功")
        return True
    except SQLAlchemyError:
        db.session.rollback()
        print("修改失败：请检查数据库连接、表结构和权限")
        return False


# ------------------- 删除数据 -------------------
def delete_student(student_id):
    try:
        student = select_student_by_id(student_id)
        if student is None:
            print(f"错误：学生ID {student_id} 不存在")
            return False

        db.session.delete(student)
        db.session.commit()
        print(f"学生 {student_id} 及其成绩已删除")
        return True
    except SQLAlchemyError:
        db.session.rollback()
        print("删除学生失败：请检查数据库连接和外键约束")
        return False


def delete_course(course_id):
    try:
        course = select_course_by_id(course_id)
        if course is None:
            print(f"错误：课程ID {course_id} 不存在")
            return False

        db.session.delete(course)
        db.session.commit()
        print(f"课程 {course_id} 及其成绩已删除")
        return True
    except SQLAlchemyError:
        db.session.rollback()
        print("删除课程失败：请检查数据库连接和外键约束")
        return False


def delete_score(student_id, course_id):
    try:
        record = select_score(student_id, course_id)
        if record is None:
            print("错误：没有这条成绩记录")
            return False

        db.session.delete(record)
        db.session.commit()
        print("成绩删除成功")
        return True
    except SQLAlchemyError:
        db.session.rollback()
        print("删除成绩失败：请检查数据库连接、表结构和权限")
        return False


# ------------------- 查询数据：使用已经学过的SQL JOIN -------------------
def query_student(student_id):
    try:
        if select_student_by_id(student_id) is None:
            print(f"错误：学生ID {student_id} 不存在")
            return []

        result = db.session.execute(
            text(
                """
                SELECT s.name, c.name, sc.score
                FROM score AS sc
                JOIN student AS s ON sc.student_id = s.id
                JOIN course AS c ON sc.course_id = c.id
                WHERE sc.student_id = :student_id
                ORDER BY c.id
                """
            ),
            {"student_id": student_id},
        )
        rows = result.all()

        print("\n=== 学生成绩 ===")
        for name, course, score in rows:
            print(f"{name} | {course} | {score}")
        if not rows:
            print("没有记录")
        return rows
    except SQLAlchemyError:
        db.session.rollback()
        print("查询失败：请检查数据库连接、表结构和权限")
        return []


def query_course(course_id):
    try:
        if select_course_by_id(course_id) is None:
            print(f"错误：课程ID {course_id} 不存在")
            return []

        result = db.session.execute(
            text(
                """
                SELECT s.name, c.name, sc.score
                FROM score AS sc
                JOIN student AS s ON sc.student_id = s.id
                JOIN course AS c ON sc.course_id = c.id
                WHERE sc.course_id = :course_id
                ORDER BY s.id
                """
            ),
            {"course_id": course_id},
        )
        rows = result.all()

        print("\n=== 课程成绩 ===")
        for name, course, score in rows:
            print(f"{name} | {course} | {score}")
        if not rows:
            print("没有记录")
        return rows
    except SQLAlchemyError:
        db.session.rollback()
        print("查询失败：请检查数据库连接、表结构和权限")
        return []


def query_all():
    try:
        result = db.session.execute(
            text(
                """
                SELECT s.name, c.name, sc.score
                FROM score AS sc
                JOIN student AS s ON sc.student_id = s.id
                JOIN course AS c ON sc.course_id = c.id
                ORDER BY s.id, c.id
                """
            )
        )
        rows = result.all()

        print("\n=== 全部成绩 ===")
        for name, course, score in rows:
            print(f"{name} | {course} | {score}")
        if not rows:
            print("暂无成绩记录")
        return rows
    except SQLAlchemyError:
        db.session.rollback()
        print("查询失败：请检查数据库连接、表结构和权限")
        return []


# ------------------- 命令行菜单 -------------------
def menu():
    while True:
        print("\n--- 成绩查询系统 ---")
        print("1. 添加学生")
        print("2. 添加课程")
        print("3. 录入成绩")
        print("4. 查询某学生成绩")
        print("5. 查询某课程成绩")
        print("6. 查看全部成绩")
        print("7. 修改成绩")
        print("8. 删除学生")
        print("9. 删除课程")
        print("10. 删除成绩记录")
        print("0. 退出")
        choice = input("请选择：").strip()

        if choice == "1":
            name = input("学生姓名：").strip()
            class_name = input("班级：").strip()
            add_student(name, class_name)

        elif choice == "2":
            name = input("课程名：").strip()
            add_course(name)

        elif choice == "3":
            try:
                student_id = int(input("学号：").strip())
                course_id = int(input("课程号：").strip())
                score = input("分数：").strip()
                add_score(student_id, course_id, score)
            except ValueError:
                print("错误：学号和课程号必须是整数")

        elif choice == "4":
            try:
                student_id = int(input("学号：").strip())
                query_student(student_id)
            except ValueError:
                print("错误：学号必须是数字")

        elif choice == "5":
            try:
                course_id = int(input("课程号：").strip())
                query_course(course_id)
            except ValueError:
                print("错误：课程号必须是数字")

        elif choice == "6":
            query_all()

        elif choice == "7":
            try:
                student_id = int(input("学号：").strip())
                course_id = int(input("课程号：").strip())
                new_score = input("新分数：").strip()
                update_score(student_id, course_id, new_score)
            except ValueError:
                print("错误：学号和课程号必须是整数")

        elif choice == "8":
            try:
                student_id = int(input("要删除的学生学号：").strip())
                delete_student(student_id)
            except ValueError:
                print("错误：学号必须是数字")

        elif choice == "9":
            try:
                course_id = int(input("要删除的课程号：").strip())
                delete_course(course_id)
            except ValueError:
                print("错误：课程号必须是数字")

        elif choice == "10":
            try:
                student_id = int(input("学号：").strip())
                course_id = int(input("课程号：").strip())
                delete_score(student_id, course_id)
            except ValueError:
                print("错误：学号和课程号必须是数字")

        elif choice == "0":
            print("再见")
            break

        else:
            print("无效选项，请重新输入")


if __name__ == "__main__":
    # 命令行程序没有HTTP请求，所以要手动进入Flask应用上下文。
    with app.app_context():
        if sys.argv[1:] == ["--init-db"]:
            sys.exit(0 if init_tables() else 1)
        elif sys.argv[1:]:
            print("用法：python mysql.py 或 python mysql.py --init-db")
            sys.exit(1)
        else:
            menu()
